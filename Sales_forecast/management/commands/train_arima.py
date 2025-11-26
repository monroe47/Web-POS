from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Train SARIMAX (ARIMA) forecast models. By default trains aggregate series; use --per-product to train per Item.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=365, help='Number of days of history to use')
        parser.add_argument('--horizon', type=int, default=14, help='Forecast horizon to store in ForecastRun')
        parser.add_argument('--per-product', action='store_true', help='Train a separate model per product')
        parser.add_argument('--product-ids', nargs='*', type=int, help='Optional list of product IDs to train (only used with --per-product)')

    def handle(self, *args, **options):
        days = options['days']
        horizon = options['horizon']
        per_product = options['per_product']
        product_ids = options.get('product_ids') or []

        try:
            from Sales_forecast import arima_pipeline
            from POS.utils import get_daily_sales_df
        except Exception as e:
            raise CommandError(f"Failed to import forecasting utilities: {e}")

        end = timezone.now().date()
        start = end - timedelta(days=days)

        if not per_product:
            self.stdout.write(self.style.NOTICE(f"Training aggregate SARIMAX model using last {days} days (horizon={horizon}) ..."))
            try:
                model, run = arima_pipeline.train_and_persist_default(days=days, horizon=horizon)
                self.stdout.write(self.style.SUCCESS(f"Saved aggregate ARIMA model as ForecastRun id={run.id}"))
            except Exception as e:
                raise CommandError(f"ARIMA training failed: {e}")
            return

        # Per-product training
        self.stdout.write(self.style.NOTICE(f"Training per-product SARIMAX models using last {days} days (horizon={horizon}) ..."))
        try:
            from Inventory.models import Item
        except Exception:
            Item = None

        if product_ids and not Item:
            raise CommandError("Inventory.Item model not available to train per-product models.")

        products = []
        if product_ids:
            products = Item.objects.filter(id__in=product_ids)
        else:
            products = Item.objects.all()

        trained = 0
        skipped = 0
        for p in products:
            try:
                df = get_daily_sales_df(start_date=start, end_date=end, product_id=p.id)
                if df.empty or df['total_quantity'].sum() == 0:
                    self.stdout.write(self.style.WARNING(f"Skipping product id={p.id} ({p.name}) — insufficient sales history"))
                    skipped += 1
                    continue
                model, run = arima_pipeline.train_sarimax_model(df, seasonal_period=7, horizon=horizon)
                self.stdout.write(self.style.SUCCESS(f"Trained ARIMA for product id={p.id} -> ForecastRun id={run.id}"))
                trained += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed for product id={p.id}: {e}"))
                continue

        self.stdout.write(self.style.SUCCESS(f"Per-product training complete — trained: {trained}, skipped: {skipped}"))
