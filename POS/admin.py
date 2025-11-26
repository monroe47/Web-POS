from django.contrib import admin
from .models import Sale, SaleItem, Transaction, SaleItemUnit, DailySalesRecord


# ==================== INLINE SALE ITEMS ====================
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('product_name', 'product', 'price', 'quantity', 'line_total')
    can_delete = False
    show_change_link = False


# ==================== SALE ADMIN ====================
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    """
    Displays all completed POS sales with their items inline.
    Read-only to protect data integrity.
    """
    list_display = ('id', 'date', 'payment_method', 'subtotal', 'discount', 'total', 'created_at')
    list_filter = ('payment_method', 'date', 'created_at')
    search_fields = ('id', 'payment_method')
    readonly_fields = (
        'date', 'subtotal', 'discount', 'total',
        'payment_method', 'amount_given', 'change', 'created_at'
    )

    inlines = [SaleItemInline]

    def has_add_permission(self, request):
        """Prevent manual creation of sales."""
        return False

    def has_change_permission(self, request, obj=None):
        """Sales are system-generated; editing is blocked."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow delete only for superusers."""
        return request.user.is_superuser


# ==================== TRANSACTION ADMIN ====================
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """
    Read-only view for all POS transaction logs.
    """
    list_display = ('id', 'sale', 'date', 'payment_method', 'subtotal', 'discount', 'total', 'created_at')
    list_filter = ('payment_method', 'date')
    search_fields = ('sale__id', 'payment_method')
    readonly_fields = ('sale', 'date', 'payment_method', 'subtotal', 'discount', 'total', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ==================== SALE ITEM ADMIN ====================
@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    """
    Read-only view for individual sale items.
    """
    list_display = ('id', 'sale', 'product_name', 'quantity', 'price', 'line_total')
    list_filter = ('sale__date',)
    search_fields = ('product_name', 'sale__id')
    readonly_fields = ('sale', 'product', 'product_name', 'quantity', 'price', 'line_total')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ==================== SALE ITEM UNIT ADMIN ====================
@admin.register(SaleItemUnit)
class SaleItemUnitAdmin(admin.ModelAdmin):
    """
    Displays daily summary of sold items (auto-generated records).
    """
    list_display = ('product_name', 'total_quantity', 'total_revenue', 'date')
    list_filter = ('date',)
    search_fields = ('product_name',)
    ordering = ('-date', '-total_quantity')
    readonly_fields = ('product_name', 'product_id', 'total_quantity', 'total_revenue', 'date')

    def has_add_permission(self, request):
        """No manual adding — these are system-generated summaries."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing of summary records."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion only by superusers."""
        return request.user.is_superuser


# ==================== DAILY SALES RECORD ADMIN ====================
@admin.register(DailySalesRecord)
class DailySalesRecordAdmin(admin.ModelAdmin):
    """
    Shows the total combined sales per day (auto-generated).
    """
    list_display = ('date', 'total_sales')
    list_filter = ('date',)
    ordering = ('-date',)
    readonly_fields = ('date', 'total_sales')
    search_fields = ('date',)

    def has_add_permission(self, request):
        """No manual adding — generated automatically by POS."""
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion only for superusers."""
        return request.user.is_superuser
