from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
)
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Sum, Count, Q, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponseRedirect
from django.forms import inlineformset_factory
from django.utils import timezone
from django.db.models.deletion import ProtectedError
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import (
    Category, UnitOfMeasure, Item, Location, 
    InventoryTransaction, InventoryItem, Supplier
)
from .forms import (
    CategoryForm, UnitOfMeasureForm, ItemForm, LocationForm,
    InventoryTransactionForm, InventoryItemForm, SupplierForm,
    InventoryAdjustmentForm
)

# Dashboard View
class InventoryDashboardView(LoginRequiredMixin, TemplateView):
    """Inventory dashboard view showing key metrics and recent activities."""
    template_name = 'inventory/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum, Value, DecimalField, Count, F
        from django.db.models.functions import Coalesce

        # Total items
        active_items = Item.objects.filter(is_active=True)
        context['total_items'] = active_items.count()
        context['total_locations'] = Location.objects.filter(is_active=True).count()
        context['total_suppliers'] = Supplier.objects.count()

        # Low stock items (with transactions, below reorder point)
        low_stock_qs = active_items.filter(reorder_point__gt=0).annotate(
            current_qty_agg=Coalesce(
                Sum('inventory_transactions__quantity'),
                Value(0, output_field=DecimalField())
            ),
            tx_count=Count('inventory_transactions', distinct=True)
        ).filter(tx_count__gt=0, current_qty_agg__lt=F('reorder_point'))
        context['low_stock_items'] = low_stock_qs

        # Recent transactions (last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        context['recent_transactions'] = InventoryTransaction.objects.select_related(
            'item', 'location'
        ).filter(created_at__gte=seven_days_ago).order_by('-created_at')[:10]

        # Expiring soon (next 30 days)
        today = timezone.now().date()
        thirty_days_ahead = today + timedelta(days=30)
        context['expiring_soon'] = InventoryItem.objects.select_related(
            'item', 'location'
        ).filter(
            expiry_date__gte=today,
            expiry_date__lte=thirty_days_ahead
        ).order_by('expiry_date')

        return context


class FactoryDashboardView(LoginRequiredMixin, TemplateView):
    """Factory Management Dashboard view."""
    template_name = 'inventory/factory_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Low stock items
        active_items = Item.objects.filter(is_active=True)
        context['total_items'] = active_items.count()
        context['low_stock_items'] = sum(1 for item in active_items if item.is_below_reorder_point)
        
        # Category stats
        context['total_categories'] = Category.objects.filter(is_active=True).count()
        
        # Location stats
        context['total_locations'] = Location.objects.filter(is_active=True).count()
        
        # Recent items
        context['recent_items'] = Item.objects.filter(is_active=True).order_by('-created_at')[:5]
        
        # Recent transactions
        context['recent_transactions'] = InventoryTransaction.objects.select_related('item').order_by('-created_at')[:5]
        
        return context

# Category Views
class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'inventory/category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return Category.objects.all().order_by('name')

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('inventory:category-list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Category "{self.object.name}" created successfully.')
        return response

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('inventory:category-list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Category "{self.object.name}" updated successfully.')
        return response

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'inventory/category_confirm_delete.html'
    success_url = reverse_lazy('inventory:category-list')
    
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(request, 'Category deleted successfully.')
        return response

# Item Views
class ItemListView(LoginRequiredMixin, ListView):
    model = Item
    template_name = 'inventory/item_list.html'
    context_object_name = 'items'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Item.objects.select_related('category', 'unit_of_measure')
        
        # Apply filters
        search = self.request.GET.get('search', '')
        category = self.request.GET.get('category')
        item_type = self.request.GET.get('item_type')
        low_stock = self.request.GET.get('low_stock') == '1' or self.request.GET.get('status') == 'low_stock'

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(sku__iexact=search) |
                Q(barcode__iexact=search)
            )

        if category:
            queryset = queryset.filter(category_id=category)

        if item_type:
            queryset = queryset.filter(item_type=item_type)

        # Always annotate with current stock from transactions
        queryset = queryset.annotate(
            current_qty_agg=Coalesce(
                Sum('inventory_transactions__quantity'),
                Value(0, output_field=DecimalField())
            ),
            tx_count=Count('inventory_transactions', distinct=True)
        )

        if low_stock:
            # Only items with transactions whose stock dropped below reorder point
            queryset = queryset.filter(
                reorder_point__gt=0,
                tx_count__gt=0,
                current_qty_agg__lt=F('reorder_point')
            )

        # Filter items expiring within 30 days
        if self.request.GET.get('expiring_soon') == '1':
            from django.utils import timezone
            from datetime import timedelta
            thirty_days_ahead = timezone.now().date() + timedelta(days=30)
            queryset = queryset.filter(
                inventory_items__expiry_date__lte=thirty_days_ahead,
                inventory_items__expiry_date__gte=timezone.now().date()
            ).distinct()

        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['item_types'] = dict(Item.ITEM_TYPES)
        return context

