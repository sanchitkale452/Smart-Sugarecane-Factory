from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import F, Sum

from .models import (
    Item, InventoryTransaction, InventoryItem, Location
)

User = get_user_model()

@receiver(pre_save, sender=Item)
def set_item_sku(sender, instance, **kwargs):
    """Automatically set SKU for items if not provided."""
    if not instance.sku and instance.name:
        from django.utils.text import slugify
        base_sku = slugify(instance.name).upper()[:20]
        timestamp = timezone.now().strftime('%y%m%d%H%M')
        instance.sku = f"{base_sku}-{timestamp}"

@receiver(post_save, sender=InventoryTransaction)
def update_inventory_on_transaction(sender, instance, created, **kwargs):
    """Update inventory levels when a transaction is created or updated."""
    if created:
        # Get or create inventory item (handle duplicates)
        try:
            inventory_item = InventoryItem.objects.get(
                item=instance.item,
                location=instance.location
            )
        except InventoryItem.DoesNotExist:
            inventory_item = InventoryItem.objects.create(
                item=instance.item,
                location=instance.location,
                quantity=0
            )
        except InventoryItem.MultipleObjectsReturned:
            # If duplicates exist, consolidate them
            inventory_items = InventoryItem.objects.filter(
                item=instance.item,
                location=instance.location
            ).order_by('id')
            inventory_item = inventory_items.first()
            # Consolidate quantities from duplicates
            total_qty = sum(item.quantity for item in inventory_items)
            inventory_item.quantity = total_qty
            # Delete duplicates (bypass signal)
            for item in inventory_items.exclude(id=inventory_item.id):
                item.quantity = 0  # Set to 0 to bypass the prevention signal
                item.save()
                item.delete()
        
        # Update quantity based on transaction type
        if instance.transaction_type in ['purchase', 'transfer_in', 'adjustment_in', 'return']:
            inventory_item.quantity += instance.quantity
        elif instance.transaction_type in ['sale', 'transfer_out', 'consumption', 'scrap', 'adjustment_out']:
            inventory_item.quantity -= instance.quantity
        
        # Ensure quantity doesn't go negative
        if inventory_item.quantity < 0:
            inventory_item.quantity = 0
        
        inventory_item.save()

@receiver(pre_save, sender=InventoryItem)
def validate_inventory_item(sender, instance, **kwargs):
    """Validate inventory item before saving."""
    # Ensure quantity is not negative
    if instance.quantity < 0:
        instance.quantity = 0
    
    # For serialized items, quantity must be 1
    if instance.item and instance.item.is_serialized:
        instance.quantity = 1

@receiver(post_save, sender=InventoryItem)
def check_reorder_levels(sender, instance, created, **kwargs):
    """Check if inventory levels are below reorder point after saving."""
    if instance.item.reorder_point is not None and instance.quantity <= instance.item.reorder_point:
        # Here you could add a notification system
        # e.g., send_email_to_purchasing(instance.item, instance.quantity)
        pass

@receiver(pre_save, sender=Location)
def set_location_code(sender, instance, **kwargs):
    """Automatically generate a location code if not provided."""
    if not instance.code and instance.name:
        from django.utils.text import slugify
        base_code = slugify(instance.name).upper().replace('-', '')[:10]
        instance.code = base_code

@receiver(pre_delete, sender=InventoryItem)
def prevent_delete_if_has_stock(sender, instance, **kwargs):
    """Prevent deletion of inventory items that still have stock."""
    if instance.quantity > 0:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied(
            f"Cannot delete inventory item with remaining stock. "
            f"Current quantity: {instance.quantity}"
        )

@receiver(pre_delete, sender=Item)
def prevent_delete_if_has_transactions(sender, instance, **kwargs):
    """Prevent deletion of items with transaction history."""
    if InventoryTransaction.objects.filter(item=instance).exists():
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied(
            "Cannot delete item with transaction history. "
            "Set as inactive instead."
        )

# Add more signals as needed for your specific requirements
