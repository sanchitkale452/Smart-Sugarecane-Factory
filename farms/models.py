from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Farm(models.Model):
    """Model representing a sugarcane farm."""
    FARM_STATUS = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
    )
    
    SOIL_TYPES = (
        ('clay', 'Clay'),
        ('sandy', 'Sandy'),
        ('loamy', 'Loamy'),
        ('silty', 'Silty'),
        ('peaty', 'Peaty'),
        ('chalky', 'Chalky'),
    )
    
    name = models.CharField(_('farm name'), max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farms_owned'
    )
    location = models.CharField(_('location'), max_length=255)
    area = models.DecimalField(_('area (acres)'), max_digits=10, decimal_places=2)
    soil_type = models.CharField(_('soil type'), max_length=20, choices=SOIL_TYPES)
    status = models.CharField(_('status'), max_length=20, choices=FARM_STATUS, default='active')
    description = models.TextField(_('description'), blank=True)
    date_acquired = models.DateField(_('date acquired'), auto_now_add=True)
    last_updated = models.DateTimeField(_('last updated'), auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = _('farm')
        verbose_name_plural = _('farms')
    
    def __str__(self):
        return f"{self.name} ({self.location}) - {self.area} acres"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('farms:farm-detail', kwargs={'pk': self.pk})

class FarmCropCycle(models.Model):
    """Model representing a crop cycle for a farm."""
    CROP_STAGES = (
        ('preparation', 'Land Preparation'),
        ('planting', 'Planting'),
        ('growing', 'Growing'),
        ('mature', 'Mature'),
        ('harvested', 'Harvested'),
        ('fallow', 'Fallow'),
    )
    
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name='crop_cycles'
    )
    variety = models.CharField(_('sugarcane variety'), max_length=100)
    planting_date = models.DateField(_('planting date'))
    expected_harvest_date = models.DateField(_('expected harvest date'))
    actual_harvest_date = models.DateField(_('actual harvest date'), null=True, blank=True)
    current_stage = models.CharField(
        _('current stage'),
        max_length=20,
        choices=CROP_STAGES,
        default='preparation'
    )
    estimated_yield = models.DecimalField(
        _('estimated yield (tons)'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    actual_yield = models.DecimalField(
        _('actual yield (tons)'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    notes = models.TextField(_('notes'), blank=True)
    
    class Meta:
        ordering = ['-planting_date']
        verbose_name = _('crop cycle')
        verbose_name_plural = _('crop cycles')
    
    def __str__(self):
        return f"{self.farm.name} - {self.variety} ({self.get_current_stage_display()})"

class FarmActivity(models.Model):
    """Model representing activities performed on a farm."""
    ACTIVITY_TYPES = (
        ('plowing', 'Plowing'),
        ('planting', 'Planting'),
        ('fertilizing', 'Fertilizing'),
        ('irrigation', 'Irrigation'),
        ('pest_control', 'Pest Control'),
        ('harvesting', 'Harvesting'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    )
    
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(
        _('activity type'),
        max_length=20,
        choices=ACTIVITY_TYPES
    )
    date = models.DateField(_('date'))
    description = models.TextField(_('description'))
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='farm_activities'
    )
    cost = models.DecimalField(
        _('cost'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = _('farm activity')
        verbose_name_plural = _('farm activities')
    
    def __str__(self):
        return f"{self.get_activity_type_display()} at {self.farm.name} on {self.date}"


class Farmer(models.Model):
    """Farmer registration and profile information."""
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farmer_profile'
    )
    full_name = models.CharField(_('full name'), max_length=200)
    email = models.EmailField(_('email'), unique=True)
    mobile_number = models.CharField(_('mobile number'), max_length=20, blank=True)
    gender = models.CharField(_('gender'), max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    address = models.TextField(_('address'), blank=True)
    village = models.CharField(_('village'), max_length=100, blank=True)
    district = models.CharField(_('district'), max_length=100, blank=True)
    state = models.CharField(_('state'), max_length=100, blank=True)
    pin_code = models.CharField(_('PIN code'), max_length=10, blank=True)
    
    # Bank Details
    bank_name = models.CharField(_('bank name'), max_length=200, blank=True)
    bank_account_number = models.CharField(_('bank account number'), max_length=50, blank=True)
    bank_ifsc_code = models.CharField(_('bank IFSC code'), max_length=20, blank=True)
    bank_branch = models.CharField(_('bank branch'), max_length=200, blank=True)
    
    # Farm Details
    total_land_area = models.DecimalField(
        _('total land area (acres)'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total land area in acres"
    )
    land_holding_type = models.CharField(
        _('land holding type'),
        max_length=100,
        blank=True,
        help_text="e.g., Owned, Leased, Shared"
    )
    
    is_verified = models.BooleanField(_('is verified'), default=False)
    is_active = models.BooleanField(_('is active'), default=True)
    registration_date = models.DateTimeField(_('registration date'), auto_now_add=True)
    last_updated = models.DateTimeField(_('last updated'), auto_now=True)
    
    class Meta:
        verbose_name = _("Farmer")
        verbose_name_plural = _("Farmers")
        ordering = ['-registration_date']
    
    def __str__(self):
        return f"{self.full_name} ({self.email})"
    
    @property
    def age(self):
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
