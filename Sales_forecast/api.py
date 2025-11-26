from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework import status
from django.utils.dateparse import parse_date
from django.db.models import Avg
import pandas as pd
import datetime

from .ml_pipeline import load_model, predict_future_sales, train_and_persist_default
from django.conf import settings
from .demo_mode import ForecastDemoMode  # Demo utilities (kept for explicit demo testing only)
from POS.utils import get_daily_sales_df
from django.utils import timezone

# Minimum historical points required before showing model forecast
MIN_HISTORY_FOR_FORECAST = 30
from .serializers import ForecastResponseSerializer

class ForecastAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        horizon = int(request.query_params.get('horizon', 7))
        product_id = request.query_params.get('product_id')
        start = request.query_params.get('start')
        end = request.query_params.get('end')
        # Allow forcing prediction during testing: ?force=1
        force = str(request.query_params.get('force', '')).lower() in ('1', 'true', 'yes')
        # Demo mode is disabled by default. Enable only via Django setting
        demo_mode = getattr(settings, 'SALES_FORECAST_ENABLE_DEMO', False)

        if product_id:
            try:
                product_id = int(product_id)
            except ValueError:
                return Response({'error': 'product_id must be integer'}, status=status.HTTP_400_BAD_REQUEST)

        df = get_daily_sales_df(start_date=parse_date(start) if start else None,
                                end_date=parse_date(end) if end else None,
                                product_id=product_id)

        # If get_daily_sales_df returned no data, try to fall back to DailySalesRecord
        # which stores aggregated daily total_sales. This ensures the dashboard shows
        # historical daily totals even if SaleItemUnit rows are absent.
        if (df is None or df.empty):
            try:
                from POS.models import DailySalesRecord
                end_date = parse_date(end) if end else timezone.now().date()
                start_date = parse_date(start) if start else (end_date - datetime.timedelta(days=365))
                qs = DailySalesRecord.objects.filter(date__gte=start_date, date__lte=end_date).order_by('date')
                rows = list(qs.values('date', 'total_sales'))
                if rows:
                    # prefer total_revenue naming (monetary) so the dashboard shows money totals
                    df = pd.DataFrame([{'date': r['date'], 'total_revenue': r['total_sales']} for r in rows])
            except Exception:
                # If anything goes wrong, keep df as empty DataFrame
                df = df if df is not None else pd.DataFrame()

        # ✅ NEW: Try actual model first
        model = None
        try:
            model = load_model()
        except Exception as e:
            model = None
            print(f"Model loading error: {str(e)}")

        # If model failed, try to train automatically when sufficient historical data exists
        if not model and not demo_mode:
            try:
                hist_len = 0
                if df is not None and hasattr(df, 'shape'):
                    hist_len = len(df)
                # Auto-train when we have enough history or if force was requested
                if hist_len >= MIN_HISTORY_FOR_FORECAST or force:
                    model, run = train_and_persist_default(days=365, horizon=horizon)
                    print(f"Model trained: {run.id}")
            except Exception as train_err:
                print(f"Model training error: {str(train_err)}")
                model = None

        # If demo mode explicitly enabled via settings, return demo data
        if demo_mode and (not model):
            print("[DEMO MODE] Using realistic mock forecast data (settings enabled)")
            return self._generate_demo_response(horizon, demo_mode=demo_mode)

        # Ensure historical dates are plain dates (not datetimes / timestamps) to satisfy DRF DateField
        if not df.empty:
            df = df.copy()
            df['date'] = pd.to_datetime(df['date']).dt.date
            # prefer monetary total_revenue when available, otherwise fall back to total_quantity
            val_col = 'total_revenue' if 'total_revenue' in df.columns else 'total_quantity'
            historical = df.tail(30)[['date', val_col]].rename(columns={val_col: 'actual'}).to_dict(orient='records')
        else:
            historical = []

        # Prepare recent window for prediction (must include enough lags)
        recent = df.copy() if (df is not None and not df.empty) else pd.DataFrame([
            {
                'date': (datetime.date.today() - datetime.timedelta(days=1)),
                'total_quantity': 0
            }
        ])
        # If recent['date'] are date objects make them datetimes for predict logic
        recent['date'] = pd.to_datetime(recent['date'])
        # Ensure we have total_quantity column (predict_future_sales expects it)
        if 'total_quantity' not in recent.columns:
            val_col = 'total_revenue' if 'total_revenue' in recent.columns else 'actual'
            if val_col in recent.columns:
                recent['total_quantity'] = recent[val_col]

        forecast_records = []
        # Only attempt prediction if we have a loaded model and sufficient historical points
        try:
            allow_predict = model is not None and ( (df is not None and len(df) >= MIN_HISTORY_FOR_FORECAST) or force )
            if allow_predict:
                try:
                    forecast_df = predict_future_sales(model, recent, horizon=horizon)
                    # forecast_df.date should already be date objects; normalize to ISO date string or date
                    for r in forecast_df.to_dict(orient='records'):
                        d = r.get('date')
                        # ensure it's a date (not datetime)
                        if isinstance(d, (pd.Timestamp, datetime.datetime)):
                            d = pd.to_datetime(d).date()
                        elif isinstance(d, str):
                            try:
                                d = parse_date(d)
                            except Exception:
                                pass
                        forecast_records.append({'date': d, 'predicted': r.get('predicted'), 'actual': None})
                except Exception as e:
                    # If prediction fails for any reason, return empty forecast (UI will show historical only)
                    print(f"Prediction error: {str(e)}")
                    forecast_records = []
        except Exception as e:
            print(f"Forecast error: {str(e)}")
            forecast_records = []
        
        # ✅ Add product restock recommendations based on predicted sales
        restock_recommendations = {}
        try:
            from Inventory.models import Item
            from POS.models import SaleItemUnit
            
            # Get all products with their current stock
            products = Item.objects.all().values('id', 'name', 'sku', 'stock')
            
            # Get recent product sales (last 7 days) to identify top-selling products
            week_ago = timezone.now().date() - datetime.timedelta(days=7)
            recent_product_sales = (
                SaleItemUnit.objects.filter(date__gte=week_ago)
                .values('product_id', 'product_name')
                .annotate(avg_daily=Avg('total_quantity'))
                .order_by('-avg_daily')
            )
            
            # Create a dict of product sales patterns
            product_sales_patterns = {r['product_id']: {
                'name': r['product_name'],
                'avg_daily': float(r['avg_daily'] or 0),
            } for r in recent_product_sales if r['product_id']}
            
            # For each forecast date, recommend which products to restock
            for forecast_record in forecast_records:
                forecast_date = forecast_record['date']
                predicted_sales = float(forecast_record['predicted'] or 0)
                
                restock_list = []
                
                # If predicted sales are positive, recommend best-selling products with low stock
                if predicted_sales > 0 and product_sales_patterns:
                    # Check all products
                    for product in products:
                        product_id = product['id']
                        if product_id in product_sales_patterns:
                            pattern = product_sales_patterns[product_id]
                            avg_daily = pattern['avg_daily']
                            current_stock = product['stock']
                            
                            # Recommend restock if:
                            # 1. Product is frequently sold (avg_daily > 0)
                            # 2. Current stock is low (less than 2 days of average sales)
                            if avg_daily > 0 and current_stock < (avg_daily * 2):
                                restock_list.append({
                                    'product_id': product_id,
                                    'product_name': product['name'],
                                    'sku': product['sku'],
                                    'current_stock': current_stock,
                                    'avg_daily_sales': round(avg_daily, 2),
                                    'suggested_restock': max(int(avg_daily * 7), 10)
                                })
                    
                    # Sort by current_stock (lowest first - restock urgent items first)
                    restock_list.sort(key=lambda x: x['current_stock'])
                    
                    # Take top 1 recommendation for this date (just product name)
                    if restock_list:
                        restock_recommendations[str(forecast_date)] = restock_list[0]
        except Exception as e:
            print(f"Restock recommendation error: {str(e)}")
            restock_recommendations = {}

        # Format historical entries as dicts with date as date object (already set above)
        hist_serial = []
        for r in historical:
            d = r.get('date')
            if isinstance(d, (pd.Timestamp, datetime.datetime)):
                d = pd.to_datetime(d).date()
            hist_serial.append({'date': d, 'actual': r.get('actual'), 'predicted': None})

        # If still no trained model available, return historical-only response (no demo fallback)
        if not model:
            print("[FALLBACK] No model available after auto-train attempt; returning historical-only response")
            payload = {
                'view': 'daily',
                'horizon': horizon,
                'historical': hist_serial,
                'forecast': [],
                'restock_recommendations': {},
                'meta': {'model': None, 'forced': bool(force)}
            }
            serializer = ForecastResponseSerializer(payload)
            return Response(serializer.data)

        payload = {
            'view': 'daily',
            'horizon': horizon,
            'historical': hist_serial,
            'forecast': forecast_records,
            'restock_recommendations': restock_recommendations,
            'meta': {'model': 'statsmodels.SARIMAX', 'forced': bool(force)}
        }
        serializer = ForecastResponseSerializer(payload)
        return Response(serializer.data)

    def _generate_demo_response(self, horizon, demo_mode=False):
        """
        ✅ Generate realistic demo forecast response
        Mimics actual API response format
        """
        # Generate mock data
        historical_data = ForecastDemoMode.generate_historical_data(days=30)
        forecast_data = ForecastDemoMode.generate_forecast_data(horizon=horizon)
        restock_recs = ForecastDemoMode.generate_restock_recommendations()

        # Format for serializer
        hist_serial = [
            {'date': d['date'], 'actual': d['actual'], 'predicted': None}
            for d in historical_data
        ]

        forecast_serial = [
            {'date': d['date'], 'predicted': d['predicted'], 'actual': None}
            for d in forecast_data
        ]

        payload = {
            'view': 'daily',
            'horizon': horizon,
            'historical': hist_serial,
            'forecast': forecast_serial,
            'restock_recommendations': restock_recs,
            'meta': {
                'model': 'SARIMAX (Demo/Fallback Mode)',
                'status': 'Demo forecast - realistic simulation',
                'demo_mode': demo_mode,
                'note': 'This is simulated data for demonstration purposes'
            }
        }

        serializer = ForecastResponseSerializer(payload)
        return Response(serializer.data)




