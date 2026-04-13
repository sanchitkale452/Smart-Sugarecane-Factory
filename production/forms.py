from django import forms
from django.forms import ModelForm, DateTimeInput, Textarea
from .models import ProductionBatch, ProductionStage, BatchStage, ProductionOutput
from django.utils import timezone
from django.core.exceptions import ValidationError

class ProductionBatchForm(ModelForm):
    """Form for creating and updating production batches."""
    class Meta:
        model = ProductionBatch
        fields = [
            'batch_number', 'farm', 'end_date', 'status',
            'expected_yield', 'actual_yield', 'notes'
        ]
        widgets = {
            'end_date': DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'notes': Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['batch_number'].widget.attrs.update({'class': 'form-control'})
        self.fields['farm'].widget.attrs.update({'class': 'form-select'})
        self.fields['status'].widget.attrs.update({'class': 'form-select'})
        
        # Set initial datetime to now if creating a new batch
        if not self.instance.pk:
            self.fields['start_date'].initial = timezone.now()
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        expected_yield = cleaned_data.get('expected_yield')
        actual_yield = cleaned_data.get('actual_yield')
        
        if end_date and start_date and end_date < start_date:
            self.add_error('end_date', 'End date cannot be before start date.')
        
        if actual_yield and expected_yield and actual_yield > expected_yield * 1.5:
            # Allow up to 50% more than expected, but require a note
            if not cleaned_data.get('notes'):
                self.add_error('notes', 'Please explain why the actual yield is significantly higher than expected.')
        
        return cleaned_data

class ProductionStageForm(ModelForm):
    """Form for creating and updating production stages."""
    class Meta:
        model = ProductionStage
        fields = ['name', 'stage_type', 'description', 'standard_duration', 'is_active']
        widgets = {
            'description': Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'is_active':
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-check-input'})

class BatchStageForm(ModelForm):
    """Form for creating and updating batch stages."""
    class Meta:
        model = BatchStage
        fields = ['batch', 'stage', 'start_time', 'end_time', 'status', 'notes', 'supervisor']
        widgets = {
            'start_time': DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_time': DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'notes': Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'notes':
                field.widget.attrs.update({'class': 'form-control'})
        
        # Set initial start time to now if creating a new batch stage
        if not self.instance.pk:
            self.initial['start_time'] = timezone.now()
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if end_time and start_time and end_time < start_time:
            self.add_error('end_time', 'End time cannot be before start time.')
        
        return cleaned_data

class ProductionOutputForm(ModelForm):
    """Form for recording production outputs."""
    class Meta:
        model = ProductionOutput
        fields = ['batch', 'output_type', 'quantity', 'quality_rating', 'notes']
        widgets = {
            'notes': Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity and quantity <= 0:
            raise ValidationError('Quantity must be greater than zero.')
        return quantity
    
    def clean_quality_rating(self):
        rating = self.cleaned_data.get('quality_rating')
        if rating and (rating < 1 or rating > 10):
            raise ValidationError('Quality rating must be between 1 and 10.')
        return rating
