from django.contrib import admin
from .models import Farm, FarmCropCycle, FarmActivity

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'location', 'area', 'status', 'date_acquired')
    list_filter = ('status', 'soil_type')
    search_fields = ('name', 'location', 'owner__username')
    list_editable = ('status',)
    readonly_fields = ('last_updated',)
    fieldsets = (
        ('Farm Information', {
            'fields': ('name', 'owner', 'status', 'description')
        }),
        ('Location & Details', {
            'fields': ('location', 'area', 'soil_type', 'date_acquired')
        }),
        ('Metadata', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )

@admin.register(FarmCropCycle)
class FarmCropCycleAdmin(admin.ModelAdmin):
    list_display = ('farm', 'variety', 'planting_date', 'expected_harvest_date', 'current_stage')
    list_filter = ('current_stage',)
    search_fields = ('farm__name', 'variety')
    date_hierarchy = 'planting_date'

@admin.register(FarmActivity)
class FarmActivityAdmin(admin.ModelAdmin):
    list_display = ('farm', 'activity_type', 'date', 'performed_by', 'cost')
    list_filter = ('activity_type', 'date')
    search_fields = ('farm__name', 'description', 'performed_by__username')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')
