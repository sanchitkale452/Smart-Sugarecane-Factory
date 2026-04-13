from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard
    path('', views.InventoryDashboardView.as_view(), name='dashboard'),
    path('factory/', views.FactoryDashboardView.as_view(), name='factory_dashboard'),
    
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category-add'),
    path('categories/<int:pk>/', views.CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),
    
    # Items
    path('items/', views.ItemListView.as_view(), name='item-list'),
    path('items/<int:pk>/', views.ItemDetailView.as_view(), name='item-detail'),
    path('items/add/', views.ItemCreateView.as_view(), name='item-add'),
    path('items/<int:pk>/update/', views.ItemUpdateView.as_view(), name='item-update'),
    path('items/<int:pk>/delete/', views.ItemDeleteView.as_view(), name='item-delete'),
    path('items/<int:pk>/delete/ajax/', views.item_delete_ajax, name='item-delete-ajax'),
    
    # Locations
    path('locations/', views.LocationListView.as_view(), name='location-list'),
    path('locations/<int:pk>/', views.LocationDetailView.as_view(), name='location-detail'),
    
    # Transactions
    path('transactions/', views.TransactionListView.as_view(), name='transaction-list'),
    path('transactions/add/', views.TransactionCreateView.as_view(), name='transaction-add'),
    
    # Inventory Management
    path('adjust/', views.InventoryAdjustmentView.as_view(), name='adjust-inventory'),
    path('levels/', views.InventoryLevelsView.as_view(), name='inventory-levels'),
    
    # API Endpoints
    path('api/items/autocomplete/', views.ItemAutocompleteView.as_view(), name='api-item-autocomplete'),
    
    # Export
    path('export/', views.ExportInventoryView.as_view(), name='export-inventory'),

    # Analysis
    path('analysis/', views.InventoryAnalysisView.as_view(), name='analysis'),
    path('analysis/api/', views.InventoryAnalysisAPIView.as_view(), name='analysis-api'),
]
