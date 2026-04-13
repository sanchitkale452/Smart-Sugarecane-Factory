from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import send_mail
from .models import User, Notification

@receiver(post_save, sender=User)
def create_welcome_notification(sender, instance, created, **kwargs):
    """Create a welcome notification for new users."""
    if created:
        Notification.objects.create(
            user=instance,
            message=f'Welcome to Sugarcane Factory Management System, {instance.get_full_name() or instance.username}!',
            notification_type='success'
        )
        
        # Send welcome email
        subject = 'Welcome to Sugarcane Factory Management System'
        message = f'Hello {instance.get_full_name() or instance.username},\n\nThank you for registering with our system.\n\nBest regards,\nSugarcane Factory Team'
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
            fail_silently=True,
        )

# Removed save_user_profile signal since we're using a custom User model with profile fields directly
