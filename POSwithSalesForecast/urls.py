"""
URL configuration for POSwithSalesForecast project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include(('Account_management.urls', 'account_management'), namespace='account_management')),
    path('inventory/', include(('Inventory.urls', 'inventory'), namespace='inventory')),
    path('pos/', include(('POS.urls', 'pos'), namespace='pos')),
    path('sales_forecast/', include(('Sales_forecast.urls', 'sales_forecast'), namespace='sales_forecast')),
    path('sheet/', include(('Sheet.urls', 'sheet'), namespace='sheet')),
    path('', RedirectView.as_view(url='pos/', permanent=False), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)