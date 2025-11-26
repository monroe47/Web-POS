# POSwithSalesForecast/Account_management/urls.py
from django.urls import path
from . import views

app_name = 'account_management'  # use lowercase to match template usage

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.create_account, name='signup'),  # Alias for create_account
    path('', views.account_list, name='account_list'),
    path('create/', views.create_account, name='create'),
    path("delete/<int:user_id>/", views.delete_account, name="delete_account"), # POST only, no pk in URL
    path('export_csv/', views.export_accounts_csv, name='export_csv'),
    path('logs/<int:user_id>/', views.user_logs, name='logs'),
]
