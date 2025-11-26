import os
import django
from datetime import date

import sys
# ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'POSwithSalesForecast.settings')
django.setup()

from Sales_forecast.models import ForecastRun
from Sales_forecast.arima_pipeline import load_arima_model
from Sales_forecast.ml_pipeline import predict_future_sales
from POS.utils import get_daily_sales_df

# find latest ARIMA run
run = ForecastRun.objects.filter(model_name__icontains='arima').order_by('-created_at').first()
if not run:
    print('No ARIMA ForecastRun found')
    raise SystemExit(1)

print('Using ForecastRun id=', run.id, 'artifact=', run.artifact_path)
model = load_arima_model(run.artifact_path)

# build recent_df (last 90 days)
end = date.today()
start = end - django.utils.timezone.timedelta(days=90)
recent_df = get_daily_sales_df(start_date=start, end_date=end)

if recent_df.empty:
    print('No recent sales data found to test forecast')
    raise SystemExit(1)

print('Recent data rows:', len(recent_df))

pred_df = predict_future_sales(model, recent_df, horizon=14)
print(pred_df.to_string(index=False))
