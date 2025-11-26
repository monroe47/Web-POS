from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages.middleware import MessageMiddleware
from Inventory.models import Item
from POS.models import Sale, SaleItem, DailySalesRecord
from decimal import Decimal
import json
import uuid
from django.utils import timezone # ADDED: Import timezone

User = get_user_model()

@override_settings(MIDDLEWARE=[
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
])
class CoreE2ETests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            full_name='Admin User',
            password='adminpassword'
        )
        self.admin_user.is_active = True
        self.admin_user.save()

        # Log in the admin user
        login_successful = self.client.login(username='admin', password='adminpassword')
        self.assertTrue(login_successful, "Admin user login failed")

        # Create an initial item that might be selected for sale
        self.initial_item = Item.objects.create(name='Initial Item', sku='INIT001', price=Decimal('1.00'), stock=10)

    def test_admin_to_sale_flow(self):
        """Simulates admin login, item creation, sale processing, and verification."""

        # 1. Simulate admin creating a new Item via Inventory app
        inventory_add_url = reverse('inventory:add_product')
        new_item_name = "E2E Test Product"
        new_item_sku = str(uuid.uuid4()).replace('-', '')[:10].upper()
        new_item_price = '150.75'
        new_item_stock = '5'
        new_item_min_stock = '2'

        response_add_item = self.client.post(inventory_add_url, {
            'name': new_item_name,
            'sku': new_item_sku,
            'price': new_item_price,
            'category': 'Test E2E Category',
            'pstock': new_item_stock,
            'min_stock_level': new_item_min_stock,
            'color_hex': '#abcdef'
        }, follow=True)

        self.assertEqual(response_add_item.status_code, 200)
        # Corrected assertion to match the HTML entity for single quote
        self.assertContains(response_add_item, f"Product &#x27;{new_item_name}&#x27; added successfully.")

        # Verify item was created in DB
        created_item = Item.objects.get(sku=new_item_sku)
        self.assertIsNotNone(created_item)
        self.assertEqual(created_item.name, new_item_name)
        self.assertEqual(created_item.stock, int(new_item_stock))

        # 2. Simulate processing a sale of the newly created item
        process_sale_url = reverse('pos:process_sale')
        sale_quantity = 2
        expected_sale_total = Decimal(new_item_price) * sale_quantity

        response_process_sale = self.client.post(process_sale_url,
            json.dumps({
                'cart_items': [
                    {'id': created_item.id, 'name': created_item.name, 'price': str(created_item.price), 'quantity': sale_quantity},
                ],
                'total_amount': str(expected_sale_total),
                'amount_tendered': str(expected_sale_total),
                'payment_method': 'Cash'
            }),
            content_type='application/json'
        )

        self.assertEqual(response_process_sale.status_code, 200)
        json_response = response_process_sale.json()
        self.assertTrue(json_response.get('success'), f"Sale processing failed: {json_response.get('message')}")
        self.assertIn('Transaction successfully processed', json_response.get('message'))

        # 3. Verify stock reduction
        created_item.refresh_from_db()
        self.assertEqual(created_item.stock, int(new_item_stock) - sale_quantity)

        # 4. Verify sale and SaleItem records
        sale_id = json_response.get('sale_id')
        self.assertIsNotNone(sale_id)
        sale = Sale.objects.get(id=sale_id)
        self.assertIsNotNone(sale)
        self.assertEqual(sale.total, expected_sale_total)

        sale_item = SaleItem.objects.get(sale=sale, product=created_item)
        self.assertIsNotNone(sale_item)
        self.assertEqual(sale_item.quantity, sale_quantity)
        self.assertEqual(sale_item.price, created_item.price)

        # 5. Verify DailySalesRecord was updated
        daily_record = DailySalesRecord.objects.get(date=timezone.localdate())
        self.assertIsNotNone(daily_record)
        # Note: Actual total sales might be higher if other sales were made in setup or other tests.
        # This test only checks that a record exists.
        self.assertTrue(daily_record.total_sales >= expected_sale_total)

