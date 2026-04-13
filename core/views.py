from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.generic import TemplateView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
from django.db.models import Q, F
from .models import User, Notification
from .forms import UserRegistrationForm, UserProfileForm

class FactoryManagementView(LoginRequiredMixin, TemplateView):
    """Factory Management home page view."""
    template_name = 'core/factory_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Import models here to avoid circular imports
        from inventory.models import Item
        from farms.models import Farm, Farmer
        
        # Inventory stats
        active_items = Item.objects.filter(is_active=True)
        context['total_items'] = active_items.count()
        context['low_stock_items'] = sum(1 for item in active_items if item.is_below_reorder_point)
        
        # Farmer stats
        context['total_farmers'] = Farmer.objects.filter(is_active=True).count()
        
        # Farm stats
        context['active_farms'] = Farm.objects.filter(status='active').count()
        
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard view for authenticated users."""
    template_name = 'core/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Import models here to avoid circular imports
        from inventory.models import Item, InventoryTransaction, InventoryItem
        from farms.models import Farm, FarmActivity
        from production.models import ProductionBatch
        
        # Inventory stats
        active_items = Item.objects.filter(is_active=True)
        context['total_items'] = active_items.count()
        context['low_stock_items'] = sum(1 for item in active_items if item.is_below_reorder_point)
        
        # Recent transactions (last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        context['recent_transactions'] = InventoryTransaction.objects.filter(
            created_at__gte=seven_days_ago
        ).count()
        
        # Expiring items (next 30 days)
        thirty_days_ahead = timezone.now().date() + timedelta(days=30)
        context['expiring_soon'] = InventoryItem.objects.filter(
            expiry_date__lte=thirty_days_ahead,
            expiry_date__gte=timezone.now().date()
        ).count()
        
        # Farms stats
        context['total_farms'] = Farm.objects.count()
        context['active_farms'] = Farm.objects.filter(status='active').count()
        
        # Production stats
        context['active_batches'] = ProductionBatch.objects.filter(
            status__in=['pending', 'in_progress']
        ).count()
        context['completed_batches'] = ProductionBatch.objects.filter(
            status='completed'
        ).count()
        
        # Recent activities
        recent_farm_activities = FarmActivity.objects.select_related(
            'farm', 'performed_by'
        ).order_by('-created_at')[:5]
        
        context['recent_activities'] = recent_farm_activities
        
        return context

class UserRegistrationView(CreateView):
    """View for new user registration."""
    model = User
    form_class = UserRegistrationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Registration successful! Please log in.')
        return response

class UserProfileView(UpdateView):
    """View for user profile management."""
    model = User
    form_class = UserProfileForm
    template_name = 'core/profile.html'
    success_url = reverse_lazy('profile')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)

def mark_notification_read(request, notification_id):
    """Mark a notification as read."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    try:
        notification = request.user.notifications.get(id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

def mark_all_notifications_read(request):
    """Mark all user notifications as read."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})

def chatbot_query(request):
    """Handle chatbot queries using Gemini AI and return intelligent responses."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        
        if not query:
            return JsonResponse({
                'text': "Please ask me a question!",
                'data': None
            })
        
        # Try to use Gemini AI
        try:
            from .gemini_service import get_gemini_service
            
            gemini_service = get_gemini_service()
            response = gemini_service.send_message(query, request.user)
            
            if response.get('success', False):
                return JsonResponse({
                    'text': response['text'],
                    'data': response.get('data')
                })
            else:
                # If Gemini fails, fall back to basic responses
                logger.warning(f"Gemini service failed: {response.get('error')}")
                raise Exception("Gemini service unavailable")
                
        except Exception as gemini_error:
            logger.error(f"Gemini AI error: {gemini_error}")
            
            # Fallback to basic rule-based responses
            query_lower = query.lower()
            
            # Import models for fallback
            from inventory.models import Item
            from farms.models import Farm
            from production.models import ProductionBatch
            
            response = {'text': '', 'data': None}
            
            # Inventory queries
            if 'inventory' in query_lower or 'stock' in query_lower:
                total_items = Item.objects.filter(is_active=True).count()
                response['text'] = f"You have {total_items} active items in inventory. You can view detailed inventory information in the Inventory section."
            
            # Production queries
            elif 'production' in query_lower or 'batch' in query_lower:
                active = ProductionBatch.objects.filter(status__in=['pending', 'in_progress']).count()
                completed = ProductionBatch.objects.filter(status='completed').count()
                response['text'] = f"Production Status:\n- Active batches: {active}\n- Completed batches: {completed}"
            
            # Farm queries
            elif 'farm' in query_lower:
                total_farms = Farm.objects.count()
                active_farms = Farm.objects.filter(status='active').count()
                response['text'] = f"Farm Status:\n- Total farms: {total_farms}\n- Active farms: {active_farms}"
            
            # Help queries
            elif 'help' in query_lower or 'support' in query_lower:
                response['text'] = "I can help you with:\n• Inventory management\n• Production tracking\n• Farm information\n• System navigation\n\nWhat would you like to know?"
            
            # Default response
            else:
                response['text'] = "I can help you with inventory, production, and farm information. What would you like to know?"
            
            return JsonResponse(response)
        
    except Exception as e:
        logger.error(f"Chatbot query error: {e}")
        return JsonResponse({
            'text': "I apologize, but I'm having trouble right now. Please try again later.",
            'error': str(e)
        }, status=500)
