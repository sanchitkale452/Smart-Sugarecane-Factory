from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Farm, FarmActivity, FarmCropCycle
from django.db.models import F
from django.utils import timezone

@receiver(post_save, sender=Farm)
def create_farm_activity_on_create(sender, instance, created, **kwargs):
    """Create an activity when a new farm is created."""
    if kwargs.get('raw', False):
        return
    if created:
        FarmActivity.objects.create(
            farm=instance,
            activity_type='maintenance',
            date=timezone.now().date(),
            description=f'Farm "{instance.name}" was registered in the system.',
            performed_by=instance.owner,
            cost=0.00
        )

@receiver(pre_save, sender=FarmCropCycle)
def update_farm_status_on_crop_cycle(sender, instance, **kwargs):
    """Update farm status based on crop cycle changes."""
    if kwargs.get('raw', False):
        return
    if instance.pk:  # Only for updates
        old_instance = FarmCropCycle.objects.get(pk=instance.pk)
        if old_instance.current_stage != instance.current_stage:
            activity = FarmActivity(
                farm=instance.farm,
                activity_type='other',
                date=timezone.now().date(),
                description=f'Crop cycle status changed from {old_instance.get_current_stage_display()} to {instance.get_current_stage_display()}.',
                performed_by=instance.farm.owner
            )
            activity.save()

@receiver(post_save, sender=FarmActivity)
def update_farm_last_activity(sender, instance, created, **kwargs):
    """Update the farm's last_updated timestamp when an activity is added."""
    if kwargs.get('raw', False):
        return
    if created:
        instance.farm.save()  # This will trigger the auto_now update on the farm model

@receiver(post_save, sender=get_user_model())
def assign_default_farm_to_staff(sender, instance, created, **kwargs):
    """Assign a default farm to new staff members if they don't have one."""
    # Disabled - no is_default field on Farm model
    pass
