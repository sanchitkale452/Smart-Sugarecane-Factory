from django import forms
from django.forms import ModelForm, DateInput
from .models import Farm, FarmCropCycle, FarmActivity
from django.utils import timezone

class FarmForm(ModelForm):
    """Form for creating and updating farms."""
    class Meta:
        model = Farm
        fields = [
            'name', 'owner', 'location', 'area', 'soil_type', 
            'status', 'description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['owner'].empty_label = "Select owner"
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

class FarmCropCycleForm(ModelForm):
    """Form for managing farm crop cycles."""
    class Meta:
        model = FarmCropCycle
        fields = [
            'farm', 'variety', 'planting_date', 'expected_harvest_date',
            'actual_harvest_date', 'current_stage', 'estimated_yield',
            'actual_yield', 'notes'
        ]
        widgets = {
            'planting_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_harvest_date': forms.DateInput(attrs={'type': 'date'}),
            'actual_harvest_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
    
    def clean(self):
        cleaned_data = super().clean()
        planting_date = cleaned_data.get('planting_date')
        expected_harvest_date = cleaned_data.get('expected_harvest_date')
        actual_harvest_date = cleaned_data.get('actual_harvest_date')
        
        if planting_date and expected_harvest_date and planting_date >= expected_harvest_date:
            raise forms.ValidationError("Expected harvest date must be after planting date.")
            
        if actual_harvest_date:
            if planting_date and actual_harvest_date < planting_date:
                raise forms.ValidationError("Actual harvest date cannot be before planting date.")
        
        return cleaned_data

class FarmActivityForm(ModelForm):
    """Form for recording farm activities."""
    class Meta:
        model = FarmActivity
        fields = [
            'farm', 'activity_type', 'date', 'description',
            'performed_by', 'cost', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['performed_by'].empty_label = "Select user"
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
    
    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date > timezone.now().date():
            raise forms.ValidationError("Activity date cannot be in the future.")
        return date
