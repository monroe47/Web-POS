from django.urls import path
from . import views

app_name = 'sheet'

urlpatterns = [
    # Accessible at '/sheet/' (project includes this app at path 'sheet/')
    path('', views.sheet_view, name='excel'),
    path('dashboard/', views.spreadsheet_dashboard, name='spreadsheet_dashboard'), # Added for template link
]
