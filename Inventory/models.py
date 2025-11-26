from django.db import models


class Item(models.Model):
    """
    Defines the structure for a single product record in the database,
    including fields for SKU, image upload, and background color.
    """

    # Core Product Details
    name = models.CharField(max_length=200, verbose_name="Product Name")

    # SKU (Supports Manual/Auto input from HTML)
    sku = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        verbose_name="SKU"
    )

    # Pricing and Category
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Selling Price")
    category = models.CharField(max_length=100, verbose_name="Category")

    # Image Upload (stored inside MEDIA_ROOT/inventory_images/)
    image = models.ImageField(
        upload_to='inventory_images/',
        blank=True,
        null=True,
        verbose_name="Product Image"
    )

    # Background Color Selection (Stores the hex code)
    color_hex = models.CharField(
        max_length=7,
        default='#fef3c7',
        verbose_name="Background Color"
    )

    # Stock and Audit Fields
    stock = models.IntegerField(default=0, verbose_name="Stock Quantity")
    min_stock_level = models.IntegerField(default=10, verbose_name="Minimum Stock Level")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date Added")

    def __str__(self):
        """A descriptive string representation for admin and debugging."""
        return f"{self.name} (SKU: {self.sku or 'N/A'}) - ₱{self.price}"

    # ✅ Added: Method for reducing stock when sold in POS
    def reduce_stock(self, quantity):
        """Safely reduce stock when a sale occurs."""
        if quantity > self.stock:
            raise ValueError(f"Not enough stock for {self.name}")
        self.stock -= quantity
        self.save()

    # ✅ Added: Method for restocking items
    def restock(self, quantity):
        """Increase stock when new items are added."""
        self.stock += quantity
        self.save()


# ✅ Optional: Restock Log Model
class RestockLog(models.Model):
    """
    Tracks every restocking action performed on an Item.
    This helps maintain inventory history and accountability.
    """
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="restocks")
    quantity_added = models.PositiveIntegerField(verbose_name="Quantity Added")
    date = models.DateTimeField(auto_now_add=True, verbose_name="Date Restocked")
    note = models.CharField(max_length=200, blank=True, null=True, verbose_name="Note")

    def save(self, *args, **kwargs):
        """Save log and automatically update the item's stock."""
        super().save(*args, **kwargs)
        self.item.restock(self.quantity_added)

    def __str__(self):
        return f"Restocked {self.item.name} (+{self.quantity_added}) on {self.date.strftime('%Y-%m-%d')}"
