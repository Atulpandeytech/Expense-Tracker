from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('incomes/', views.income_list, name='income_list'),
    path('incomes/<int:pk>/edit/', views.income_update, name='income_update'),
    path('incomes/<int:pk>/delete/', views.income_delete, name='income_delete'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/add/', views.expense_create, name='expense_create'),
    path('expenses/<int:pk>/', views.expense_detail, name='expense_detail'),
    path('expenses/<int:pk>/edit/', views.expense_update, name='expense_update'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    path('expenses/category/<slug:slug>/', views.expense_by_category, name='expense_by_category'),
    path('expenses/month/<str:month_name_value>/', views.expense_by_month, name='expense_by_month'),
    path('budgets/', views.budgets, name='budgets'),
    re_path(r'^reports/(?P<year>[0-9]{4})/$', views.annual_report, name='annual_report'),
    path('api/chart-data/', views.chart_data_json, name='chart_data_json'),
    path('mentor/', views.mentor_chat, name='mentor_chat'),
]
