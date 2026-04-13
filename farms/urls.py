from django.urls import path
from . import views

app_name = 'farms'

urlpatterns = [
    # Farmer Dashboard
    path('dashboard/', views.FarmDashboardView.as_view(), name='farm_dashboard'),
    
    # Farmer URLs
    path('farmers/', views.FarmerListView.as_view(), name='farmer-list'),
    path('farmers/register/', views.FarmerRegistrationView.as_view(), name='farmer-registration'),
    path('farmers/manage/', views.FarmerManagementView.as_view(), name='farmer-management'),
    path('farmers/<int:pk>/', views.FarmerDetailView.as_view(), name='farmer-detail'),
    path('farmers/list/', views.FarmerListView.as_view(), name='farmer-list-alt'),
    path('farmers/<int:pk>/toggle-verify/', views.FarmerToggleVerifyView.as_view(), name='farmer-toggle-verify'),
    path('farmers/<int:pk>/toggle-active/', views.FarmerToggleActiveView.as_view(), name='farmer-toggle-active'),
    
    # Farm URLs
    path('', views.FarmListView.as_view(), name='farm-list'),
    path('add/', views.FarmCreateView.as_view(), name='farm-create'),
    path('<int:pk>/', views.FarmDetailView.as_view(), name='farm-detail'),
    path('<int:pk>/update/', views.FarmUpdateView.as_view(), name='farm-update'),
    path('<int:pk>/delete/', views.FarmDeleteView.as_view(), name='farm-delete'),
    
    # Farm Crop Cycle URLs
    path('<int:farm_pk>/crop-cycles/add/', views.FarmCropCycleCreateView.as_view(), 
         name='crop-cycle-create'),
    
    # Farm Activity URLs
    path('<int:farm_pk>/activities/add/', views.FarmActivityCreateView.as_view(), 
         name='activity-create'),
    
    # API Endpoints
    path('api/<int:pk>/', views.get_farm_data, name='api-farm-detail'),

    # Variety Analysis
    path('variety-analysis/', views.VarietyAnalysisView.as_view(), name='variety-analysis'),
    path('variety-analysis/api/', views.VarietyAnalysisAPIView.as_view(), name='variety-analysis-api'),
]
