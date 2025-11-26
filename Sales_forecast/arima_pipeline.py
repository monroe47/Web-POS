import os
import time
import joblib
import pandas as pd

from django.conf import settings
from statsmodels.tsa.statespace.sarimax import SARIMAX
from pmdarima import auto_arima

from .models import ForecastRun
from Inventory.models import Item
from POS.utils import get_daily_sales_df

# determine models dir in same way as ml_pipeline
BASE_DIR = getattr(settings, 'BASE_DIR', None)
MODELS_DIR = getattr(settings, 'FORECAST_MODELS_DIR', None) or (os.path.join(BASE_DIR, 'forecast_models') if BASE_DIR else './forecast_models')
os.makedirs(MODELS_DIR, exist_ok=True)


def _ensure_series(train_df, date_col='date', qty_col='total_quantity'):
    df = train_df.copy()
    if qty_col in df.columns:
        df = df.rename(columns={qty_col: 'y'})
    df['date'] = pd.to_datetime(df['date'])
    ts = df.set_index('date').asfreq('D', fill_value=0).pop('y').astype(float)
    return ts


def train_sarimax_model(train_df, seasonal_period=7, max_p=3, max_q=3, save_artifact=True, horizon=14, product=None):
    """
    Fit a SARIMAX model on the aggregated daily series in `train_df` and persist it.
    Uses pmdarima.auto_arima to find orders when possible.
    Returns (fitted_model, ForecastRun instance)
    """
    t0 = time.time()
    ts = _ensure_series(train_df)

    # fallback if not enough data
    if len(ts) < max(10, seasonal_period * 2):
        print(f"Not enough history to fit SARIMAX model for product {product.name if product else 'TOTAL'}")
        # Create a dummy run if model can't be trained
        run = ForecastRun.objects.create(
            model_name='statsmodels.SARIMAX (Not Trained)', # Corrected model name for fallback
            train_start=train_df['date'].min() if not train_df.empty else None,
            train_end=train_df['date'].max() if not train_df.empty else None,
            horizon=horizon,
            params={'error': 'Not enough data', 'order': (0,0,0), 'seasonal_order': (0,0,0,seasonal_period) },
            metrics={},
            duration_seconds=time.time() - t0
            # product=product # Removed as ForecastRun does not have a product field
        )
        return None, run # Return None for model if not trained

    # try auto_arima to pick orders; if pmdarima fails we fallback to simple (1,1,1)x(0,1,1,seasonal_period)
    try:
        arima_res = auto_arima(ts, seasonal=True, m=seasonal_period,
                               max_p=max_p, max_q=max_q, max_P=2, max_Q=2,
                               stepwise=True, suppress_warnings=True, error_action='ignore')
        order = arima_res.order
        seasonal_order = arima_res.seasonal_order
    except Exception as e:
        # Fallback to simple orders if auto_arima fails
        print(f"auto_arima failed for product {product.name if product else 'TOTAL'}: {e}. Falling back to default orders.")
        order = (1, 1, 1)
        seasonal_order = (0, 1, 1, seasonal_period)

    model = SARIMAX(ts, order=order, seasonal_order=seasonal_order,
                    enforce_stationarity=False, enforce_invertibility=False)
    fitted = model.fit(disp=False)

    run = ForecastRun.objects.create(
        model_name='statsmodels.SARIMAX', # This will be the name if successfully trained
        train_start=train_df['date'].min(),
        train_end=train_df['date'].max(),
        horizon=horizon,
        params={'order': order, 'seasonal_order': seasonal_order},
        metrics={},
        duration_seconds=time.time() - t0
        # product=product # Removed as ForecastRun does not have a product field
    )

    artifact_path = os.path.join(MODELS_DIR, f'forecast_arima_run_{run.id}.joblib')
    if save_artifact:
        joblib.dump(fitted, artifact_path)
        run.artifact_path = artifact_path
        run.save(update_fields=['artifact_path'])

    return fitted, run


def train_and_persist_default(days=365, horizon=14, product_id=None):
    end = pd.Timestamp.now().date()
    start = end - pd.Timedelta(days=days)
    df = get_daily_sales_df(start_date=start, end_date=end, product_id=product_id)

    product_obj = None
    if product_id:
        try:
            product_obj = Item.objects.get(id=product_id)
        except Item.DoesNotExist:
            product_obj = None
    return train_sarimax_model(df, horizon=horizon, product=product_obj)


def load_arima_model(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return joblib.load(path)
