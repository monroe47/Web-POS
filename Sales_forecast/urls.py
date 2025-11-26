from django.urls import path
from .api import ForecastAPIView, RetrainAPIView, DailySalesDetailsAPIView
from .views import SalesForecastDashboardView, forecast_report_view, export_sales_dashboard_to_excel

app_name = 'sales_forecast'

urlpatterns = [
    path('', SalesForecastDashboardView.as_view(), name='dashboard'),
    path('export_excel/', export_sales_dashboard_to_excel, name='export_sales_dashboard_to_excel'),
    path('forecast_report/', forecast_report_view, name='forecast_report'),

    # API endpoints (app-scoped). The frontend will request these under /sales_forecast/ prefix.
    path('api/forecast/', ForecastAPIView.as_view(), name='api_forecast'),
    path('api/forecast/retrain/', RetrainAPIView.as_view(), name='api_retrain'),
    path('api/daily_sales_details/', DailySalesDetailsAPIView.as_view(), name='api_daily_sales_details'),
]
