from django.core.management.base import BaseCommand
from django.utils import timezone
import pandas as pd
import datetime
import tempfile
import csv
import os
import random
from decimal import Decimal

# ml pipeline helpers (feature generation, prediction helpers, and training helper)
from Sales_forecast import ml_pipeline
from xgboost import XGBRegressor

# Defensive imports for optional DB usage
try:
    from POS.utils import get_daily_sales_df
except Exception:
    get_daily_sales_df = None

try:
    from Inventory.models import Item
except Exception:
    Item = None

try:
    from Sales_forecast.models import ForecastRun
except Exception:
    ForecastRun = None

from django.core.management import call_command


def print_header(title, compact=False):
    if compact:
        print(f"-- {title} --")
    else:
        print("\n" + "=" * 80)
        print(f" {title}")
        print("=" * 80)


def ascii_chart(dates, actual_vals, forecast_vals=None, height=12, label_actual="Actual", label_forecast="Forecast"):
    all_vals = [v for v in (list(actual_vals) + (list(forecast_vals) if forecast_vals else [])) if v is not None]
    if not all_vals:
        print("(No data to chart)")
        return
    vmax = max(all_vals)
    vmin = min(all_vals)
    if vmax == vmin:
        vmax += 1.0
        vmin = max(0, vmin - 1)
    cols = len(dates)
    grid = [[" " for _ in range(cols)] for _ in range(height)]

    def value_to_row(v):
        return int(round((v - vmin) / (vmax - vmin) * (height - 1)))

    for i, v in enumerate(actual_vals):
        if v is None:
            continue
        r = value_to_row(v)
        grid[height - 1 - r][i] = "*"

    if forecast_vals:
        f_len = len(forecast_vals)
        start = cols - f_len
        for j, v in enumerate(forecast_vals):
            idx = start + j
            if idx < 0 or idx >= cols or v is None:
                continue
            r = value_to_row(v)
            cur = grid[height - 1 - r][idx]
            if cur == "*":
                grid[height - 1 - r][idx] = "X"
            else:
                grid[height - 1 - r][idx] = "o"

    for row_i, row in enumerate(grid):
        yval = vmin + (height - 1 - row_i) * (vmax - vmin) / (height - 1)
        print(f"{yval:8.2f} | " + "".join(row))
    print(" " * 10 + "-" * cols)
    label_line = [" " for _ in range(cols)]
    step = max(1, cols // 10)
    for i, d in enumerate(dates):
        if i % step == 0 or i == cols - 1:
            s = str(d)[0:10]
            for k, ch in enumerate(s):
                if i + k < cols:
                    label_line[i + k] = ch
    print(" " * 11 + "".join(label_line))
    print(f"Legend: '*' = {label_actual}, 'o' = {label_forecast}, 'X' = overlap")


class Command(BaseCommand):
    help = "Simulate an interactive terminal-based Sales Forecast dashboard (in-memory testing by default)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Run once with defaults and exit (non-interactive).",
        )
        parser.add_argument(
            "--export-dir",
            type=str,
            default=None,
            help="Directory where CSV exports should be written (default: temp folder)",
        )
        parser.add_argument(
            "--compact",
            action="store_true",
            help="Use compact UI mode for smaller terminal windows",
        )

    def handle(self, *args, **options):
        interactive = not options.get("auto", False)
        export_dir = options.get("export_dir")
        compact_mode = options.get("compact", False)

        view_mode = "daily"
        horizon = 7
        smooth = True
        products = []
        try:
            if Item is not None:
                products = list(Item.objects.all())
        except Exception:
            products = []
        product_choice = None
        working_df = None

        def generate_dummy_df(days_back=30, base=20, volatility=10):
            today = datetime.date.today()
            rows = []
            for i in range(days_back):
                d = today - datetime.timedelta(days=(days_back - 1 - i))
                dow = d.weekday()
                multiplier = 1.0 + (0.2 if dow >= 5 else 0.0)
                val = max(0.0, base * multiplier + random.gauss(0, volatility))
                rows.append({"date": d, "total_quantity": float(round(val, 2))})
            return pd.DataFrame(rows)

        def load_historical_from_db(product_id=None, days=30):
            if get_daily_sales_df is None:
                return None
            try:
                end = datetime.date.today()
                start = end - datetime.timedelta(days=days - 1)
                df = get_daily_sales_df(start_date=start, end_date=end, product_id=product_id)
                if df is None or df.empty:
                    return None
                if "total_quantity" in df.columns:
                    df = df[["date", "total_quantity"]]
                elif "total_revenue" in df.columns:
                    df = df.rename(columns={"total_revenue": "total_quantity"})[["date", "total_quantity"]]
                else:
                    for c in df.columns:
                        if c != "date":
                            df = df.rename(columns={c: "total_quantity"})[["date", "total_quantity"]]
                            break
                df["date"] = pd.to_datetime(df["date"]).dt.date
                return df
            except Exception as e:
                print("Failed to read historical from DB:", e)
                return None

        def build_and_predict(df_hist, horizon_days, attempt_load_model=False, force=False):
            if df_hist is None or df_hist.empty:
                return [], []
            df = df_hist.copy().sort_values("date").reset_index(drop=True)
            recent = df.copy()
            recent["date"] = pd.to_datetime(recent["date"])

            model = None
            if attempt_load_model:
                try:
                    model = ml_pipeline.load_model()
                    if not compact_mode:
                        print("Loaded persisted model artifact.")
                except Exception:
                    model = None

            if model is None:
                try:
                    X, y, df_fe = ml_pipeline.make_supervised(df.rename(columns={"total_quantity": "total_quantity"}))
                    if X.shape[0] < 3 and not force:
                        if not compact_mode:
                            print("Not enough rows to train; using naive forecast (repeat last value).")
                        last_value = float(df["total_quantity"].iloc[-1])
                        preds = []
                        next_date = df["date"].max() + pd.Timedelta(days=1)
                        for i in range(horizon_days):
                            preds.append({"date": (next_date + pd.Timedelta(days=i)).date(), "predicted": float(last_value)})
                        hist_serial = [{"date": r["date"], "actual": float(r["total_quantity"])} for _, r in df.iterrows()]
                        return hist_serial, preds
                    model = XGBRegressor(objective="reg:squarederror", n_estimators=200, random_state=42)
                    model.fit(X, y)
                    if not compact_mode:
                        print("Trained in-memory test model.")
                except Exception as e:
                    if not compact_mode:
                        print("Training failed, falling back to naive forecast:", e)
                    last_value = float(df["total_quantity"].iloc[-1])
                    preds = []
                    next_date = df["date"].max() + pd.Timedelta(days=1)
                    for i in range(horizon_days):
                        preds.append({"date": (next_date + pd.Timedelta(days=i)).date(), "predicted": float(last_value)})
                    hist_serial = [{"date": r["date"], "actual": float(r["total_quantity"])} for _, r in df.iterrows()]
                    return hist_serial, preds

            try:
                forecast_df = ml_pipeline.predict_future_sales(model, recent, horizon=horizon_days)
                forecast_records = []
                for r in forecast_df.to_dict(orient="records"):
                    d = r.get("date")
                    if isinstance(d, pd.Timestamp):
                        d = pd.to_datetime(d).date()
                    elif isinstance(d, datetime.datetime):
                        d = d.date()
                    forecast_records.append({"date": d, "predicted": float(r.get("predicted", 0.0))})
                hist_serial = [{"date": r["date"], "actual": float(r["total_quantity"])} for _, r in df.iterrows()]
                return hist_serial, forecast_records
            except Exception as e:
                if not compact_mode:
                    print("Prediction failed, naive fallback:", e)
                last_value = float(df["total_quantity"].iloc[-1])
                preds = []
                next_date = df["date"].max() + pd.Timedelta(days=1)
                for i in range(horizon_days):
                    preds.append({"date": (next_date + pd.Timedelta(days=i)).date(), "predicted": float(last_value)})
                hist_serial = [{"date": r["date"], "actual": float(r["total_quantity"])} for _, r in df.iterrows()]
                return hist_serial, preds

        def compute_kpis(historical, forecast, horizon_days):
            today_sales = 0.0
            if historical:
                today_sales = float(historical[-1]["actual"])
            next_forecast = float(forecast[0]["predicted"]) if forecast else 0.0
            look = min(7, horizon_days)
            avg_last7 = 0.0
            if len(historical) >= look:
                avg_last7 = sum([h["actual"] for h in historical[-look:]]) / look
            avg_next = 0.0
            if len(forecast) >= look:
                avg_next = sum([f["predicted"] for f in forecast[:look]]) / look
            pct_change = ((avg_next - avg_last7) / avg_last7 * 100.0) if avg_last7 else 0.0
            return {"today_sales": today_sales, "next_forecast": next_forecast, "pct_change": pct_change}

        def print_dashboard(historical, forecast, horizon_days, view_mode_local, smooth_local, compact=False):
            print_header("SALES FORECAST DASHBOARD (Terminal Simulation)", compact=compact)
            kpi = compute_kpis(historical, forecast, horizon_days)
            if compact:
                print(f"View:{view_mode_local[:4]} Horizon:{horizon_days} Smooth:{'ON' if smooth_local else 'OFF'}")
            else:
                print(f"View: {view_mode_local.capitalize()} | Horizon: {horizon_days} day(s) | Smooth: {'ON' if smooth_local else 'OFF'}")
                print("-" * 80)
            print(f"Today's Sales:        ?{kpi['today_sales']:.2f}")
            print(f"Next Day Forecast:    ?{kpi['next_forecast']:.2f}")
            print(f"7-day Change:         {kpi['pct_change']:+.2f}%")
            if not compact:
                print("-" * 80)

            last_n = 30
            hist_to_plot = historical[-last_n:] if len(historical) >= last_n else historical
            dates = [r["date"].isoformat() if hasattr(r["date"], "isoformat") else str(r["date"]) for r in hist_to_plot]
            actuals = [r["actual"] for r in hist_to_plot]
            labels_combined = dates + [f["date"].isoformat() for f in forecast]
            actuals_combined = actuals + [None] * len(forecast)
            forecast_combined = [None] * len(dates) + [f["predicted"] for f in forecast]
            if compact:
                print("ASCII Chart (Actual vs Forecast):")
            ascii_chart(labels_combined, actuals_combined, forecast_combined, height=12, label_actual="Actual Sales", label_forecast="Forecast")

            print("\nForecast Details:")
            print(f"{'Date':<12} {'Predicted':>12} {'% Change':>10}")
            last_actual = historical[-1]["actual"] if historical else 0
            for f in forecast:
                pct = ((f["predicted"] - last_actual) / (last_actual or 1)) * 100.0
                print(f"{str(f['date']):<12} {f['predicted']:12.2f} {pct:10.2f}%")

            print("\nRecent Sales (last 14 days):")
            print(f"{'Date':<12} {'Total Sales':>12} {'Trend':>10}")
            recent = historical[-14:] if len(historical) >= 14 else historical
            for i, r in enumerate(recent):
                trend = 0.0
                if i > 0:
                    trend = r["actual"] - recent[i - 1]["actual"]
                print(f"{str(r['date']):<12} {r['actual']:12.2f} {trend:10.2f}")

            if not compact:
                print("\nSide Panel:")
                try:
                    latest = ForecastRun.objects.order_by("-created_at").first() if ForecastRun is not None else None
                    if latest:
                        print(f"Model: {latest.model_name} (last trained: {latest.train_end})")
                    else:
                        print("Model: No persisted model found (using in-memory model for this session).")
                except Exception:
                    print("Model: (unable to read persisted runs)")

                try:
                    from POS.models import SaleItemUnit
                    since = datetime.date.today() - datetime.timedelta(days=7)
                    qs = SaleItemUnit.objects.filter(date__gte=since).values("product_name").annotate(total_qty=pd.NamedAgg("total_quantity", "sum")).order_by("-total_qty")[:5]
                    if qs:
                        print("\nTop Products (7d):")
                        for q in qs:
                            print(f" - {q.get('product_name')}: {q.get('total_qty')}")
                    else:
                        print("\nTop Products (7d): No product summary data.")
                except Exception:
                    print("\nTop Products (7d): (not available)")

            if compact:
                print("Quick: r=Refresh t=Retrain e=Export q=Quit")
            else:
                print("\nQuick Actions: [1] Refresh  [2] Retrain (persisted)  [3] Cleanup persisted runs  [4] Export CSV  [q] Quit")
                print("-" * 80)

        if not interactive:
            if not compact_mode:
                print("Auto mode: running a single simulation with defaults.")
            working_df = generate_dummy_df(days_back=30, base=30, volatility=8)
            historical, forecast = build_and_predict(working_df, horizon_days=horizon, attempt_load_model=True)
            print_dashboard(historical, forecast, horizon, view_mode, smooth, compact=compact_mode)
            return

        created_runs = []
        last_hist = None
        last_fore = None
        while True:
            print_header("Interactive Sales Forecast Simulator", compact=compact_mode)
            if compact_mode:
                print(f"View:{view_mode[:4]} Hor:{horizon} Smooth:{'ON' if smooth else 'OFF'}")
                print(f"Product:{'All' if product_choice is None else getattr(product_choice,'name',str(product_choice))}")
                print("Actions: g=Gen l=Load r=Refresh t=Retrain c=Cleanup e=Export s=ToggleCompact p=Product v=ViewRuns q=Quit")
            else:
                print(f"1) View Mode: {view_mode}   2) Horizon: {horizon}   3) Product: {'All' if product_choice is None else getattr(product_choice,'name',str(product_choice))}")
                print(f"4) Smooth: {'ON' if smooth else 'OFF'}   5) Data Source: {'DB (read-only)' if get_daily_sales_df and working_df is None else 'In-memory dummy' if working_df is not None else 'Not loaded'}")
                print("Actions:")
                print(" [G] Generate in-memory dummy data (fast)")
                print(" [L] Load historical from DB (read-only)")
                print(" [R] Refresh / Run forecast")
                print(" [T] Retrain Model (persisted) -- explicit option")
                print(" [C] Cleanup persisted retrain artifacts (session only)")
                print(" [E] Export current forecast to CSV")
                print(" [S] Toggle Smooth")
                print(" [H] Change Horizon")
                print(" [P] Choose Product (All or specific)")
                print(" [V] View Model Runs")
                print(" [Q] Quit")
            choice = input("Select action: ").strip().lower()

            # keyboard shortcuts mapping
            if choice == "r":
                choice = "1"
            elif choice == "t":
                choice = "2"
            elif choice == "e":
                choice = "4"
            elif choice == "q":
                choice = "q"

            if choice in ("q", "quit"):
                print("Exiting simulation.")
                break

            if choice == "l":
                if get_daily_sales_df is None:
                    print("DB loader not available in this environment.")
                else:
                    days = input("Days back to load (default 30): ").strip()
                    try:
                        days = int(days) if days else 30
                    except Exception:
                        days = 30
                    df = load_historical_from_db(product_id=(product_choice.id if product_choice else None), days=days)
                    if df is None or df.empty:
                        print("No historical DB rows found for the requested range/product.")
                    else:
                        working_df = df
                        print(f"Loaded historical data ({len(df)} rows) into working memory (read-only).")

            elif choice == "g":
                days = input("Generate how many days of dummy history? (default 30): ").strip()
                try:
                    days = int(days) if days else 30
                except Exception:
                    days = 30
                base = input("Base daily sales (default 30): ").strip()
                try:
                    base = float(base) if base else 30.0
                except Exception:
                    base = 30.0
                vol = input("Volatility (stddev, default 8): ").strip()
                try:
                    vol = float(vol) if vol else 8.0
                except Exception:
                    vol = 8.0
                df = generate_dummy_df(days_back=days, base=base, volatility=vol)
                working_df = df
                print(f"Generated {len(df)} days of in-memory dummy data.")

            elif choice == "1":
                if working_df is None:
                    sub = input("No working data loaded. Use DB if available? (y/n) [n]: ").strip().lower()
                    if sub in ("y", "yes") and get_daily_sales_df is not None:
                        working_df = load_historical_from_db(product_id=(product_choice.id if product_choice else None), days=30)
                        if working_df is None:
                            print("No DB data found. Generating dummy instead.")
                            working_df = generate_dummy_df(days_back=30)
                    else:
                        working_df = generate_dummy_df(days_back=30)
                hist, fore = build_and_predict(working_df, horizon_days=horizon, attempt_load_model=True)
                print_dashboard(hist, fore, horizon, view_mode, smooth, compact=compact_mode)
                last_hist = hist
                last_fore = fore

            elif choice == "2":
                print("Persistent retrain will call the project's train_and_persist_default and create ForecastRun/artifact.")
                confirm = input("Proceed with persisted retrain? This will write to DB and files. (y/N): ").strip().lower()
                if confirm in ("y", "yes"):
                    try:
                        days = input("History days for retrain (default 365): ").strip()
                        days = int(days) if days else 365
                    except Exception:
                        days = 365
                    horizon_r = input("Horizon for retrain (default 7): ").strip()
                    try:
                        horizon_r = int(horizon_r) if horizon_r else 7
                    except Exception:
                        horizon_r = 7
                    try:
                        print("Starting persistent retrain (may take time)...")
                        model, run = ml_pipeline.train_and_persist_default(days=days, horizon=horizon_r)
                        created_runs.append({"id": run.id, "artifact": run.artifact_path})
                        print(f"Persistent retrain finished. Created ForecastRun id={run.id} artifact={run.artifact_path}")
                        # inline cleanup confirmation for this session-created run
                        do_cleanup = input("Delete this persisted run now? (y/N): ").strip().lower()
                        if do_cleanup in ("y", "yes"):
                            try:
                                rid = run.id
                                ap = run.artifact_path
                                run.delete()
                                if ap and os.path.exists(ap):
                                    try:
                                        os.remove(ap)
                                    except Exception as e:
                                        print(f"Failed to remove artifact file {ap}: {e}")
                                created_runs = [cr for cr in created_runs if cr.get("id") != rid]
                                print(f"Persisted run {rid} deleted and artifact removed.")
                            except Exception as e:
                                print(f"Failed to cleanup persisted run {run.id}: {e}")
                    except Exception as e:
                        print("Persistent retrain failed:", e)
                else:
                    print("Cancelled persisted retrain.")

            elif choice == "3":
                if not created_runs:
                    print("No session-created persisted runs to clean up.")
                else:
                    print("Session-created persisted runs:")
                    for cr in created_runs:
                        print(f" - id={cr['id']} artifact={cr.get('artifact')}")
                    sub = input("Delete all session-created persisted runs now? (y/N): ").strip().lower()
                    if sub in ("y", "yes"):
                        deleted = 0
                        for cr in list(created_runs):
                            rid = cr.get("id")
                            try:
                                rr = None
                                if ForecastRun is not None:
                                    try:
                                        rr = ForecastRun.objects.filter(id=rid).first()
                                    except Exception:
                                        rr = None
                                ap = cr.get("artifact")
                                if rr:
                                    rr.delete()
                                if ap and os.path.exists(ap):
                                    try:
                                        os.remove(ap)
                                    except Exception as e:
                                        print(f"Failed to remove artifact {ap}: {e}")
                                created_runs.remove(cr)
                                deleted += 1
                            except Exception as e:
                                print(f"Failed to delete run id={rid}: {e}")
                        print(f"Deleted {deleted} session-created persisted run(s).")

            elif choice == "4":
                if last_hist is None or last_fore is None:
                    print("No results available. Run [r] Refresh first.")
                    continue
                dirpath = export_dir or tempfile.gettempdir()
                try:
                    os.makedirs(dirpath, exist_ok=True)
                except Exception as e:
                    print(f"Failed to create export dir {dirpath}: {e}")
                    dirpath = tempfile.gettempdir()
                fname = f"sf_forecast_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                path = os.path.join(dirpath, fname)
                try:
                    with open(path, "w", newline="", encoding="utf-8") as fh:
                        w = csv.writer(fh)
                        w.writerow(["type", "date", "value"])
                        for h in last_hist:
                            w.writerow(["actual", h["date"].isoformat() if hasattr(h["date"], 'isoformat') else str(h["date"]), f"{h['actual']:.2f}"])
                        for f in last_fore:
                            w.writerow(["forecast", f["date"].isoformat() if hasattr(f["date"], 'isoformat') else str(f["date"]), f"{f['predicted']:.2f}"])
                    print(f"Exported CSV to: {path}")
                except Exception as e:
                    print(f"Failed to export CSV: {e}")

            elif choice == "s":
                smooth = not smooth
                print(f"Smooth set to: {'ON' if smooth else 'OFF'}")

            elif choice == "h":
                val = input("Set horizon (days, e.g., 1,3,7,14): ").strip()
                try:
                    horizon = int(val)
                    print(f"Horizon set to {horizon} day(s).")
                except Exception:
                    print("Invalid horizon (must be integer).")

            elif choice == "p":
                if products:
                    print("Products available:")
                    print(" 0) All products")
                    for i, p in enumerate(products, start=1):
                        name = getattr(p, "name", getattr(p, "product_name", str(p)))
                        print(f" {i}) {name} (id={getattr(p,'id',None)})")
                    sel = input("Choose product number (0 for All): ").strip()
                    try:
                        sel = int(sel)
                        if sel == 0:
                            product_choice = None
                        else:
                            product_choice = products[sel - 1]
                        print(f"Product set to: {'All' if product_choice is None else getattr(product_choice,'name',str(product_choice))}")
                    except Exception:
                        print("Invalid selection.")
                else:
                    print("No product records available in Inventory. Using All products.")

            elif choice == "v":
                if ForecastRun is None:
                    print("ForecastRun model not available in this environment.")
                else:
                    try:
                        runs = ForecastRun.objects.order_by("-created_at")[:10]
                        if not runs:
                            print("No persisted ForecastRun records found.")
                        else:
                            print("Recent ForecastRun records:")
                            for r in runs:
                                print(f" - id={r.id} model={r.model_name} trained_on={r.train_end} metrics={r.metrics} artifact={r.artifact_path}")
                    except Exception as e:
                        print("Unable to query ForecastRun:", e)

            else:
                print("Unknown choice. Please select a valid action or use keyboard shortcuts r/t/e/q.")

        print("Simulation ended.")
        if created_runs:
            print("Persisted ForecastRun(s) created during this session:")
            for cr in created_runs:
                print(f" - id={cr['id']} artifact={cr['artifact']}")
        print("Done.")
