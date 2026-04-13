from django.contrib import admin
from .models import (
    ProductionBatch, ProductionStage, BatchStage, ProductionOutput,
    CrushingMachine, SensorReading, AnomalyAlert, OptimizationRecommendation
)

@admin.register(ProductionBatch)
class ProductionBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'farm', 'start_date', 'status', 'expected_yield', 'actual_yield')
    list_filter = ('status', 'start_date')
    search_fields = ('batch_number', 'farm__name', 'notes')
    date_hierarchy = 'start_date'
    readonly_fields = ('last_updated', 'created_by')
    fieldsets = (
        ('Batch Information', {
            'fields': ('batch_number', 'farm', 'status')
        }),
        ('Production Details', {
            'fields': ('start_date', 'end_date', 'expected_yield', 'actual_yield')
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_by', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only set created_by during the first save
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(ProductionStage)
class ProductionStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'stage_type', 'standard_duration', 'is_active')
    list_filter = ('stage_type', 'is_active')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)

@admin.register(BatchStage)
class BatchStageAdmin(admin.ModelAdmin):
    list_display = ('batch', 'stage', 'start_time', 'end_time', 'status', 'supervisor')
    list_filter = ('status', 'stage', 'start_time')
    search_fields = ('batch__batch_number', 'notes')
    readonly_fields = ('duration',)

@admin.register(ProductionOutput)
class ProductionOutputAdmin(admin.ModelAdmin):
    list_display = ('batch', 'get_output_type_display', 'quantity', 'quality_rating', 'recorded_at')
    list_filter = ('output_type', 'recorded_at')
    search_fields = ('batch__batch_number', 'notes')
    date_hierarchy = 'recorded_at'


@admin.register(CrushingMachine)
class CrushingMachineAdmin(admin.ModelAdmin):
    list_display = ('machine_id', 'name', 'status', 'last_maintenance', 'next_maintenance', 'is_active')
    list_filter = ('status', 'is_active', 'manufacturer')
    search_fields = ('machine_id', 'name', 'model')
    readonly_fields = ('machine_id',)
    fieldsets = (
        ('Machine Information', {
            'fields': ('machine_id', 'name', 'model', 'manufacturer', 'installation_date', 'is_active')
        }),
        ('Status', {
            'fields': ('status', 'last_maintenance', 'next_maintenance')
        }),
        ('Optimal Parameters', {
            'fields': ('optimal_pressure', 'optimal_temperature', 'optimal_rotation_speed'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ('machine', 'timestamp', 'pressure', 'temperature', 'rotation_speed', 'extraction_rate')
    list_filter = ('machine', 'timestamp')
    search_fields = ('machine__machine_id', 'machine__name')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
    
    fieldsets = (
        ('Reading Information', {
            'fields': ('machine', 'batch', 'timestamp')
        }),
        ('Primary Sensors', {
            'fields': ('pressure', 'temperature', 'rotation_speed', 'torque', 'feed_rate')
        }),
        ('Secondary Sensors', {
            'fields': ('vibration', 'power_consumption', 'moisture_content', 'brix_level'),
            'classes': ('collapse',)
        }),
        ('Calculated Values', {
            'fields': ('extraction_rate',),
            'classes': ('collapse',)
        }),
    )


@admin.register(AnomalyAlert)
class AnomalyAlertAdmin(admin.ModelAdmin):
    list_display = ('machine', 'detected_at', 'severity', 'status', 'anomaly_score', 'acknowledged_by')
    list_filter = ('severity', 'status', 'detected_at', 'machine')
    search_fields = ('machine__machine_id', 'description', 'resolution_notes')
    date_hierarchy = 'detected_at'
    readonly_fields = ('detected_at', 'anomaly_score', 'sensor_reading')
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('machine', 'sensor_reading', 'detected_at', 'severity', 'anomaly_score')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Status & Resolution', {
            'fields': ('status', 'acknowledged_by', 'acknowledged_at', 'resolved_at', 'resolution_notes')
        }),
    )
    
    actions = ['mark_as_acknowledged', 'mark_as_resolved']
    
    def mark_as_acknowledged(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            status='acknowledged',
            acknowledged_by=request.user,
            acknowledged_at=timezone.now()
        )
        self.message_user(request, f"{queryset.count()} alerts marked as acknowledged.")
    mark_as_acknowledged.short_description = "Mark selected alerts as acknowledged"
    
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            status='resolved',
            resolved_at=timezone.now()
        )
        self.message_user(request, f"{queryset.count()} alerts marked as resolved.")
    mark_as_resolved.short_description = "Mark selected alerts as resolved"


@admin.register(OptimizationRecommendation)
class OptimizationRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        'machine', 'created_at', 'expected_improvement', 'confidence_score', 
        'is_applied', 'applied_by'
    )
    list_filter = ('is_applied', 'created_at', 'machine')
    search_fields = ('machine__machine_id', 'notes')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'expected_improvement', 'confidence_score')
    
    fieldsets = (
        ('Recommendation Information', {
            'fields': ('machine', 'batch', 'created_at', 'expected_improvement', 'confidence_score')
        }),
        ('Current Parameters', {
            'fields': (
                'current_pressure', 'current_temperature', 
                'current_rotation_speed', 'current_feed_rate', 'current_yield'
            )
        }),
        ('Recommended Parameters', {
            'fields': (
                'recommended_pressure', 'recommended_temperature',
                'recommended_rotation_speed', 'recommended_feed_rate', 'expected_yield'
            )
        }),
        ('Implementation', {
            'fields': ('is_applied', 'applied_at', 'applied_by', 'actual_yield', 'notes')
        }),
    )
    
    actions = ['mark_as_applied']
    
    def mark_as_applied(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            is_applied=True,
            applied_at=timezone.now(),
            applied_by=request.user
        )
        self.message_user(request, f"{queryset.count()} recommendations marked as applied.")
    mark_as_applied.short_description = "Mark selected recommendations as applied"
