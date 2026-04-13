from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import (
    Category, UnitOfMeasure, Item, Location, InventoryTransaction, 
    InventoryItem, Supplier
)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    # Removed prepopulated_fields as we don't have a slug field

@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'abbreviation')
    list_editable = ('is_active',)

class InventoryItemInline(admin.TabularInline):
    model = InventoryItem
    extra = 1
    fields = ('location', 'quantity', 'serial_number', 'lot_number', 'expiry_date')
    # Removed current_quantity from readonly_fields as it's not a model field

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'sku', 'item_type', 'category', 'unit_of_measure', 
        'current_quantity', 'is_below_reorder_point', 'is_active'
    )
    list_filter = ('item_type', 'category', 'is_active')
    search_fields = ('name', 'sku', 'barcode', 'description')
    list_editable = ('is_active',)
    inlines = [InventoryItemInline]
    readonly_fields = ('current_quantity', 'is_below_reorder_point')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'sku', 'barcode', 'description', 'category')
        }),
        ('Specifications', {
            'fields': ('item_type', 'unit_of_measure', 'is_serialized', 'is_lot_tracked')
        }),
        ('Inventory Control', {
            'fields': ('min_quantity', 'max_quantity', 'reorder_point')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at', 'current_quantity', 'is_below_reorder_point')
        }),
    )

    def is_below_reorder_point(self, obj):
        return obj.is_below_reorder_point
    is_below_reorder_point.boolean = True
    is_below_reorder_point.short_description = 'Reorder?'

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location_type', 'parent', 'current_occupancy', 'is_active')
    list_filter = ('location_type', 'is_active')
    search_fields = ('name', 'code', 'description')
    list_editable = ('is_active',)
    readonly_fields = ('current_occupancy',)

@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'item_link', 'transaction_type', 'quantity', 'unit_cost', 'total_cost', 'location', 'reference')
    list_filter = ('transaction_type', 'location', 'created_at')
    search_fields = ('item__name', 'reference', 'notes')
    date_hierarchy = 'created_at'
    readonly_fields = ('total_cost', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('item', 'location')
    
    def item_link(self, obj):
        url = reverse('admin:inventory_item_change', args=[obj.item.id])
        return format_html('<a href="{}">{}</a>', url, obj.item.name)
    item_link.short_description = 'Item'
    item_link.admin_order_field = 'item__name'
    def total_cost(self, obj):
        return obj.total_cost
    total_cost.short_description = 'Total Cost'

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('item', 'location', 'quantity', 'serial_number', 'lot_number', 'expiry_date', 'is_expired')
    list_filter = ('location', 'expiry_date')
    search_fields = ('item__name', 'serial_number', 'lot_number')
    readonly_fields = ('is_expired', 'age_days')
    list_select_related = ('item', 'location')

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_person', 'email', 'phone')
    list_editable = ('is_active',)
    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'contact_person', 'email', 'phone', 'website')
        }),
        ('Address', {
            'fields': ('address',)
        }),
        ('Business Details', {
            'fields': ('tax_id', 'payment_terms')
        }),
        ('Status', {
            'fields': ('is_active', 'notes')
        }),
    )