class ItemDetailView(LoginRequiredMixin, DetailView):
    model = Item
    template_name = 'inventory/item_detail.html'
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        
        # Get current inventory levels by location
        context['inventory_by_location'] = InventoryItem.objects.filter(
            item=item,
            quantity__gt=0
        ).values(
            'location__name', 'location__id'
        ).annotate(
            total_quantity=Sum('quantity')
        ).order_by('location__name')
        
        # Get recent transactions
        context['recent_transactions'] = InventoryTransaction.objects.filter(
            item=item
        ).select_related('location').order_by('-created_at')[:10]
        
        return context

class ItemCreateView(LoginRequiredMixin, CreateView):
    model = Item
    form_class = ItemForm
    template_name = 'inventory/item_form.html'
    
    def form_valid(self, form):
        if getattr(self.request, 'user', None) and self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        else:
            form.instance.created_by = None
        response = super().form_valid(form)

        # Create opening stock transaction if initial quantity provided
        initial_qty = form.cleaned_data.get('initial_quantity') or 0
        initial_loc = form.cleaned_data.get('initial_location')
        if initial_qty > 0 and initial_loc:
            InventoryTransaction.objects.create(
                item=self.object,
                transaction_type='purchase',
                quantity=initial_qty,
                location=initial_loc,
                reference='OPENING-STOCK',
                notes='Opening stock on item creation',
                created_by=self.request.user if self.request.user.is_authenticated else None,
            )

        messages.success(self.request, f'Item "{self.object.name}" created successfully.')
        return response
    
    def get_success_url(self):
        return reverse_lazy('inventory:item-detail', kwargs={'pk': self.object.pk})

class ItemUpdateView(LoginRequiredMixin, UpdateView):
    model = Item
    form_class = ItemForm
    template_name = 'inventory/item_form.html'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Item "{self.object.name}" updated successfully.')
        return response
    
    def get_success_url(self):
        return reverse_lazy('inventory:item-detail', kwargs={'pk': self.object.pk})

@method_decorator(csrf_exempt, name='dispatch')
class ItemDeleteView(LoginRequiredMixin, DeleteView):
    model = Item
    template_name = 'inventory/item_confirm_delete.html'
    success_url = reverse_lazy('inventory:item-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction_count'] = self.get_object().inventory_transactions.count()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        item_name = self.object.name
        self.object.inventory_transactions.all().delete()
        self.object.delete()
        messages.success(request, f'Item "{item_name}" and all its transaction records deleted permanently.')
        return HttpResponseRedirect(self.success_url)


