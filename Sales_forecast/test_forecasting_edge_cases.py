from django.test import TestCase, Client, override_settings
from django.utils import timezone
from datetime import timedelta, date, datetime, time
from decimal import Decimal
from unittest.mock import patch
import pandas as pd
import numpy as np
import joblib
import os
from django.conf import settings # ADDED: Import settings
from django.contrib.auth import get_user_model # ADDED: Import get_user_model

from Sales_forecast.ml_pipeline import predict_future_sales, make_features, train_xgb_model
from Sales_forecast.arima_pipeline import train_sarimax_model
from Sales_forecast.models import ForecastRun
from Inventory.models import Item
from POS.models import Sale, SaleItem, Transaction, DailySalesRecord

User = get_user_model() # ADDED: Define User

# Ensure settings are configured for tests
@override_settings(
    FORECAST_MODELS_DIR="/tmp/forecast_models_test/",
    MEDIA_ROOT="/tmp/media_test/",
    DEBUG=True
)
class ForecastingEdgeCaseTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.makedirs(settings.FORECAST_MODELS_DIR, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if os.path.exists(settings.FORECAST_MODELS_DIR):
            import shutil
            shutil.rmtree(settings.FORECAST_MODELS_DIR)

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', full_name='Test User', password='password123')
        self.user.is_active = True
        self.user.save()
        self.item1 = Item.objects.create(name='Test Product 1', sku='TP1', price=Decimal('10.00'), stock=100)
        self.item2 = Item.objects.create(name='Test Product 2', sku='TP2', price=Decimal('20.00'), stock=50)

        self.today = timezone.localdate()


    def _create_sales_data(self, num_days, start_date=None, sparse=False, constant_value=None):
        """Helper to create sales data."""
        if start_date is None:
            start_date = self.today - timedelta(days=num_days - 1)

        sales_data = []
        for i in range(num_days):
            current_date = start_date + timedelta(days=i)
            aware_dt = timezone.make_aware(datetime.combine(current_date, time.min))

            if sparse and i % 3 != 0: # Sparse data: only every 3rd day has sales
                continue
            if constant_value is not None: # Constant data for convergence test
                qty = constant_value
            else:
                qty = np.random.randint(10, 50)

            sale = Sale.objects.create(
                subtotal=Decimal(str(qty * self.item1.price)),
                total=Decimal(str(qty * self.item1.price)),
                amount_given=Decimal(str(qty * self.item1.price)),
                change=Decimal('0.00'),
                payment_method='Cash',
                date=aware_dt
            )
            SaleItem.objects.create(sale=sale, product=self.item1, quantity=qty, price=self.item1.price)
            sales_data.append({'date': current_date, 'total_quantity': qty, 'total_revenue': qty * self.item1.price})

        DailySalesRecord.record_daily_sale() # Aggregate records after creating sales
        df = pd.DataFrame(sales_data)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df

    def test_predict_future_sales_insufficient_historical_data(self):
        """Test that prediction handles insufficient historical data gracefully."""
        # Create only a few days of data, less than MIN_HISTORY_FOR_FORECAST (which is 30)
        historical_df = self._create_sales_data(num_days=5)

        class MockModel:
            def predict(self, X): return np.array([0] * len(X))
            def get_forecast(self, steps): return np.array([0] * steps)

        loaded_mock_model = MockModel()

        np.random.seed(42)
        dummy_df_for_training = self._create_sales_data(num_days=50)
        fe_df_training = make_features(dummy_df_for_training)
        fe_df_training.dropna(inplace=True)

        if fe_df_training.empty:
            dummy_model = MockModel()
        else:
            dummy_model, _ = train_xgb_model(dummy_df_for_training)

        recent_df_too_short = self._create_sales_data(num_days=5)
        if not recent_df_too_short.empty:
            forecast_df = predict_future_sales(dummy_model, recent_df_too_short, horizon=7)
            self.assertFalse(forecast_df.empty)
            self.assertEqual(len(forecast_df), 7)
            self.assertFalse(forecast_df["predicted"].isnull().any())
        else:
            forecast_df = predict_future_sales(dummy_model, pd.DataFrame(columns=["date", "total_quantity"]), horizon=7)
            self.assertTrue(forecast_df.empty)


    def test_make_features_handles_sparse_and_zero_values(self):
        """Test make_features function with sparse sales data."""
        sparse_df = pd.DataFrame({
            'date': [self.today - timedelta(days=3), self.today - timedelta(days=2), self.today - timedelta(days=1), self.today],
            'total_quantity': [10, 0, 15, 0],
            'total_revenue': [100.0, 0.0, 150.0, 0.0]
        })
        sparse_df['product_id'] = self.item1.id
        sparse_df['product_name'] = self.item1.name

        df_fe = make_features(sparse_df)

        self.assertFalse(df_fe.isnull().any().any())
        self.assertIn('lag_1', df_fe.columns)
        self.assertIn('roll_mean_3', df_fe.columns)
        self.assertEqual(df_fe['y'].iloc[1], 0)


    def test_arima_convergence_warning_fallback(self):
        """Test that auto_arima handles convergence issues by falling back to default orders."""
        constant_sales_df = self._create_sales_data(num_days=15, constant_value=25)

        with patch('pmdarima.arima.auto_arima') as mock_auto_arima:
            mock_auto_arima.side_effect = Exception("Simulated auto_arima convergence failure")

            model, run = train_sarimax_model(constant_sales_df, product=self.item1, seasonal_period=7, horizon=7)

            self.assertIsNotNone(run)
            self.assertEqual(run.model_name, 'statsmodels.SARIMAX (Not Trained)') # Expected behavior
            self.assertIn('Not enough data', run.params['error'])

            self.assertEqual(run.params['order'], (0,0,0))
            self.assertEqual(run.params['seasonal_order'], (0,0,0,7))


    def test_predict_future_sales_with_few_recent_data_points(self):
        """Test predict_future_sales when provided with data shorter than some lags."""
        long_historical_df = self._create_sales_data(num_days=50)
        trained_model, _ = train_xgb_model(long_historical_df)

        recent_df_short = self._create_sales_data(num_days=2, start_date=self.today - timedelta(days=1))

        forecast_df = predict_future_sales(trained_model, recent_df_short, horizon=5)

        self.assertFalse(forecast_df.empty)
        self.assertEqual(len(forecast_df), 5)
        self.assertFalse(forecast_df["predicted"].isnull().any())
