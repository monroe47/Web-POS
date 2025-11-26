# POSwithSalesForecast/POSwithSalesForecast/urls.py


from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_view, name='list'),
    path('add/', views.inventory_view, name='add_product'),
    path('update/<int:product_id>/', views.update_product, name='update_product'),
    path('delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('restock/<int:product_id>/', views.restock_item, name='restock_item'),
    path('export/excel/', views.export_inventory_to_excel, name='export_inventory_to_excel'),
]