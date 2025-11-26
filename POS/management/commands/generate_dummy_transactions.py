from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, time as dtime
import random
from decimal import Decimal

# Safe imports
try:
    from POS.models import Sale, SaleItem
except Exception:
    Sale = None
    SaleItem = None

try:
    from Inventory.models import Item
except Exception:
    Item = None

SAMPLE_NAMES = [
    "SkyGlow 1L", "MaxGlow 1L", "Dishwash Pro 1L", "SparkClean 500ml",
    "HandWash 250ml", "FloorClean 2L"
]

class Command(BaseCommand):
    help = 'Generate random dummy transactions for the past N days (for testing/demo)'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Number of past days to generate (default: 30)')
        parser.add_argument('--max-sales-per-day', type=int, default=6, help='Max number of sales per day (default:6)')
        parser.add_argument('--max-items-per-sale', type=int, default=4, help='Max distinct items per sale (default:4)')

    def handle(self, *args, **options):
        if Sale is None or SaleItem is None:
            self.stderr.write('Sale or SaleItem model not found. Aborting.')
            return

        days = options['days']
        max_sales = options['max_sales_per_day']
        max_items = options['max_items_per_sale']

        tz = timezone.get_current_timezone()
        today = timezone.now().date()

        all_items = list(Item.objects.all()) if Item is not None else []

        created = 0
        for day_offset in range(days):
            day_date = today - timedelta(days=(days - 1 - day_offset))
            # random number of sales this day
            sales_count = random.randint(1, max(1, max_sales))
            for s in range(sales_count):
                # random time during the day
                hour = random.randint(8, 20)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                dt = datetime.combine(day_date, dtime(hour, minute, second))
                aware_dt = timezone.make_aware(dt, timezone=tz)

                sale = Sale(date=aware_dt)
                # initial save to get id
                sale.save()

                # choose number of items
                items_n = random.randint(1, max(1, max_items))
                chosen = []
                for i in range(items_n):
                    if all_items:
                        product = random.choice(all_items)
                        price = Decimal(product.price)
                        pname = getattr(product, 'name', 'Product')
                        pid = product.id
                    else:
                        product = None
                        price = Decimal(random.choice([25, 35, 45, 120, 60]))
                        pname = random.choice(SAMPLE_NAMES)
                        pid = None

                    qty = random.randint(1, 5)

                    si = SaleItem(sale=sale, product=product, product_name=pname, quantity=qty, price=price)
                    si.save()
                    chosen.append(si)

                # after items saved, sale.update_totals has been called by SaleItem.save
                # set payment and amount given
                payment = random.choice(['Cash', 'GCash', 'Card'])
                # small chance of discount
                if random.random() < 0.12:
                    discount = Decimal(random.choice([5,10,20]))
                else:
                    discount = Decimal('0.00')

                # apply discount and recompute totals
                sale.discount = discount
                sale.update_totals()

                # amount given = total + random tender
                tender_extra = Decimal(random.choice([0,0,10,20,50]))
                sale.amount_given = (sale.total + tender_extra).quantize(Decimal('0.01'))
                sale.change = (sale.amount_given - sale.total).quantize(Decimal('0.01'))
                sale.payment_method = payment
                sale.save()

                created += 1

        self.stdout.write(self.style.SUCCESS(f'Generated {created} dummy sales/transactions for last {days} days.'))
