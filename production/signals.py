from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db.models import F, Sum
from django.utils import timezone
from .models import ProductionBatch, BatchStage, ProductionOutput

@receiver(post_save, sender=BatchStage)
def update_batch_status_on_stage_completion(sender, instance, created, **kwargs):
    """
    Update the production batch status when all stages are completed.
    """
    if instance.status == 'completed' and not created:
        batch = instance.batch
        completed_stages = batch.batch_stages.filter(status='completed').count()
        total_stages = batch.batch_stages.count()
        
        if completed_stages == total_stages:
            batch.status = 'completed'
            batch.end_date = timezone.now()
            batch.save()

@receiver(post_save, sender=ProductionOutput)
def update_batch_yield(sender, instance, created, **kwargs):
    """
    Update the actual yield of the production batch when outputs are added.
    """
    if created:
        batch = instance.batch
        total_output = batch.outputs.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        if batch.actual_yield != total_output:
            batch.actual_yield = total_output
            batch.save()

@receiver(pre_save, sender=ProductionBatch)
def generate_batch_number(sender, instance, **kwargs):
    """
    Generate a unique batch number if not provided.
    Format: BATCH-YYYYMMDD-XXXX (where X is a sequential number)
    """
    if not instance.batch_number:
        today = timezone.now().strftime('%Y%m%d')
        last_batch = ProductionBatch.objects.filter(
            batch_number__startswith=f'BATCH-{today}'
        ).order_by('-batch_number').first()
        
        if last_batch:
            last_number = int(last_batch.batch_number.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
            
        instance.batch_number = f'BATCH-{today}-{new_number:04d}'

@receiver(post_save, sender=ProductionBatch)
def create_initial_stages(sender, instance, created, **kwargs):
    """
    Create initial production stages when a new batch is created.
    """
    if created:
        from .models import ProductionStage
        
        # Get all active production stages
        stages = ProductionStage.objects.filter(is_active=True).order_by('id')
        
        # Create batch stages
        for stage in stages:
            BatchStage.objects.create(
                batch=instance,
                stage=stage,
                start_time=timezone.now(),
                status='pending'
            )
            
            # Only auto-start the first stage
            if stage == stages.first():
                BatchStage.objects.filter(
                    batch=instance,
                    stage=stage
                ).update(
                    status='in_progress',
                    start_time=timezone.now()
                )
