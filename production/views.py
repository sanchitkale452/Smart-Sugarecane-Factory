from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q, F, Avg
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
import csv
import json

from .models import ProductionBatch, ProductionStage, BatchStage, ProductionOutput, Machine, MachineReading
from .forms import ProductionBatchForm, ProductionStageForm, BatchStageForm, ProductionOutputForm

class DashboardView(LoginRequiredMixin, TemplateView):
    """Production dashboard view."""
    template_name = 'production/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Production statistics
        context['total_batches'] = ProductionBatch.objects.count()
        context['active_batches'] = ProductionBatch.objects.filter(
            status__in=['in_progress', 'on_hold']
        ).count()
        context['total_output'] = ProductionOutput.objects.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        # Recent batches
        context['recent_batches'] = ProductionBatch.objects.order_by('-start_date')[:5]
        
        # Production by stage
        context['stages'] = ProductionStage.objects.filter(is_active=True)
        
        return context

# Production Batch Views
class ProductionBatchListView(LoginRequiredMixin, ListView):
    model = ProductionBatch
    template_name = 'production/batch_list.html'
    context_object_name = 'batches'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = ProductionBatch.objects.select_related('farm').order_by('-start_date')
        
        # Filtering
        status = self.request.GET.get('status')
        farm = self.request.GET.get('farm')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if status:
            queryset = queryset.filter(status=status)
        if farm:
            queryset = queryset.filter(farm_id=farm)
        if date_from:
            queryset = queryset.filter(start_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(start_date__date__lte=date_to)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add filter form context if needed
        return context

class ProductionBatchDetailView(LoginRequiredMixin, DetailView):
    model = ProductionBatch
    template_name = 'production/batch_detail.html'
    context_object_name = 'batch'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch = self.get_object()
        
        # Get all stages for this batch
        context['batch_stages'] = batch.batch_stages.select_related('stage', 'supervisor')
        
        # Get production outputs
        context['outputs'] = batch.outputs.all()
        
        # Calculate total output
        context['total_output'] = batch.outputs.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        return context

class ProductionBatchCreateView(LoginRequiredMixin, CreateView):
    model = ProductionBatch
    form_class = ProductionBatchForm
    template_name = 'production/batch_form.html'
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user if self.request.user.is_authenticated else None
        response = super().form_valid(form)
        messages.success(self.request, f'Production batch {self.object.batch_number} created successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('production:batch-detail', kwargs={'pk': self.object.pk})

class ProductionBatchUpdateView(LoginRequiredMixin, UpdateView):
    model = ProductionBatch
    form_class = ProductionBatchForm
    template_name = 'production/batch_form.html'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Production batch {self.object.batch_number} updated successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('production:batch-detail', kwargs={'pk': self.object.pk})

# Production Stage Views
class ProductionStageListView(LoginRequiredMixin, ListView):
    model = ProductionStage
    template_name = 'production/stage_list.html'
    context_object_name = 'stages'
    
    def get_queryset(self):
        return ProductionStage.objects.filter(is_active=True).order_by('name')

class ProductionStageCreateView(LoginRequiredMixin, CreateView):
    model = ProductionStage
    form_class = ProductionStageForm
    template_name = 'production/stage_form.html'
    success_url = reverse_lazy('production:stage-list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Production stage {self.object.name} created successfully!')
        return response

# Batch Stage Views
class BatchStageCreateView(LoginRequiredMixin, CreateView):
    model = BatchStage
    form_class = BatchStageForm
    template_name = 'production/batch_stage_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        batch_id = self.kwargs.get('batch_id')
        if batch_id:
            initial['batch'] = get_object_or_404(ProductionBatch, pk=batch_id)
        return initial
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Stage {self.object.stage.name} added to batch {self.object.batch.batch_number}!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('production:batch-detail', kwargs={'pk': self.object.batch.pk})

class BatchStageUpdateView(LoginRequiredMixin, UpdateView):
    model = BatchStage
    form_class = BatchStageForm
    template_name = 'production/batch_stage_form.html'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Stage {self.object.stage.name} updated successfully!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('production:batch-detail', kwargs={'pk': self.object.batch.pk})

# Production Output Views
class ProductionOutputCreateView(LoginRequiredMixin, CreateView):
    model = ProductionOutput
    form_class = ProductionOutputForm
    template_name = 'production/output_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        batch_id = self.kwargs.get('batch_id')
        if batch_id:
            initial['batch'] = get_object_or_404(ProductionBatch, pk=batch_id)
        return initial
    
    def form_valid(self, form):
        form.instance.recorded_by = self.request.user if self.request.user.is_authenticated else None
        response = super().form_valid(form)
        messages.success(self.request, f'Output recorded successfully for batch {self.object.batch.batch_number}!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('production:batch-detail', kwargs={'pk': self.object.batch.pk})

# API Views
class ProductionStatsAPI(LoginRequiredMixin, View):
    """API endpoint for production statistics."""
    def get(self, request, *args, **kwargs):
        # Get date range (default: last 30 days)
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=30)
        
        # Get data for the chart
        daily_output = ProductionOutput.objects.filter(
            recorded_at__date__range=[start_date, end_date]
        ).values('recorded_at__date').annotate(
            total=Sum('quantity')
        ).order_by('recorded_at__date')
        
        # Format data for Chart.js
        labels = [str(item['recorded_at__date']) for item in daily_output]
        data = [float(item['total'] or 0) for item in daily_output]
        
        return JsonResponse({
            'labels': labels,
            'datasets': [{
                'label': 'Daily Production (kg)',
                'data': data,
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            }]
        })


class MachineAnalysisView(LoginRequiredMixin, TemplateView):
    """Machine Analysis dashboard view."""
    template_name = 'production/machine_analysis.html'

    def get_context_data(self, **kwargs):
        import json as _json
        context = super().get_context_data(**kwargs)

        machines = Machine.objects.all()

        # Filters
        status_filter = self.request.GET.get('status', '')
        type_filter   = self.request.GET.get('machine_type', '')
        health_filter = self.request.GET.get('health', '')
        search_q      = self.request.GET.get('q', '')

        if status_filter:
            machines = machines.filter(current_status=status_filter)
        if type_filter:
            machines = machines.filter(machine_type=type_filter)
        if health_filter == 'healthy':
            machines = machines.filter(health_score__gte=90)
        elif health_filter == 'attention':
            machines = machines.filter(health_score__gte=70, health_score__lt=90)
        elif health_filter == 'critical':
            machines = machines.filter(health_score__lt=70)
        if search_q:
            machines = machines.filter(
                Q(name__icontains=search_q) |
                Q(location__icontains=search_q) |
                Q(serial_number__icontains=search_q)
            )

        all_machines = Machine.objects.all()

        # Summary stats
        context['healthy_machines']   = all_machines.filter(health_score__gte=90).count()
        context['attention_machines'] = all_machines.filter(health_score__gte=70, health_score__lt=90).count()
        context['critical_machines']  = all_machines.filter(health_score__lt=70).count()
        context['running_machines']   = all_machines.filter(current_status='running').count()
        context['total_machines']     = all_machines.count()
        context['avg_efficiency']     = all_machines.aggregate(avg=Avg('efficiency_rating'))['avg'] or 0

        # Maintenance schedule
        today = timezone.now().date()
        context['overdue_machines']    = all_machines.filter(next_maintenance_due__lt=today).order_by('next_maintenance_due')
        context['upcoming_maintenance'] = all_machines.filter(
            next_maintenance_due__gte=today,
            next_maintenance_due__lte=today + timezone.timedelta(days=14)
        ).order_by('next_maintenance_due')

        # Recent anomaly alerts
        context['recent_alerts'] = MachineReading.objects.filter(
            is_anomaly=True
        ).select_related('machine').order_by('-timestamp')[:10]

        # ── Chart data ──────────────────────────────────────────────
        def f(v): return round(float(v), 1) if v is not None else 0

        # 1. Health donut
        context['chart_health'] = _json.dumps([
            context['healthy_machines'],
            context['attention_machines'],
            context['critical_machines'],
        ])

        # 2. Machine type distribution
        type_counts = all_machines.values('machine_type').annotate(count=Count('id'))
        type_label_map = dict(Machine.MACHINE_TYPE)
        context['chart_type_labels'] = _json.dumps([type_label_map.get(t['machine_type'], t['machine_type']) for t in type_counts])
        context['chart_type_data']   = _json.dumps([t['count'] for t in type_counts])

        # 3. Avg efficiency per type
        eff_by_type = all_machines.values('machine_type').annotate(avg_eff=Avg('efficiency_rating'))
        context['chart_eff_labels'] = _json.dumps([type_label_map.get(t['machine_type'], t['machine_type']) for t in eff_by_type])
        context['chart_eff_data']   = _json.dumps([f(t['avg_eff']) for t in eff_by_type])

        # 4. Per-machine health scores (bar)
        machine_list = list(all_machines.order_by('name'))
        context['chart_machine_names']  = _json.dumps([m.name for m in machine_list])
        context['chart_machine_health'] = _json.dumps([f(m.health_score) for m in machine_list])
        context['chart_machine_eff']    = _json.dumps([f(m.efficiency_rating) for m in machine_list])
        context['chart_machine_temp']   = _json.dumps([f(m.temperature) for m in machine_list])
        context['chart_machine_vib']    = _json.dumps([f(m.vibration_level) for m in machine_list])

        # 5. Status distribution
        status_counts = all_machines.values('current_status').annotate(count=Count('id'))
        status_label_map = dict(Machine.MACHINE_STATUS)
        context['chart_status_labels'] = _json.dumps([status_label_map.get(s['current_status'], s['current_status']) for s in status_counts])
        context['chart_status_data']   = _json.dumps([s['count'] for s in status_counts])

        # 6. Readings trend — last 14 days avg temp & vibration per day
        from datetime import timedelta
        fourteen_ago = timezone.now() - timedelta(days=14)
        daily_readings = (
            MachineReading.objects
            .filter(timestamp__gte=fourteen_ago)
            .extra(select={'day': "date(timestamp)"})
            .values('day')
            .annotate(
                avg_temp=Avg('temperature'),
                avg_vib=Avg('vibration'),
                count=Count('id')
            )
            .order_by('day')
        )
        context['chart_reading_days']  = _json.dumps([str(r['day']) for r in daily_readings])
        context['chart_reading_temp']  = _json.dumps([f(r['avg_temp']) for r in daily_readings])
        context['chart_reading_vib']   = _json.dumps([f(r['avg_vib']) for r in daily_readings])
        context['chart_reading_count'] = _json.dumps([r['count'] for r in daily_readings])

        # Filter form state
        context['machines']         = machines
        context['status_filter']    = status_filter
        context['type_filter']      = type_filter
        context['health_filter']    = health_filter
        context['search_q']         = search_q
        context['machine_statuses'] = Machine.MACHINE_STATUS
        context['machine_types']    = Machine.MACHINE_TYPE

        return context


class MachineCreateView(LoginRequiredMixin, View):
    """AJAX view to create a new machine."""

    def post(self, request):
        data = request.POST
        try:
            machine = Machine.objects.create(
                name=data['name'],
                machine_type=data['machine_type'],
                serial_number=data['serial_number'],
                location=data['location'],
                installation_date=data['installation_date'],
                model_number=data.get('model_number', ''),
                current_status=data.get('current_status', 'idle'),
                next_maintenance_due=data.get('next_maintenance_due') or None,
            )
            return JsonResponse({'success': True, 'id': machine.id, 'name': machine.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class MachineUpdateView(LoginRequiredMixin, View):
    """AJAX view to update machine details."""

    def post(self, request, machine_id):
        machine = get_object_or_404(Machine, id=machine_id)
        data = request.POST
        try:
            machine.name = data.get('name', machine.name)
            machine.machine_type = data.get('machine_type', machine.machine_type)
            machine.location = data.get('location', machine.location)
            machine.current_status = data.get('current_status', machine.current_status)
            machine.efficiency_rating = data.get('efficiency_rating') or machine.efficiency_rating
            machine.temperature = data.get('temperature') or machine.temperature
            machine.vibration_level = data.get('vibration_level') or machine.vibration_level
            machine.power_consumption = data.get('power_consumption') or machine.power_consumption
            machine.next_maintenance_due = data.get('next_maintenance_due') or machine.next_maintenance_due
            machine.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class MachineReadingCreateView(LoginRequiredMixin, View):
    """AJAX view to log a new sensor reading for a machine."""

    def post(self, request, machine_id):
        machine = get_object_or_404(Machine, id=machine_id)
        data = request.POST
        try:
            reading = MachineReading.objects.create(
                machine=machine,
                temperature=data.get('temperature') or None,
                vibration=data.get('vibration') or None,
                power_consumption=data.get('power_consumption') or None,
                production_rate=data.get('production_rate') or None,
                error_code=data.get('error_code', ''),
            )
            # Update machine live metrics
            if reading.temperature:
                machine.temperature = reading.temperature
            if reading.vibration:
                machine.vibration_level = reading.vibration
            if reading.power_consumption:
                machine.power_consumption = reading.power_consumption
            machine.save(update_fields=['temperature', 'vibration_level', 'power_consumption'])
            return JsonResponse({'success': True, 'reading_id': reading.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class MachineExportView(LoginRequiredMixin, View):
    """Export machine data as CSV."""

    def get(self, request):
        machines = Machine.objects.all()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="machines.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Type', 'Serial Number', 'Location', 'Status',
            'Health Score', 'Temperature (°C)', 'Vibration (Hz)',
            'Efficiency (%)', 'Power (kW)', 'Operating Hours',
            'Last Maintenance', 'Next Maintenance Due',
        ])
        for m in machines:
            writer.writerow([
                m.name, m.get_machine_type_display(), m.serial_number, m.location,
                m.get_current_status_display(), float(m.health_score),
                float(m.temperature) if m.temperature else '',
                float(m.vibration_level) if m.vibration_level else '',
                float(m.efficiency_rating) if m.efficiency_rating else '',
                float(m.power_consumption) if m.power_consumption else '',
                float(m.operating_hours),
                m.last_maintenance or '', m.next_maintenance_due or '',
            ])
        return response


class MachineHealthCheckView(LoginRequiredMixin, View):
    """AJAX view to run health check on a machine."""
    
    def post(self, request, machine_id):
        machine = get_object_or_404(Machine, id=machine_id)
        
        # Run health analysis
        health_analysis = machine.analyze_health()
        machine.save(update_fields=['health_score', 'is_healthy'])
        
        # Convert Decimal to float for JSON serialization
        health_analysis['health_score'] = float(health_analysis['health_score'])
        
        return JsonResponse({
            'success': True,
            'health_analysis': health_analysis
        })