class RetrainAPIView(APIView):
    """
    Admin-only endpoint to retrain using default settings (last 365 days).
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        days = int(request.data.get('days', 365))
        horizon = int(request.data.get('horizon', 7))
        try:
            model, run = train_and_persist_default(days=days, horizon=horizon)
            return Response({'status': 'ok', 'run_id': run.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'status': 'error', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DailySalesDetailsAPIView(APIView):
    """
    ✅ NEW: Get detailed sales breakdown for a specific date.
    Returns all products sold that day with quantities, prices, and totals.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        date_str = request.query_params.get('date')
        
        if not date_str:
            return Response({'error': 'date parameter required (format: YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            sale_date = parse_date(date_str)
            if not sale_date:
                return Response({'error': 'Invalid date format (use YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Date parse error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from POS.models import SaleItem, Sale
            from datetime import timedelta
            
            # Get all sales for the day (between start and end of day)
            day_start = datetime.datetime.combine(sale_date, datetime.time.min)
            day_end = datetime.datetime.combine(sale_date, datetime.time.max)
            
            # Get all sale items for this date
            sale_items = SaleItem.objects.filter(
                sale__date__gte=day_start,
                sale__date__lte=day_end
            ).select_related('product').order_by('sale__date')
            
            # Group by product
            products_dict = {}
            for item in sale_items:
                product_name = item.product.name if item.product else item.product_name
                product_id = item.product.id if item.product else None
                unit_price = float(item.price)
                quantity = item.quantity
                
                if product_name not in products_dict:
                    products_dict[product_name] = {
                        'product_id': product_id,
                        'product_name': product_name,
                        'unit_price': unit_price,
                        'quantity': 0,
                        'total_amount': 0.0
                    }
                
                products_dict[product_name]['quantity'] += quantity
                products_dict[product_name]['total_amount'] += float(item.line_total)
            
            # Get grand total from DailySalesRecord
            from POS.models import DailySalesRecord
            daily_record = DailySalesRecord.objects.filter(date=sale_date).first()
            grand_total = float(daily_record.total_sales) if daily_record else sum(p['total_amount'] for p in products_dict.values())
            
            # Format response
            products_list = list(products_dict.values())
            
            return Response({
                'date': sale_date.isoformat(),
                'products': products_list,
                'total_products': len(products_list),
                'total_items_sold': sum(p['quantity'] for p in products_list),
                'grand_total': grand_total,
                'formatted_date': sale_date.strftime('%B %d, %Y')
            })
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Error fetching sales details: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)