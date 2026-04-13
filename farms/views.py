from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Fieldset, Div
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Farm, FarmCropCycle, FarmActivity, Farmer
from .forms import FarmForm, FarmCropCycleForm, FarmActivityForm


def _get_demo_user():
    User = get_user_model()
    user, created = User.objects.get_or_create(username='demo')
    if created:
        user.set_unusable_password()
        user.save()
    return user

# Farm Views
class FarmListView(LoginRequiredMixin, ListView):
    model = Farm
    template_name = 'farms/farm_list.html'
    context_object_name = 'farms'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Farm.objects.all().order_by('name')
        search_query = self.request.GET.get('search', '')
        status_filter = self.request.GET.get('status', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_farms'] = Farm.objects.count()
        context['active_farms'] = Farm.objects.filter(status='active').count()
        context['total_area'] = Farm.objects.aggregate(Sum('area'))['area__sum'] or 0
        return context

class FarmDetailView(LoginRequiredMixin, DetailView):
    model = Farm
    template_name = 'farms/farm_detail.html'
    context_object_name = 'farm'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        farm = self.get_object()
        
        # Get recent activities
        context['recent_activities'] = FarmActivity.objects.filter(
            farm=farm
        ).order_by('-date')[:5]
        
        # Get current crop cycle if exists
        context['current_crop'] = FarmCropCycle.objects.filter(
            farm=farm,
            current_stage__in=['preparation', 'planting', 'growing', 'mature']
        ).first()
        
        # Get farm statistics
        context['total_activities'] = FarmActivity.objects.filter(farm=farm).count()
        context['total_crop_cycles'] = FarmCropCycle.objects.filter(farm=farm).count()
        
        return context

class FarmCreateView(LoginRequiredMixin, CreateView):
    model = Farm
    form_class = FarmForm
    template_name = 'farms/farm_form.html'
    
    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.owner = self.request.user
        else:
            form.instance.owner = _get_demo_user()
        response = super().form_valid(form)
        messages.success(self.request, f'Farm "{self.object.name}" has been created successfully!')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Farm'
        return context

class FarmUpdateView(LoginRequiredMixin, UpdateView):
    model = Farm
    form_class = FarmForm
    template_name = 'farms/farm_form.html'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Farm "{self.object.name}" has been updated successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('farms:farm-detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Update {self.object.name}'
        return context

class FarmDeleteView(LoginRequiredMixin, DeleteView):
    model = Farm
    template_name = 'farms/farm_confirm_delete.html'
    success_url = reverse_lazy('farms:farm-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['linked_batches'] = self.get_object().production_batches.all()
        return context

    def post(self, request, *args, **kwargs):
        farm = self.get_object()
        try:
            farm.delete()
            messages.success(request, f'Farm "{farm.name}" has been deleted successfully!')
            return redirect(self.success_url)
        except ProtectedError as e:
            batch_list = ', '.join(str(b) for b in e.protected_objects)
            messages.error(
                request,
                f'Cannot delete farm "{farm.name}" because it is linked to production batches: {batch_list}. '
                f'Delete or reassign those batches first.'
            )
            return redirect('farms:farm-detail', pk=farm.pk)

# Farm Crop Cycle Views
class FarmCropCycleCreateView(LoginRequiredMixin, CreateView):
    model = FarmCropCycle
    form_class = FarmCropCycleForm
    template_name = 'farms/crop_cycle_form.html'
    
    def form_valid(self, form):
        farm = get_object_or_404(Farm, pk=self.kwargs.get('farm_pk'))
        form.instance.farm = farm
        response = super().form_valid(form)
        messages.success(self.request, 'Crop cycle has been added successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('farms:farm-detail', kwargs={'pk': self.kwargs.get('farm_pk')})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['farm'] = get_object_or_404(Farm, pk=self.kwargs.get('farm_pk'))
        return context

# Farm Activity Views
class FarmActivityCreateView(LoginRequiredMixin, CreateView):
    model = FarmActivity
    form_class = FarmActivityForm
    template_name = 'farms/activity_form.html'
    
    def form_valid(self, form):
        farm = get_object_or_404(Farm, pk=self.kwargs.get('farm_pk'))
        form.instance.farm = farm
        form.instance.performed_by = self.request.user if self.request.user.is_authenticated else None
        response = super().form_valid(form)
        messages.success(self.request, 'Activity has been recorded successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('farms:farm-detail', kwargs={'pk': self.kwargs.get('farm_pk')})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['farm'] = get_object_or_404(Farm, pk=self.kwargs.get('farm_pk'))
        return context

# API Views
def get_farm_data(request, pk):
    """API endpoint to get farm data in JSON format."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    farm = get_object_or_404(Farm, pk=pk)
    
    data = {
        'id': farm.id,
        'name': farm.name,
        'location': farm.location,
        'area': str(farm.area),
        'status': farm.status,
        'soil_type': farm.get_soil_type_display(),
        'date_acquired': farm.date_acquired.strftime('%Y-%m-%d'),
        'description': farm.description,
    }
    

# Farmer Registration Views and Forms

class FarmerRegistrationForm(forms.ModelForm):
    class Meta:
        model = Farmer
        fields = [
            'full_name', 'email', 'mobile_number', 'gender', 'date_of_birth',
            'address', 'village', 'district', 'state', 'pin_code',
            'bank_name', 'bank_account_number', 'bank_ifsc_code', 'bank_branch',
            'total_land_area', 'land_holding_type'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Personal Information',
                'full_name', 'email', 'mobile_number', 'gender', 'date_of_birth'
            ),
            Fieldset(
                'Address Information',
                'address', 'village', 'district', 'state', 'pin_code'
            ),
            Fieldset(
                'Bank Details',
                'bank_name', 'bank_account_number', 'bank_ifsc_code', 'bank_branch'
            ),
            Fieldset(
                'Farm Details',
                'total_land_area', 'land_holding_type'
            ),
            Submit('submit', 'Register Farmer', css_class='btn btn-primary')
        )


class FarmerRegistrationView(CreateView):
    model = Farmer
    form_class = FarmerRegistrationForm
    template_name = 'farms/farmer_registration.html'
    success_url = reverse_lazy('farms:farmer-list')

    def form_valid(self, form):
        User = get_user_model()
        full_name = form.cleaned_data['full_name']
        email = form.cleaned_data['email']

        # Use logged-in user if available, otherwise auto-create one
        if self.request.user.is_authenticated:
            user = self.request.user
            # If this user already has a farmer profile, create a new user account
            if hasattr(user, 'farmer_profile'):
                user = None
        else:
            user = None

        if user is None:
            # Generate a unique username from email
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}{counter}'
                counter += 1
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': username,
                    'first_name': full_name.split()[0] if full_name else '',
                    'last_name': ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
                }
            )
            if created:
                user.set_unusable_password()
                user.save()

        form.instance.user = user
        messages.success(self.request, f'Farmer {full_name} registered successfully!')
        return super().form_valid(form)


class FarmerListView(LoginRequiredMixin, ListView):
    model = Farmer
    template_name = 'farms/farmer_list.html'
    context_object_name = 'farmers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(mobile_number__icontains=search)
            )
        return queryset


class FarmerManagementView(LoginRequiredMixin, ListView):
    model = Farmer
    template_name = 'farms/farmer_management.html'
    context_object_name = 'farmers'
    paginate_by = 20

    def get_queryset(self):
        queryset = Farmer.objects.all()
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        verified = self.request.GET.get('verified', '')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(mobile_number__icontains=search)
            )
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        if verified == '1':
            queryset = queryset.filter(is_verified=True)
        elif verified == '0':
            queryset = queryset.filter(is_verified=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_farmers'] = Farmer.objects.count()
        context['active_farmers'] = Farmer.objects.filter(is_active=True).count()
        context['verified_farmers'] = Farmer.objects.filter(is_verified=True).count()
        context['pending_farmers'] = Farmer.objects.filter(is_verified=False).count()
        context['search_q'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['verified_filter'] = self.request.GET.get('verified', '')
        return context


class FarmerToggleVerifyView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        farmer = get_object_or_404(Farmer, pk=pk)
        farmer.is_verified = not farmer.is_verified
        farmer.save(update_fields=['is_verified'])
        status = 'verified' if farmer.is_verified else 'unverified'
        return JsonResponse({'success': True, 'message': f'{farmer.full_name} {status}.'})


class FarmerToggleActiveView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        farmer = get_object_or_404(Farmer, pk=pk)
        farmer.is_active = not farmer.is_active
        farmer.save(update_fields=['is_active'])
        status = 'activated' if farmer.is_active else 'deactivated'
        return JsonResponse({'success': True, 'message': f'{farmer.full_name} {status}.'})


class FarmerDetailView(LoginRequiredMixin, DetailView):
    model = Farmer
    template_name = 'farms/farmer_detail.html'
    context_object_name = 'farmer'


class FarmDashboardView(LoginRequiredMixin, TemplateView):
    """Farm Management Dashboard view."""
    template_name = 'farms/farm_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Farmer stats
        context['total_farmers'] = Farmer.objects.filter(is_active=True).count()

        # Farm stats
        context['total_farms'] = Farm.objects.count()
        context['active_farms'] = Farm.objects.filter(status='active').count()
        
        # Crop cycle stats
        context['active_cycles'] = FarmCropCycle.objects.exclude(current_stage='harvested').count()
        
        # Total area
        from django.db.models import Sum
        context['total_area'] = Farm.objects.aggregate(total=Sum('area'))['total'] or 0
        
        # Recent farmers
        context['recent_farmers'] = Farmer.objects.filter(is_active=True).order_by('-registration_date')[:5]
        
        # Recent activities
        context['recent_activities'] = FarmActivity.objects.select_related('farm', 'performed_by').order_by('-date')[:5]
        
        return context


class VarietyAnalysisView(LoginRequiredMixin, TemplateView):
    """Sugarcane variety analysis — data embedded server-side, charts update via JS."""
    template_name = 'farms/variety_analysis.html'

    def get_context_data(self, **kwargs):
        import json
        from django.db.models import Avg, Count, Sum

        context = super().get_context_data(**kwargs)
        selected = self.request.GET.get('variety', '')

        all_varieties = list(
            FarmCropCycle.objects.values_list('variety', flat=True).distinct().order_by('variety')
        )
        context['varieties'] = all_varieties
        context['selected_variety'] = selected

        def build_data(variety_filter=''):
            qs = FarmCropCycle.objects.all()
            if variety_filter:
                qs = qs.filter(variety=variety_filter)

            yield_data = list(
                qs.values('variety')
                .annotate(avg_estimated=Avg('estimated_yield'), avg_actual=Avg('actual_yield'), cycle_count=Count('id'))
                .order_by('variety')
            )
            stage_data = list(
                qs.values('current_stage').annotate(count=Count('id')).order_by('current_stage')
            )
            stage_labels = {k: str(v) for k, v in FarmCropCycle.CROP_STAGES}
            farm_data = list(
                qs.values('farm__name')
                .annotate(count=Count('id'), total_yield=Sum('actual_yield'))
                .order_by('-count')[:10]
            )
            trend_data = list(
                qs.filter(actual_yield__isnull=False)
                .values('variety', 'planting_date__year')
                .annotate(avg_yield=Avg('actual_yield'))
                .order_by('planting_date__year')
            )

            def f(v): return round(float(v), 2) if v is not None else None

            return {
                'yield_comparison': {
                    'labels': [d['variety'] for d in yield_data],
                    'estimated': [f(d['avg_estimated']) for d in yield_data],
                    'actual': [f(d['avg_actual']) for d in yield_data],
                    'counts': [d['cycle_count'] for d in yield_data],
                },
                'stage_distribution': {
                    'labels': [stage_labels.get(d['current_stage'], d['current_stage']) for d in stage_data],
                    'counts': [d['count'] for d in stage_data],
                },
                'farm_distribution': {
                    'labels': [d['farm__name'] for d in farm_data],
                    'counts': [d['count'] for d in farm_data],
                    'yields': [f(d['total_yield']) for d in farm_data],
                },
                'yield_trend': [
                    {'variety': d['variety'], 'year': d['planting_date__year'], 'avg_yield': f(d['avg_yield'])}
                    for d in trend_data
                ],
            }

        # Build data for ALL varieties (for dynamic switching)
        all_data = {'': build_data('')}
        for v in all_varieties:
            all_data[v] = build_data(v)

        context['chart_data_json'] = json.dumps(all_data)
        return context


class VarietyAnalysisAPIView(LoginRequiredMixin, View):
    """JSON API returning variety analysis data for charts."""

    def get(self, request):
        from django.db.models import Avg, Count, Sum
        from decimal import Decimal

        variety_filter = request.GET.get('variety', '')
        qs = FarmCropCycle.objects.all()
        if variety_filter:
            qs = qs.filter(variety=variety_filter)

        # 1. Avg estimated vs actual yield per variety
        yield_data = (
            qs.values('variety')
            .annotate(
                avg_estimated=Avg('estimated_yield'),
                avg_actual=Avg('actual_yield'),
                cycle_count=Count('id'),
            )
            .order_by('variety')
        )

        # 2. Stage distribution (all or filtered)
        stage_data = (
            qs.values('current_stage')
            .annotate(count=Count('id'))
            .order_by('current_stage')
        )
        stage_labels = dict(FarmCropCycle.CROP_STAGES)

        # 3. Cycles per farm for selected variety
        farm_data = (
            qs.values('farm__name')
            .annotate(count=Count('id'), total_yield=Sum('actual_yield'))
            .order_by('-count')[:10]
        )

        # 4. Yield trend over planting years
        trend_data = (
            qs.filter(actual_yield__isnull=False)
            .values('variety', 'planting_date__year')
            .annotate(avg_yield=Avg('actual_yield'))
            .order_by('planting_date__year')
        )

        def to_float(val):
            if val is None:
                return None
            return float(val)

        return JsonResponse({
            'yield_comparison': {
                'labels': [d['variety'] for d in yield_data],
                'estimated': [to_float(d['avg_estimated']) for d in yield_data],
                'actual': [to_float(d['avg_actual']) for d in yield_data],
                'counts': [d['cycle_count'] for d in yield_data],
            },
            'stage_distribution': {
                'labels': [stage_labels.get(d['current_stage'], d['current_stage']) for d in stage_data],
                'counts': [d['count'] for d in stage_data],
            },
            'farm_distribution': {
                'labels': [d['farm__name'] for d in farm_data],
                'counts': [d['count'] for d in farm_data],
                'yields': [to_float(d['total_yield']) for d in farm_data],
            },
            'yield_trend': [
                {
                    'variety': d['variety'],
                    'year': d['planting_date__year'],
                    'avg_yield': to_float(d['avg_yield']),
                }
                for d in trend_data
            ],
        })