def item_delete_ajax(request, pk):
    """AJAX endpoint to delete an item directly."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse(
            {
                'success': False,
                'error': 'Authentication required',
                'login_url': reverse('login')
            },
            status=401
        )

    try:
        item = get_object_or_404(Item, pk=pk)
        name = item.name

        # Delete dependent records first
        item.inventory_transactions.all().delete()
        item.inventory_items.all().delete()

        item.delete()
        return JsonResponse({'success': True, 'message': f'"{name}" deleted successfully.'})
    except ProtectedError:
        return JsonResponse(
            {
                'success': False,
                'error': 'This item cannot be deleted because it is referenced by other records.'
            },
            status=409
        )
    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Location Views
class LocationListView(LoginRequiredMixin, ListView):
    model = Location
    template_name = 'inventory/location_list.html'
    context_object_name = 'locations'
    
    def get_queryset(self):
        return Location.objects.all().order_by('name')

class LocationDetailView(LoginRequiredMixin, DetailView):
    model = Location
    template_name = 'inventory/location_detail.html'
    context_object_name = 'location'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.get_object()
        
        # Get items in this location
        context['inventory_items'] = InventoryItem.objects.filter(
            location=location,
            quantity__gt=0
        ).select_related('item').order_by('item__name')
        
        # Get recent transactions
        context['recent_transactions'] = InventoryTransaction.objects.filter(
            location=location
        ).select_related('item').order_by('-created_at')[:10]
        
        return context

# Transaction Views
class TransactionListView(LoginRequiredMixin, ListView):
    model = InventoryTransaction
    template_name = 'inventory/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = InventoryTransaction.objects.select_related(
            'item', 'location'
        ).order_by('-created_at')
        
        # Apply filters
        item_id = self.request.GET.get('item')
        location_id = self.request.GET.get('location')
        transaction_type = self.request.GET.get('transaction_type')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if item_id:
            queryset = queryset.filter(item_id=item_id)
            
        if location_id:
            queryset = queryset.filter(location_id=location_id)
            
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
            
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
            
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        # Filter to last 7 days when coming from dashboard
        if self.request.GET.get('recent') == '1':
            from django.utils import timezone
            from datetime import timedelta
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=7))

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = Item.objects.all()
        context['locations'] = Location.objects.all()
        context['transaction_types'] = InventoryTransaction.TRANSACTION_TYPES
        return context

class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = InventoryTransaction
    form_class = InventoryTransactionForm
    template_name = 'inventory/transaction_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user = getattr(self.request, 'user', None)
        kwargs['user'] = user if user and user.is_authenticated else None
        return kwargs
    
    def form_valid(self, form):
        # Assign creator only if authenticated
        if getattr(self.request, 'user', None) and self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        else:
            form.instance.created_by = None
        response = super().form_valid(form)
        messages.success(self.request, 'Transaction recorded successfully.')
        return response
    
    def get_success_url(self):
        return reverse_lazy('inventory:transaction-list')

# Inventory Adjustment View
class InventoryAdjustmentView(LoginRequiredMixin, View):
    template_name = 'inventory/inventory_adjustment.html'
    
    def get(self, request, *args, **kwargs):
        form = InventoryAdjustmentForm(user=request.user if request.user.is_authenticated else None)
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = InventoryAdjustmentForm(request.POST, user=request.user if request.user.is_authenticated else None)
        
        if form.is_valid():
            item = form.cleaned_data['item']
            location = form.cleaned_data['location']
            adjustment_type = form.cleaned_data['adjustment_type']
            quantity = form.cleaned_data['quantity']
            reason = form.cleaned_data['reason']
            
            # Get or create inventory item
            inventory_item, created = InventoryItem.objects.get_or_create(
                item=item,
                location=location,
                defaults={'quantity': 0}
            )
            
            # Apply adjustment
            if adjustment_type == 'add':
                inventory_item.quantity += quantity
                transaction_type = 'adjustment_in'
                message = f'Added {quantity} {item.unit_of_measure.abbreviation} to inventory.'
            elif adjustment_type == 'remove':
                inventory_item.quantity -= quantity
                transaction_type = 'adjustment_out'
                message = f'Removed {quantity} {item.unit_of_measure.abbreviation} from inventory.'
            else:  # set
                old_quantity = inventory_item.quantity
                inventory_item.quantity = quantity
                transaction_type = 'adjustment_in' if quantity > old_quantity else 'adjustment_out'
                message = f'Set inventory level to {quantity} {item.unit_of_measure.abbreviation}.'
            
            # Save the inventory item
            inventory_item.save()
            
            # Create transaction record
            InventoryTransaction.objects.create(
                item=item,
                transaction_type=transaction_type,
                quantity=abs(quantity),
                location=location,
                reference=f'ADJ-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                notes=f'Adjustment: {reason}',
                created_by=request.user if request.user.is_authenticated else None
            )
            
            messages.success(request, message)
            return redirect('inventory:adjust-inventory')
        
        return render(request, self.template_name, {'form': form})

# API Views
class ItemAutocompleteView(LoginRequiredMixin, View):
    """API endpoint for item autocomplete."""
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        
        if not query:
            return JsonResponse({'results': []})
        
        items = Item.objects.filter(
            Q(name__icontains=query) |
            Q(sku__iexact=query) |
            Q(barcode__iexact=query)
        ).filter(is_active=True)[:10]
        
        results = [{
            'id': item.id,
            'text': f"{item.name} ({item.sku})",
            'sku': item.sku,
            'barcode': item.barcode,
            'unit': item.unit_of_measure.abbreviation if item.unit_of_measure else ''
        } for item in items]
        
        return JsonResponse({'results': results})

class InventoryLevelsView(LoginRequiredMixin, TemplateView):
    """View for checking inventory levels."""
    template_name = 'inventory/inventory_levels.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all active items with their current quantities
        items = Item.objects.filter(is_active=True).annotate(
            current_qty_agg=Coalesce(
                Sum('inventory_items__quantity'),
                Value(0, output_field=DecimalField())
            ),
            location_count=Count('inventory_items__location', distinct=True)
        ).select_related('category', 'unit_of_measure')
        
        # Apply filters
        category_id = self.request.GET.get('category')
        if category_id:
            items = items.filter(category_id=category_id)
        
        low_stock = self.request.GET.get('low_stock') == '1'
        if low_stock:
            items = items.filter(
                Q(current_qty_agg__lte=F('reorder_point')) |
                Q(current_qty_agg__isnull=True, reorder_point__gt=0)
            )
        
        # Add categories for filter dropdown
        context['categories'] = Category.objects.all()
        context['items'] = items.order_by('name')
        
        return context

# Export Views
class ExportInventoryView(LoginRequiredMixin, View):
    """Export inventory data to CSV/Excel."""
    def get(self, request, *args, **kwargs):
        import csv
        from django.http import HttpResponse
        
        # Create the HttpResponse object with the appropriate CSV header.
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventory_export.csv"'
        
        writer = csv.writer(response)
        
        # Write headers
        writer.writerow([
            'Item Name', 'SKU', 'Barcode', 'Category', 'Current Quantity',
            'Unit of Measure', 'Location', 'Last Updated'
        ])
        
        # Write data
        items = InventoryItem.objects.select_related(
            'item', 'item__category', 'item__unit_of_measure', 'location'
        ).filter(quantity__gt=0).order_by('item__name', 'location__name')
        
        for item in items:
            writer.writerow([
                item.item.name,
                item.item.sku or '',
                item.item.barcode or '',
                item.item.category.name if item.item.category else '',
                str(item.quantity),
                item.item.unit_of_measure.abbreviation if item.item.unit_of_measure else '',
                item.location.name,
                item.updated_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        return response


class InventoryAnalysisView(LoginRequiredMixin, TemplateView):
    """Inventory analysis dashboard — data embedded directly in template."""
    template_name = 'inventory/inventory_analysis.html'

    def get_context_data(self, **kwargs):
        import json
        from django.utils import timezone
        from datetime import timedelta

        context = super().get_context_data(**kwargs)
        category_filter = self.request.GET.get('category', '')
        type_filter = self.request.GET.get('item_type', '')

        context['categories'] = Category.objects.filter(is_active=True)
        context['item_types'] = Item.ITEM_TYPES
        context['selected_category'] = category_filter
        context['selected_type'] = type_filter

        # Base queryset with annotated current stock
        items_qs = Item.objects.filter(is_active=True).annotate(
            current_qty=Coalesce(
                Sum('inventory_transactions__quantity'),
                Value(0, output_field=DecimalField())
            )
        ).select_related('category', 'unit_of_measure')

        if category_filter:
            items_qs = items_qs.filter(category_id=category_filter)
        if type_filter:
            items_qs = items_qs.filter(item_type=type_filter)

        all_items = list(items_qs)

        def f(v):
            return round(float(v), 2) if v is not None else 0

        # 1. Stock by category
        cat_map = {}
        for item in all_items:
            cat = item.category.name if item.category else 'Uncategorized'
            cat_map.setdefault(cat, 0)
            cat_map[cat] += f(item.current_qty)
        cat_sorted = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)

        # 2. Item type distribution
        type_map = {}
        type_labels = {k: str(v) for k, v in Item.ITEM_TYPES}
        for item in all_items:
            label = type_labels.get(item.item_type, item.item_type)
            type_map[label] = type_map.get(label, 0) + 1

        # 3. Stock status
        status_counts = {'In Stock': 0, 'Low Stock': 0, 'Out of Stock': 0}
        for item in all_items:
            qty = f(item.current_qty)
            reorder = float(item.reorder_point) if item.reorder_point else 0
            if qty <= 0:
                status_counts['Out of Stock'] += 1
            elif reorder > 0 and qty < reorder:
                status_counts['Low Stock'] += 1
            else:
                status_counts['In Stock'] += 1

        # 4. Transactions by type (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        tx_qs = InventoryTransaction.objects.filter(created_at__gte=thirty_days_ago)
        if category_filter:
            tx_qs = tx_qs.filter(item__category_id=category_filter)
        if type_filter:
            tx_qs = tx_qs.filter(item__item_type=type_filter)

        tx_labels_map = {k: str(v) for k, v in InventoryTransaction.TRANSACTION_TYPES}
        tx_map = {}
        for row in tx_qs.values('transaction_type').annotate(count=Count('id')):
            label = tx_labels_map.get(row['transaction_type'], row['transaction_type'])
            tx_map[label] = row['count']

        # 5. Daily trend (last 14 days)
        fourteen_days_ago = timezone.now() - timedelta(days=14)
        daily_qs = (
            InventoryTransaction.objects
            .filter(created_at__gte=fourteen_days_ago)
            .extra(select={'day': "date(created_at)"})
            .values('day').annotate(count=Count('id')).order_by('day')
        )
        daily_labels = [str(r['day']) for r in daily_qs]
        daily_counts = [r['count'] for r in daily_qs]

        # 6. Top 10 items by stock
        top_items = sorted(all_items, key=lambda x: f(x.current_qty), reverse=True)[:10]

        chart_data = {
            'stock_by_category': {
                'labels': [c[0] for c in cat_sorted],
                'quantities': [c[1] for c in cat_sorted],
            },
            'item_type_distribution': {
                'labels': list(type_map.keys()),
                'counts': list(type_map.values()),
            },
            'stock_status': {
                'labels': list(status_counts.keys()),
                'counts': list(status_counts.values()),
            },
            'transaction_by_type': {
                'labels': list(tx_map.keys()),
                'counts': list(tx_map.values()),
            },
            'daily_trend': {
                'labels': daily_labels,
                'counts': daily_counts,
            },
            'top_items': {
                'labels': [i.name for i in top_items],
                'quantities': [f(i.current_qty) for i in top_items],
                'units': [i.unit_of_measure.abbreviation for i in top_items],
            },
        }

        context['chart_data_json'] = json.dumps(chart_data)
        return context


class InventoryAnalysisAPIView(LoginRequiredMixin, View):
    """JSON API for inventory analysis charts."""

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta

        category_filter = request.GET.get('category', '')
        type_filter = request.GET.get('item_type', '')

        items_qs = Item.objects.filter(is_active=True).annotate(
            current_qty=Coalesce(
                Sum('inventory_transactions__quantity'),
                Value(0, output_field=DecimalField())
            )
        )
        if category_filter:
            items_qs = items_qs.filter(category_id=category_filter)
        if type_filter:
            items_qs = items_qs.filter(item_type=type_filter)

        # 1. Stock level by category
        cat_data = (
            items_qs.values('category__name')
            .annotate(total_qty=Sum('current_qty'), item_count=Count('id'))
            .order_by('-total_qty')
        )

        # 2. Item type distribution
        type_data = (
            items_qs.values('item_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        type_labels = dict(Item.ITEM_TYPES)

        # 3. Stock status breakdown
        all_items = list(items_qs.select_related('category'))
        status_counts = {'In Stock': 0, 'Low Stock': 0, 'Out of Stock': 0}
        for item in all_items:
            qty = float(item.current_qty)
            reorder = float(item.reorder_point) if item.reorder_point else 0
            if qty <= 0:
                status_counts['Out of Stock'] += 1
            elif reorder > 0 and qty < reorder:
                status_counts['Low Stock'] += 1
            else:
                status_counts['In Stock'] += 1

        # 4. Transaction volume last 30 days by type
        thirty_days_ago = timezone.now() - timedelta(days=30)
        tx_qs = InventoryTransaction.objects.filter(created_at__gte=thirty_days_ago)
        if category_filter:
            tx_qs = tx_qs.filter(item__category_id=category_filter)
        if type_filter:
            tx_qs = tx_qs.filter(item__item_type=type_filter)

        tx_type_data = (
            tx_qs.values('transaction_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        tx_labels = dict(InventoryTransaction.TRANSACTION_TYPES)

        # 5. Daily transaction trend last 14 days
        fourteen_days_ago = timezone.now() - timedelta(days=14)
        daily_tx = (
            InventoryTransaction.objects
            .filter(created_at__gte=fourteen_days_ago)
            .extra(select={'day': "date(created_at)"})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        # 6. Top 10 items by current stock qty
        top_items = sorted(all_items, key=lambda x: float(x.current_qty), reverse=True)[:10]

        def f(v):
            return round(float(v), 2) if v is not None else 0

        return JsonResponse({
            'stock_by_category': {
                'labels': [d['category__name'] or 'Uncategorized' for d in cat_data],
                'quantities': [f(d['total_qty']) for d in cat_data],
                'counts': [d['item_count'] for d in cat_data],
            },
            'item_type_distribution': {
                'labels': [type_labels.get(d['item_type'], d['item_type']) for d in type_data],
                'counts': [d['count'] for d in type_data],
            },
            'stock_status': {
                'labels': list(status_counts.keys()),
                'counts': list(status_counts.values()),
            },
            'transaction_by_type': {
                'labels': [tx_labels.get(d['transaction_type'], d['transaction_type']) for d in tx_type_data],
                'counts': [d['count'] for d in tx_type_data],
            },
            'daily_trend': {
                'labels': [str(d['day']) for d in daily_tx],
                'counts': [d['count'] for d in daily_tx],
            },
            'top_items': {
                'labels': [i.name for i in top_items],
                'quantities': [f(i.current_qty) for i in top_items],
                'units': [i.unit_of_measure.abbreviation for i in top_items],
            },
        })
