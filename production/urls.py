from django.urls import path
from . import views

app_name = 'production'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Machine Analysis
    path('machines/', views.MachineAnalysisView.as_view(), name='machine_analysis'),
    path('machines/add/', views.MachineCreateView.as_view(), name='machine_create'),
    path('machines/export/', views.MachineExportView.as_view(), name='machine_export'),
    path('machines/<int:machine_id>/health-check/', views.MachineHealthCheckView.as_view(), name='machine_health_check'),
    path('machines/<int:machine_id>/update/', views.MachineUpdateView.as_view(), name='machine_update'),
    path('machines/<int:machine_id>/reading/', views.MachineReadingCreateView.as_view(), name='machine_reading'),

    # Production Batches
    path('batches/', views.ProductionBatchListView.as_view(), name='batch-list'),
    path('batches/add/', views.ProductionBatchCreateView.as_view(), name='batch-create'),
    path('batches/<int:pk>/', views.ProductionBatchDetailView.as_view(), name='batch-detail'),
    path('batches/<int:pk>/update/', views.ProductionBatchUpdateView.as_view(), name='batch-update'),

    # Batch Stages
    path('batches/<int:batch_id>/stages/add/', views.BatchStageCreateView.as_view(), name='batch-stage-create'),
    path('batch-stages/<int:pk>/update/', views.BatchStageUpdateView.as_view(), name='batch-stage-update'),

    # Production Outputs
    path('batches/<int:batch_id>/outputs/add/', views.ProductionOutputCreateView.as_view(), name='output-create'),

    # Production Stages
    path('stages/', views.ProductionStageListView.as_view(), name='stage-list'),
    path('stages/add/', views.ProductionStageCreateView.as_view(), name='stage-create'),

    # API Endpoints
    path('api/production-stats/', views.ProductionStatsAPI.as_view(), name='api-production-stats'),
]
