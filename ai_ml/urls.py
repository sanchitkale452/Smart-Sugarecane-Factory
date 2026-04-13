"""
URL configuration for AI/ML features
"""
from django.urls import path
from . import views

app_name = 'ai_ml'

urlpatterns = [
    # Dashboard
    path('', views.ai_dashboard, name='dashboard'),
    
    # Detailed views
    path('machine/<int:machine_id>/', views.machine_health_detail, name='machine-health'),
    path('farm/<int:farm_id>/', views.farm_yield_analysis, name='farm-yield'),
    path('inventory/<int:item_id>/', views.inventory_forecast_view, name='inventory-forecast'),
    
    # API endpoints
    path('api/anomaly/<int:machine_id>/', views.api_detect_anomaly, name='api-anomaly'),
    path('api/yield/<int:farm_id>/', views.api_predict_yield, name='api-yield'),
    path('api/forecast/<int:item_id>/', views.api_forecast_demand, name='api-forecast'),
]
