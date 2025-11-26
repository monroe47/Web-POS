"""
Sales Forecast Demo Mode - Generates mock prediction data
When actual ML model is unavailable, this provides realistic demo forecasts
"""

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random
import math

class ForecastDemoMode:
    """
    ? Generates realistic mock forecast data when ML model is unavailable
    ? Maintains same output format as real predictions
    ? Mimics realistic sales trends
    """

    @staticmethod
    def generate_historical_data(product_id=None, days=30):
        """
        Generate realistic historical sales data for charting
        Mimics actual sales patterns with trends and variance
        """
        today = timezone.now().date()
        data = []
        
        # Base daily sales (realistic values)
        base_sales = random.randint(500, 3000)
        
        for i in range(days, 0, -1):
            date = today - timedelta(days=i)
            
            # Add realistic patterns:
            # - Weekly seasonality (lower sales on certain days)
            weekday = date.weekday()
            weekday_factor = 0.7 if weekday in [0, 6] else 1.0  # Lower on Mon/Sun
            
            # - Slight trend (increasing/decreasing)
            trend_factor = 1.0 + (i / days) * 0.15
            
            # - Random variance
            variance = random.uniform(0.85, 1.15)
            
            # Calculate daily sales
            daily_sales = base_sales * weekday_factor * trend_factor * variance
            daily_sales = Decimal(str(round(daily_sales, 2)))
            
            data.append({
                'date': date.isoformat(),
                'actual': float(daily_sales),
                'predicted': None
            })
        
        return data

    @staticmethod
    def generate_forecast_data(horizon=7, trend_direction='up'):
        """
        Generate realistic forecast predictions
        Creates smooth trend with realistic variance
        """
        today = timezone.now().date()
        forecast = []
        
        # Base predicted sales (similar to recent actuals)
        base_prediction = random.randint(1000, 2500)
        
        for day in range(1, horizon + 1):
            future_date = today + timedelta(days=day)
            
            # Apply trend
            if trend_direction == 'up':
                trend_factor = 1.0 + (day / horizon) * 0.10
            elif trend_direction == 'down':
                trend_factor = 1.0 - (day / horizon) * 0.08
            else:
                trend_factor = 1.0
            
            # Smooth variance (less volatile than actuals)
            variance = random.uniform(0.92, 1.08)
            
            # Weekly pattern
            weekday_factor = 0.75 if future_date.weekday() in [0, 6] else 1.0
            
            predicted_sales = base_prediction * trend_factor * variance * weekday_factor
            predicted_sales = Decimal(str(round(predicted_sales, 2)))
            
            forecast.append({
                'date': future_date.isoformat(),
                'predicted': float(predicted_sales),
                'actual': None
            })
        
        return forecast

    @staticmethod
    def generate_restock_recommendations(products_data=None, horizon=7):
        """
        Generate realistic restock recommendations
        Based on predicted sales patterns
        """
        if not products_data:
            products_data = [
                {'id': 1, 'name': 'Milk', 'sku': 'MLK-001', 'stock': 45, 'avg_daily': 8.5},
                {'id': 2, 'name': 'Bread', 'sku': 'BRD-001', 'stock': 22, 'avg_daily': 5.2},
                {'id': 3, 'name': 'Eggs', 'sku': 'EGG-001', 'stock': 60, 'avg_daily': 12.3},
            ]
        
        recommendations = {}
        today = timezone.now().date()
        
        for i in range(1, horizon + 1):
            forecast_date = (today + timedelta(days=i)).isoformat()
            
            # Find products that might need restocking
            for product in products_data:
                avg_daily = product.get('avg_daily', random.uniform(3, 15))
                current_stock = product.get('stock', 0)
                
                # Calculate if restock needed
                days_until_empty = current_stock / avg_daily if avg_daily > 0 else 999
                
                # Recommend restock if less than 3 days of stock left
                if days_until_empty < 3:
                    suggested_qty = max(int(avg_daily * 7), 10)
                    
                    recommendations[forecast_date] = {
                        'product_id': product['id'],
                        'product_name': product['name'],
                        'sku': product['sku'],
                        'current_stock': current_stock,
                        'avg_daily_sales': round(avg_daily, 2),
                        'suggested_restock': suggested_qty,
                        'urgency': 'high' if days_until_empty < 1.5 else 'medium'
                    }
            
            # Break after first recommendation
            if recommendations:
                break
        
        return recommendations

    @staticmethod
    def generate_model_info():
        """
        Generate realistic model metadata
        Mimics actual trained model information
        """
        return {
            'model_name': 'SARIMAX (Demo Mode)',
            'trained_on': (timezone.now().date() - timedelta(days=2)).isoformat(),
            'status': 'Demo - Realistic Simulation',
            'params': {
                'order': (1, 1, 1),
                'seasonal_order': (0, 1, 1, 7),
                'data_points_used': 365,
            },
            'metrics': {
                'RMSE': round(random.uniform(50, 200), 2),
                'MAE': round(random.uniform(30, 150), 2),
                'MAPE': round(random.uniform(3, 8), 2),
                'accuracy': round(random.uniform(85, 95), 1)
            },
            'last_trained': timezone.now().isoformat(),
        }

    @staticmethod
    def generate_kpi_data(historical_data=None, forecast_data=None):
        """
        Generate realistic KPI metrics
        """
        if not historical_data:
            historical_data = ForecastDemoMode.generate_historical_data()
        
        if not forecast_data:
            forecast_data = ForecastDemoMode.generate_forecast_data()
        
        # Calculate from generated data
        actual_values = [h['actual'] for h in historical_data if h['actual']]
        forecast_values = [f['predicted'] for f in forecast_data if f['predicted']]
        
        if actual_values:
            today_sales = actual_values[-1] if actual_values else 0
        else:
            today_sales = 0
        
        if forecast_values:
            next_day_forecast = forecast_values[0]
        else:
            next_day_forecast = 0
        
        # Calculate 7-day change
        if len(actual_values) >= 7:
            avg_last_7 = sum(actual_values[-7:]) / 7
            avg_forecast = sum(forecast_values[:7]) / len(forecast_values[:7]) if forecast_values else 0
            
            if avg_last_7 > 0:
                change_pct = ((avg_forecast - avg_last_7) / avg_last_7) * 100
            else:
                change_pct = 0
        else:
            change_pct = 0
        
        return {
            'today_sales': float(today_sales),
            'next_day_forecast': float(next_day_forecast),
            'change_percent': round(change_pct, 1),
            'data_quality': 'Demo Data - Realistic Simulation'
        }

    @staticmethod
    def generate_daily_summary(date=None):
        """
        Generate daily sales summary for reporting
        """
        if not date:
            date = timezone.now().date()
        
        summary = {
            'date': date.isoformat(),
            'total_sales': Decimal(str(round(random.uniform(5000, 15000), 2))),
            'items_sold': random.randint(100, 500),
            'transactions': random.randint(20, 100),
            'avg_transaction': Decimal(str(round(random.uniform(100, 500), 2))),
        }
        
        return summary

    @staticmethod
    def generate_monthly_summary(year=None, month=None):
        """
        Generate monthly sales summary
        """
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month
        
        days_in_month = 28 if month == 2 else 30 if month in [4, 6, 9, 11] else 31
        
        monthly_data = []
        for day in range(1, days_in_month + 1):
            daily_sales = Decimal(str(round(random.uniform(5000, 15000), 2)))
            monthly_data.append({
                'date': f'{year:04d}-{month:02d}-{day:02d}',
                'total_sales': float(daily_sales)
            })
        
        return {
            'year': year,
            'month': month,
            'daily_data': monthly_data,
            'total_sales': float(sum(d['total_sales'] for d in monthly_data)),
            'avg_daily': float(sum(d['total_sales'] for d in monthly_data) / len(monthly_data))
        }

    @staticmethod
    def generate_product_forecast(product_name, horizon=7):
        """
        Generate realistic product-specific forecast
        """
        return {
            'product_name': product_name,
            'horizon': horizon,
            'historical': ForecastDemoMode.generate_historical_data(days=30),
            'forecast': ForecastDemoMode.generate_forecast_data(horizon=horizon),
        }

    @staticmethod
    def add_demo_watermark(data):
        """
        Add metadata indicating this is demo data
        """
        data['_demo_mode'] = True
        data['_demo_generated_at'] = timezone.now().isoformat()
        data['_demo_note'] = 'This is simulated forecast data for demonstration purposes'
        return data
