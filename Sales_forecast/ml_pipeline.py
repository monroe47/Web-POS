import os
import time
from datetime import timedelta
import joblib
import pandas as pd
import numpy as np

from django.conf import settings
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from POS.utils import get_daily_sales_df
from .models import ForecastRun, ForecastResult
from Inventory.models import Item

# Opt-in to pandas future behavior for downcasting to avoid noisy FutureWarning
pd.set_option('future.no_silent_downcasting', True)

BASE_DIR = getattr(settings, 'BASE_DIR', None)
MODELS_DIR = getattr(settings, 'FORECAST_MODELS_DIR', None) or (os.path.join(BASE_DIR, 'forecast_models') if BASE_DIR else './forecast_models')
os.makedirs(MODELS_DIR, exist_ok=True)


# ---------------- Feature engineering ----------------
def make_features(df, lags=(1, 7, 14), rolling_windows=(3, 7, 30)):
    """
    df: DataFrame with at least ['date','total_quantity'].
    Returns DataFrame with engineered features and 'y' as target.
    """
    df = df.copy()
    # Normalize column names expected by pipeline
    if 'total_quantity' in df.columns:
        df = df.rename(columns={'total_quantity': 'y'})
    # ensure date is datetime
    df['date'] = pd.to_datetime(df['date'])
    # set daily frequency, fill missing days with 0 target
    df = df.set_index('date').asfreq('D', fill_value=0).reset_index()

    # calendar features
    df['dow'] = df['date'].dt.dayofweek
    df['month'] = df['date'].dt.month
    df['day'] = df['date'].dt.day

    # lags
    for lag in lags:
        df[f'lag_{lag}'] = df['y'].shift(lag)

    # rolling means (use shifted series so current day not included)
    for w in rolling_windows:
        df[f'roll_mean_{w}'] = df['y'].shift(1).rolling(window=w, min_periods=1).mean()

    # keep product columns if present (they will be excluded from numeric feature set)
    if 'product_id' not in df.columns:
        df['product_id'] = None
    if 'product_name' not in df.columns:
        df['product_name'] = 'TOTAL'

    # Infer more specific dtypes first, then fill NA. This avoids pandas emitting the
    # "downcasting object dtype arrays on .fillna ... is deprecated" warning because
    # infer_objects will convert object columns to their proper numeric types before fillna.
    df = df.infer_objects(copy=False)
    df = df.fillna(0)

    # Ensure target is numeric
    df['y'] = pd.to_numeric(df['y'], errors='coerce').fillna(0).astype(float)

    return df


def _build_feature_matrix(df_fe):
    """
    Build numeric-only feature matrix for training/prediction.

    Important: only include intended predictive features (lag_*, roll_mean_*, dow, month, day).
    This prevents accidental inclusion of columns such as total_revenue or product_name that may
    exist in training but not be available for recursive prediction.
    """
    allowed = [c for c in df_fe.columns if c.startswith('lag_') or c.startswith('roll_mean_') or c in ('dow', 'month', 'day')]
    X = df_fe[allowed].apply(pd.to_numeric, errors='coerce').fillna(0).astype(float) if allowed else pd.DataFrame()
    return X, allowed


def make_supervised(df):
    """
    Returns X (DataFrame numeric), y (Series float), df_fe (feature-engineered DataFrame).
    """
    df_fe = make_features(df)
    X, feature_cols = _build_feature_matrix(df_fe)
    y = df_fe['y'].astype(float)
    return X, y, df_fe


# ---------------- Training ----------------
def train_xgb_model(train_df, horizon=7, params=None, save_artifact=True, product=None):
    """
    Trains an XGBRegressor on the supplied train_df (pandas DataFrame).
    Returns (model, ForecastRun instance).
    """
    t0 = time.time()
    if params is None:
        params = dict(
            objective='reg:squarederror',
            n_estimators=300,
            learning_rate=0.1,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )

    X, y, df_fe = make_supervised(train_df)

    # If for some reason no allowed features were present, create fallback from lags/rolls that exist.
    if X.shape[1] == 0:
        fallback_cols = [c for c in df_fe.columns if c.startswith('lag_') or c.startswith('roll_mean_') or c in ('dow', 'month', 'day')]
        X = df_fe[fallback_cols].apply(pd.to_numeric, errors='coerce').fillna(0).astype(float)

    # simple chronological split for validation
    split = int(len(X) * 0.8) if len(X) > 10 else max(1, len(X) - 1)
    X_train, X_val = X.iloc[:split], X.iloc[split:]
    y_train, y_val = y.iloc[:split], y.iloc[split:]

    model = XGBRegressor(**params)
    # Fit model (XGBoost expects numeric-only DataFrames)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    preds = model.predict(X_val) if len(X_val) else np.array([])
    mae = float(mean_absolute_error(y_val, preds)) if len(X_val) else None
    # Compute RMSE explicitly (avoid sklearn version differences)
    rmse = float(np.sqrt(mean_squared_error(y_val, preds))) if len(X_val) else None

    run = ForecastRun.objects.create(
        model_name='xgb.XGBRegressor',
        train_start=train_df['date'].min(),
        train_end=train_df['date'].max(),
        horizon=horizon,
        params=params,
        metrics={'mae': mae, 'rmse': rmse},
        duration_seconds=time.time() - t0
    )

    artifact_path = os.path.join(MODELS_DIR, f'forecast_xgb_run_{run.id}.joblib')
    if save_artifact:
        joblib.dump(model, artifact_path)
        run.artifact_path = artifact_path
        run.save(update_fields=['artifact_path'])

    return model, run


