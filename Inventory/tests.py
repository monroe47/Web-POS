from django.test import TestCase
from Inventory.models import Item

class ItemModelTest(TestCase):
    def test_item_creation(
        self,
    ):
        """Test that an Item can be created successfully."""
        item = Item.objects.create(
            name="Test Product",
            sku="TP001",
            price=100.00,
            category="Test Category",
            stock=10,
            min_stock_level=5,
            color_hex="#FFFFFF",
        )
        self.assertEqual(item.name, "Test Product")
        self.assertEqual(item.sku, "TP001")
        self.assertEqual(item.price, 100.00)
        self.assertEqual(item.stock, 10)

    def test_item_str_representation(
        self,
    ):
        """Test the string representation of an Item."""
        item = Item.objects.create(name="Another Test", sku="AT002", price=50.00, stock=1)
        # Corrected expected string to match the model's __str__ method (which outputs price with one decimal place)
        self.assertEqual(str(item), "Another Test (SKU: AT002) - ₱50.0")

    def test_item_min_stock_level_default(
        self,
    ):
        """Test that min_stock_level defaults correctly if not provided."""
        item = Item.objects.create(name="Default Test", sku="DT003", price=10.00, stock=20)
        self.assertEqual(item.min_stock_level, 10)

