# Sales_forecast/tests.py
"""
Django test suite for Sales_forecast app.

Contains:
- tests for POS.utils.get_daily_sales_df aggregation
- tests for ml_pipeline training, artifact creation and prediction
- API endpoint tests for ForecastAPIView and RetrainAPIView

Run with:
    python manage.py test Sales_forecast
"""
import os
import tempfile
from datetime import timedelta

import pandas as pd
from django.test import TestCase, override_settings, Client
from django.utils import timezone

from POS.models import SaleItemUnit
from POS.utils import get_daily_sales_df
from Sales_forecast.ml_pipeline import (
    train_xgb_model,
    load_model,
    predict_future_sales,
    train_and_persist_default,
)
from Sales_forecast.models import ForecastRun


class UtilsTests(TestCase):
    def test_get_daily_sales_df_aggregates_multiple_products(self):
        today = timezone.now().date()
        SaleItemUnit.objects.all().delete()

        SaleItemUnit.objects.create(
            product_name="Product A", product_id=1, total_quantity=5, total_revenue=500, date=today
        )
        SaleItemUnit.objects.create(
            product_name="Product B", product_id=2, total_quantity=3, total_revenue=300, date=today
        )
        SaleItemUnit.objects.create(
            product_name="Product A", product_id=1, total_quantity=2, total_revenue=200, date=today - timedelta(days=1)
        )

        df = get_daily_sales_df(start_date=today - timedelta(days=1), end_date=today)
        self.assertEqual(len(df), 2)
        today_row = df[df['date'] == pd.to_datetime(today)]
        self.assertTrue(not today_row.empty)
        self.assertEqual(int(today_row['total_quantity'].iloc[0]), 8)
        self.assertEqual(float(today_row['total_revenue'].iloc[0]), 800.0)

    def test_get_daily_sales_df_product_filter(self):
        today = timezone.now().date()
        SaleItemUnit.objects.all().delete()

        SaleItemUnit.objects.create(
            product_name="Product A", product_id=1, total_quantity=4, total_revenue=400, date=today
        )
        SaleItemUnit.objects.create(
            product_name="Product B", product_id=2, total_quantity=6, total_revenue=600, date=today
        )

        df_a = get_daily_sales_df(start_date=today, end_date=today, product_id=1)
        self.assertEqual(len(df_a), 1)
        self.assertEqual(int(df_a.iloc[0]['total_quantity']), 4)
        self.assertEqual(float(df_a.iloc[0]['total_revenue']), 400.0)


class MLPipelineTests(TestCase):
    def setUp(self):
        SaleItemUnit.objects.all().delete()
        self.today = timezone.now().date()
        start = self.today - timedelta(days=89)
        for i in range(90):
            d = start + timedelta(days=i)
            qty = 50 + (i % 7) * 3
            revenue = float(qty * 20.0)
            SaleItemUnit.objects.create(
                product_name="TOTAL", product_id=None, total_quantity=qty, total_revenue=revenue, date=d
            )

        self.test_params = {
            "objective": "reg:squarederror",
            "n_estimators": 8,
            "learning_rate": 0.2,
            "max_depth": 3,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }
        self.tmpdir = tempfile.mkdtemp(prefix="forecast_test_")

    @override_settings(FORECAST_MODELS_DIR=None)
    def test_train_xgb_model_creates_run_and_artifact(self):
        df = get_daily_sales_df(start_date=self.today - timedelta(days=89), end_date=self.today)
        from django.conf import settings
        settings.FORECAST_MODELS_DIR = self.tmpdir

        model, run = train_xgb_model(df, horizon=7, params=self.test_params, save_artifact=True)

        self.assertIsInstance(run, ForecastRun)
        self.assertTrue(os.path.exists(run.artifact_path))
        loaded = load_model(run.artifact_path)
        self.assertIsNotNone(loaded)
        recent_df = df.tail(14).rename(columns={"total_quantity": "total_quantity"})
        preds = predict_future_sales(loaded, recent_df, horizon=5)
        self.assertEqual(len(preds), 5)
        for r in preds.to_dict(orient="records"):
            self.assertIn("date", r)
            self.assertIn("predicted", r)

    @override_settings(FORECAST_MODELS_DIR=None)
    def test_train_and_persist_default_helper(self):
        from django.conf import settings
        settings.FORECAST_MODELS_DIR = self.tmpdir

        model, run = train_and_persist_default(days=90, horizon=7)
        self.assertIsInstance(run, ForecastRun)
        self.assertTrue(os.path.exists(run.artifact_path))


class APITests(TestCase):
    def setUp(self):
        SaleItemUnit.objects.all().delete()
        self.today = timezone.now().date()
        start = self.today - timedelta(days=29)
        for i in range(30):
            d = start + timedelta(days=i)
            qty = 40 + (i % 5) * 2
            revenue = float(qty * 25.0)
            SaleItemUnit.objects.create(
                product_name="TOTAL", product_id=None, total_quantity=qty, total_revenue=revenue, date=d
            )

        self.client = Client()
        User = __import__('django.contrib.auth').contrib.auth.get_user_model() if False else __import__('django.contrib.auth').contrib.auth.get_user_model()  # fallback, but will be overridden below
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            # try common signatures for create_superuser
            self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass1234")
        except TypeError:
            try:
                self.admin = User.objects.create_superuser("admin", password="pass1234")
            except TypeError:
                self.admin = User.objects.create_user(username="admin", password="pass1234")
                self.admin.is_staff = True
                self.admin.is_superuser = True
                self.admin.save()

        self.tmpdir = tempfile.mkdtemp(prefix="forecast_test_")
        from django.conf import settings
        settings.FORECAST_MODELS_DIR = self.tmpdir
        df = get_daily_sales_df(start_date=self.today - timedelta(days=29), end_date=self.today)
        train_xgb_model(df, horizon=7, params={"n_estimators": 6, "learning_rate": 0.2, "random_state": 1})

    def test_forecast_api_get(self):
        """
        Use explicit path to avoid URL reversing issues in different projects.
        """
        resp = self.client.get("/sales_forecast/api/forecast/", {"horizon": 5})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("historical", data)
        self.assertIn("forecast", data)
        self.assertIsInstance(data["historical"], list)
        self.assertIsInstance(data["forecast"], list)
        self.assertLessEqual(len(data["forecast"]), 5)

    def test_retrain_api_requires_admin_and_creates_run(self):
        url = "/sales_forecast/api/forecast/retrain/"
        resp = self.client.post(url, {"days": 30, "horizon": 7}, content_type="application/json")
        self.assertIn(resp.status_code, (302, 403, 401))

        self.client.force_login(self.admin)
        resp2 = self.client.post(url, '{"days":30, "horizon":5}', content_type="application/json")
        self.assertIn(resp2.status_code, (200, 201))
        try:
            payload = resp2.json()
            if isinstance(payload, dict):
                self.assertIn("run_id", payload)
        except ValueError:
            pass