# ---------------- Persistence & loading ----------------
def load_model(path=None):
    """
    Load the latest model artifact if path not provided.
    """
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        return joblib.load(path)

    latest = ForecastRun.objects.order_by('-created_at').first()
    if not latest or not latest.artifact_path:
        raise FileNotFoundError("No saved forecast model found.")
    return joblib.load(latest.artifact_path)


# ---------------- Prediction (recursive) ----------------
def predict_future_sales(model, recent_df, horizon=7):
    """
    recent_df: DataFrame with columns ['date','total_quantity'] up to last known date.
    Performs recursive multi-step forecasting using the model.
    Returns DataFrame with columns ['date','predicted'].
    """
    df = recent_df.copy()
    # normalize and ensure date/dtype
    if 'total_quantity' in df.columns:
        df = df.rename(columns={'total_quantity': 'y'})
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').asfreq('D', fill_value=0).reset_index()
    df['y'] = pd.to_numeric(df['y'], errors='coerce').fillna(0).astype(float)

    # If model is a statsmodels SARIMAXResults-like object, use its forecasting API
    try:
        # statsmodels results have get_forecast method
        if hasattr(model, 'get_forecast'):
            forecast = model.get_forecast(steps=horizon)
            mean = forecast.predicted_mean
            # Convert to array if needed
            if hasattr(mean, 'values'):
                mean_vals = mean.values
            else:
                mean_vals = np.array(mean)
            
            start_date = df['date'].max() + pd.Timedelta(days=1)
            idx = pd.date_range(start=start_date, periods=horizon, freq='D')
            return pd.DataFrame({'date': idx.date, 'predicted': mean_vals})
    except Exception:
        # fall through to recursive XGBoost-style predictor below
        pass

    # Default: assume scikit-learn-like regressor (e.g., XGBoost)
    preds = []
    for step in range(horizon):
        fe = make_features(df[['date', 'y']])
        X_row, _ = _build_feature_matrix(fe)
        if X_row.shape[0] == 0:
            raise RuntimeError("No feature columns available for prediction.")
        last = X_row.iloc[[-1]]
        pred = float(model.predict(last)[0])
        next_date = df['date'].max() + timedelta(days=1)
        preds.append({'date': next_date.date(), 'predicted': pred})
        # append predicted for next iteration using pd.concat (append removed in pandas)
        new_row = pd.DataFrame({'date': [next_date], 'y': [pred]})
        df = pd.concat([df, new_row], ignore_index=True)
    return pd.DataFrame(preds)


# ---------------- Convenience helpers ----------------
def train_and_persist_default(days=365, horizon=7, params=None, product_id=None):
    """
    Helper to load POS data for last `days`, train and persist model.
    Prefers ARIMA training by default if available; falls back to XGBoost.
    """
    end = pd.Timestamp.now().date()
    start = end - pd.Timedelta(days=days)
    # Get data for a specific product or total sales
    df = get_daily_sales_df(start_date=start, end_date=end, product_id=product_id)
    
    # Prefer ARIMA training by default if available; fall back to XGBoost
    try:
        # import locally to avoid hard dependency at module import time
        from . import arima_pipeline
        return arima_pipeline.train_and_persist_default(days=days, horizon=horizon, product_id=product_id)
    except Exception as e:
        # If ARIMA pipeline unavailable or fails, fall back to existing XGBoost pipeline
        product_obj = None
        if product_id:
            try:
                product_obj = Item.objects.get(id=product_id)
            except Item.DoesNotExist:
                product_obj = None
        return train_xgb_model(df, horizon=horizon, params=params, product=product_obj)

# New function to train models for all products
def train_all_product_models(days=365, horizon=7, params=None):
    """
    Trains and persists XGBoost models for all individual products.
    Also trains a model for overall total sales.
    """
    print("--- Training models for all products ---")
    # First, train a model for overall total sales
    print("Training model for TOTAL sales...")
    train_and_persist_default(days=days, horizon=horizon, params=params, product_id=None)
    print("Done training model for TOTAL sales.")

    # Get all products from the Inventory app
    products = Item.objects.all()
    if not products:
        print("No products found in Inventory to train individual models.")
        return

    for product in products:
        print(f"Training model for product: {product.name} (ID: {product.id})...")
        train_and_persist_default(days=days, horizon=horizon, params=params, product_id=product.id)
        print(f"Done training model for {product.name}.")
    print("--- Finished training models for all products ---")
