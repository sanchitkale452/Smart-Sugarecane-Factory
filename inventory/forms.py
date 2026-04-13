from django import forms
from django.forms import ModelForm, inlineformset_factory
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum

from .models import (
    Category, UnitOfMeasure, Item, Location, 
    InventoryTransaction, InventoryItem, Supplier
)

class CategoryForm(ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'parent', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude the current instance from parent choices to avoid circular references
        if self.instance.pk:
            self.fields['parent'].queryset = Category.objects.exclude(pk=self.instance.pk)

class UnitOfMeasureForm(ModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = ['name', 'abbreviation', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

class ItemForm(ModelForm):
    # Optional initial stock when creating a new item
    initial_quantity = forms.DecimalField(
        max_digits=12, decimal_places=3, min_value=0,
        required=False, initial=0,
        label='Initial Stock Quantity',
        help_text='Enter opening stock. Leave 0 to add stock later via transactions.'
    )
    initial_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        label='Initial Stock Location',
        help_text='Required if initial quantity is greater than 0.'
    )

    class Meta:
        model = Item
        fields = [
            'name', 'sku', 'barcode', 'description', 'category', 'item_type', 'unit_of_measure',
            'min_quantity', 'max_quantity', 'reorder_point', 'is_serialized',
            'is_lot_tracked', 'is_active', 'notes'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        min_qty = cleaned_data.get('min_quantity')
        max_qty = cleaned_data.get('max_quantity')
        reorder = cleaned_data.get('reorder_point')
        initial_qty = cleaned_data.get('initial_quantity') or 0
        initial_loc = cleaned_data.get('initial_location')

        if min_qty is not None and max_qty is not None and min_qty > max_qty:
            self.add_error('min_quantity', 'Minimum quantity cannot be greater than maximum quantity.')

        if reorder is not None and min_qty is not None and reorder < min_qty:
            self.add_error('reorder_point', 'Reorder point should be greater than or equal to minimum quantity.')

        if initial_qty > 0 and not initial_loc:
            self.add_error('initial_location', 'Please select a location for the initial stock.')

        return cleaned_data

class LocationForm(ModelForm):
    class Meta:
        model = Location
        fields = [
            'name', 'code', 'location_type', 'parent', 'description',
            'is_active', 'address', 'max_capacity', 'notes'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude the current instance from parent choices to avoid circular references
        if self.instance.pk:
            self.fields['parent'].queryset = Location.objects.exclude(pk=self.instance.pk)

class InventoryTransactionForm(ModelForm):
    class Meta:
        model = InventoryTransaction
        fields = [
            'item', 'transaction_type', 'quantity', 'unit_cost',
            'location', 'reference', 'notes'
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
            'transaction_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = Item.objects.filter(is_active=True)
        self.fields['location'].queryset = Location.objects.filter(is_active=True)
        
        # Set default transaction date to now
        if not self.instance.pk:
            self.initial['transaction_date'] = timezone.now()
    
    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        quantity = cleaned_data.get('quantity')
        transaction_type = cleaned_data.get('transaction_type')
        location = cleaned_data.get('location')
        
        if not all([item, quantity, transaction_type, location]):
            return cleaned_data
        
        # Check for negative quantities on outgoing transactions
        if transaction_type in ['sale', 'transfer_out', 'consumption', 'scrap']:
            # Get current quantity in the location
            current_qty = InventoryItem.objects.filter(
                item=item,
                location=location
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            if quantity > current_qty:
                self.add_error(
                    'quantity',
                    f'Not enough stock. Only {current_qty} available in {location}.'
                )
        
        return cleaned_data

class InventoryItemForm(ModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            'item', 'serial_number', 'lot_number', 'quantity', 'location',
            'expiry_date', 'manufactured_date', 'purchase_date',
            'purchase_price', 'supplier', 'notes'
        ]
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'manufactured_date': forms.DateInput(attrs={'type': 'date'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = Item.objects.filter(is_active=True)
        self.fields['location'].queryset = Location.objects.filter(is_active=True)
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
        
        # Set initial values for dates if not set
        if not self.instance.pk:
            self.initial['purchase_date'] = timezone.now().date()
    
    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        serial_number = cleaned_data.get('serial_number')
        lot_number = cleaned_data.get('lot_number')
        
        if not item:
            return cleaned_data
        
        # Validate serial number for serialized items
        if item.is_serialized and not serial_number:
            self.add_error('serial_number', 'Serial number is required for this item.')
        
        # Validate lot number for lot-tracked items
        if item.is_lot_tracked and not lot_number:
            self.add_error('lot_number', 'Lot number is required for this item.')
        
        # Validate quantity for serialized items
        if item.is_serialized and cleaned_data.get('quantity', 0) != 1:
            self.add_error('quantity', 'Quantity must be 1 for serialized items.')
        
        # Validate expiry date
        manufactured_date = cleaned_data.get('manufactured_date')
        expiry_date = cleaned_data.get('expiry_date')
        
        if manufactured_date and expiry_date and expiry_date < manufactured_date:
            self.add_error('expiry_date', 'Expiry date cannot be before manufactured date.')
        
        return cleaned_data

class SupplierForm(ModelForm):
    class Meta:
        model = Supplier
        fields = [
            'name', 'contact_person', 'email', 'phone', 'address',
            'tax_id', 'website', 'payment_terms', 'notes', 'is_active'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'payment_terms': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

# Formset for bulk item creation
InventoryItemFormSet = inlineformset_factory(
    Item, InventoryItem, 
    form=InventoryItemForm,
    fields=('location', 'quantity', 'serial_number', 'lot_number', 'expiry_date'),
    extra=1,
    can_delete=False
)

# Form for inventory adjustments
class InventoryAdjustmentForm(forms.Form):
    item = forms.ModelChoiceField(queryset=Item.objects.filter(is_active=True))
    location = forms.ModelChoiceField(queryset=Location.objects.filter(is_active=True))
    adjustment_type = forms.ChoiceField(choices=[
        ('add', 'Add to Inventory'),
        ('remove', 'Remove from Inventory'),
        ('set', 'Set Exact Quantity')
    ])
    quantity = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = Item.objects.filter(is_active=True)
        self.fields['location'].queryset = Location.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        location = cleaned_data.get('location')
        adjustment_type = cleaned_data.get('adjustment_type')
        quantity = cleaned_data.get('quantity')
        
        if not all([item, location, adjustment_type, quantity]):
            return cleaned_data
        
        # Check if we're removing more than available
        if adjustment_type == 'remove':
            current_qty = InventoryItem.objects.filter(
                item=item,
                location=location
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            if quantity > current_qty:
                self.add_error(
                    'quantity',
                    f'Cannot remove {quantity} items. Only {current_qty} available in {location}.'
                )
        
        return cleaned_data
