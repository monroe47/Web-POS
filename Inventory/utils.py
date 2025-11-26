
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from django.db.models.functions import TruncDay

# Attempt to import SaleItemUnit defensively
try:
    from POS.models import SaleItemUnit
except ImportError:
    SaleItemUnit = None

def get_dynamic_min_stock_level(item, sales_period_days=30, safety_multiplier=1.5):
    """
    Calculates a dynamic minimum stock level for an item based on its recent sales data.

    Args:
        item: The Inventory.Item object for which to calculate the threshold.
        sales_period_days: The number of recent days to consider for sales data.
        safety_multiplier: Multiplier for average daily sales to determine safety stock.

    Returns:
        An integer representing the dynamic minimum stock level.
    """
    if SaleItemUnit is None:
        # Fallback if SaleItemUnit cannot be imported
        return item.min_stock_level if hasattr(item, 'min_stock_level') else 10

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=sales_period_days)

    # Aggregate sales data for the item over the period
    sales_data = SaleItemUnit.objects.filter(
        product_id=item.id,
        date__gte=start_date,
        date__lte=end_date
    ).values('date').annotate(total_sold=Sum('total_quantity'))

    if not sales_data:
        # No sales data found for the period, return the item's fixed min_stock_level or a default
        return item.min_stock_level if hasattr(item, 'min_stock_level') else 10

    total_quantity_sold = sum(entry['total_sold'] for entry in sales_data)
    
    # Calculate the number of actual sales days, not just the period length
    # This prevents underestimating average daily sales if sales are sparse
    num_sales_days = len(set(entry['date'] for entry in sales_data))
    if num_sales_days == 0:
        average_daily_sales = 0
    else:
        average_daily_sales = total_quantity_sold / num_sales_days

    # Calculate dynamic threshold, ensuring it's at least 1 if sales occurred
    dynamic_threshold = int(average_daily_sales * safety_multiplier)
    
    return max(1, dynamic_threshold) if total_quantity_sold > 0 else (item.min_stock_level if hasattr(item, 'min_stock_level') else 10)
