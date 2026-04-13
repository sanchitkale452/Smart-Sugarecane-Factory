from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from farms.models import Farm
import json


class Machine(models.Model):
    """Model representing factory machines with performance tracking."""
    
    MACHINE_STATUS = (
        ('running', 'Running'),
        ('idle', 'Idle'),
        ('maintenance', 'Under Maintenance'),
        ('error', 'Error'),
        ('offline', 'Offline'),
    )
    
    MACHINE_TYPE = (
        ('crusher', 'Crusher'),
        ('boiler', 'Boiler'),
        ('evaporator', 'Evaporator'),
        ('centrifuge', 'Centrifuge'),
        ('dryer', 'Dryer'),
        ('packaging', 'Packaging'),
        ('other', 'Other'),
    )
    
    name = models.CharField(_('machine name'), max_length=100)
    machine_type = models.CharField(_('machine type'), max_length=20, choices=MACHINE_TYPE)
    model_number = models.CharField(_('model number'), max_length=50, blank=True)
    serial_number = models.CharField(_('serial number'), max_length=50, unique=True)
    location = models.CharField(_('location'), max_length=100)
    installation_date = models.DateField(_('installation date'))
    last_maintenance = models.DateField(_('last maintenance'), null=True, blank=True)
    next_maintenance_due = models.DateField(_('next maintenance due'), null=True, blank=True)
    
    # Performance metrics
    current_status = models.CharField(_('current status'), max_length=20, choices=MACHINE_STATUS, default='idle')
    efficiency_rating = models.DecimalField(_('efficiency rating'), max_digits=5, decimal_places=2, null=True, blank=True, help_text="Percentage (0-100)")
    operating_hours = models.DecimalField(_('operating hours'), max_digits=10, decimal_places=2, default=0.00)
    temperature = models.DecimalField(_('temperature'), max_digits=6, decimal_places=2, null=True, blank=True, help_text="Current temperature in Celsius")
    vibration_level = models.DecimalField(_('vibration level'), max_digits=6, decimal_places=2, null=True, blank=True, help_text="Vibration level in Hz")
    power_consumption = models.DecimalField(_('power consumption'), max_digits=8, decimal_places=2, null=True, blank=True, help_text="Power consumption in kW")
    
    # Health indicators
    is_healthy = models.BooleanField(_('is healthy'), default=True)
    health_score = models.DecimalField(_('health score'), max_digits=5, decimal_places=2, default=100.00, help_text="Overall health score (0-100)")
    last_health_check = models.DateTimeField(_('last health check'), auto_now=True)
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('Machine')
        verbose_name_plural = _('Machines')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_machine_type_display()})"
    
    def analyze_health(self):
        """Analyze machine health based on current metrics."""
        health_issues = []
        score = 100.0
        
        # Check temperature
        if self.temperature:
            if self.temperature > 80:  # High temperature threshold
                health_issues.append("High temperature")
                score -= 20
            elif self.temperature > 60:
                health_issues.append("Elevated temperature")
                score -= 10
        
        # Check vibration
        if self.vibration_level:
            if self.vibration_level > 50:  # High vibration threshold
                health_issues.append("High vibration")
                score -= 25
            elif self.vibration_level > 30:
                health_issues.append("Elevated vibration")
                score -= 15
        
        # Check efficiency
        if self.efficiency_rating:
            if self.efficiency_rating < 70:
                health_issues.append("Low efficiency")
                score -= 20
            elif self.efficiency_rating < 85:
                health_issues.append("Reduced efficiency")
                score -= 10
        
        # Check maintenance due
        if self.next_maintenance_due:
            days_until_maintenance = (self.next_maintenance_due - timezone.now().date()).days
            if days_until_maintenance < 0:
                health_issues.append("Maintenance overdue")
                score -= 30
            elif days_until_maintenance < 7:
                health_issues.append("Maintenance due soon")
                score -= 15
        
        # Update health status
        self.health_score = max(0, score)
        self.is_healthy = score >= 70
        self.last_health_check = timezone.now()
        
        return {
            'is_healthy': self.is_healthy,
            'health_score': self.health_score,
            'issues': health_issues,
            'status': 'Good' if score >= 90 else 'Fair' if score >= 70 else 'Poor'
        }
    
    @property
    def status_color(self):
        """Return color based on machine status."""
        colors = {
            'running': 'success',
            'idle': 'secondary',
            'maintenance': 'warning',
            'error': 'danger',
            'offline': 'dark'
        }
        return colors.get(self.current_status, 'secondary')
    
    @property
    def health_color(self):
        """Return color based on health score."""
        if self.health_score >= 90:
            return 'success'
        elif self.health_score >= 70:
            return 'warning'
        else:
            return 'danger'


class MachineReading(models.Model):
    """Model for storing real-time machine readings."""
    
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='readings')
    timestamp = models.DateTimeField(_('timestamp'), auto_now_add=True)
    temperature = models.DecimalField(_('temperature'), max_digits=6, decimal_places=2, null=True, blank=True)
    vibration = models.DecimalField(_('vibration'), max_digits=6, decimal_places=2, null=True, blank=True)
    power_consumption = models.DecimalField(_('power consumption'), max_digits=8, decimal_places=2, null=True, blank=True)
    production_rate = models.DecimalField(_('production rate'), max_digits=8, decimal_places=2, null=True, blank=True)
    error_code = models.CharField(_('error code'), max_length=20, blank=True)
    is_anomaly = models.BooleanField(_('is anomaly'), default=False)
    
    class Meta:
        verbose_name = _('Machine Reading')
        verbose_name_plural = _('Machine Readings')
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.machine.name} - {self.timestamp}"


class ProductionBatch(models.Model):
    """Model representing a production batch in the factory."""
    BATCH_STATUS = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    )
    
    batch_number = models.CharField(_('batch number'), max_length=50, unique=True)
    farm = models.ForeignKey(
        Farm,
        on_delete=models.PROTECT,
        related_name='production_batches',
        verbose_name=_('source farm')
    )
    start_date = models.DateTimeField(_('start date'), auto_now_add=True)
    end_date = models.DateTimeField(_('end date'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=BATCH_STATUS,
        default='pending'
    )
    expected_yield = models.DecimalField(
        _('expected yield (kg)'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    actual_yield = models.DecimalField(
        _('actual yield (kg)'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_batches',
        verbose_name=_('created by')
    )
    last_updated = models.DateTimeField(_('last updated'), auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = _('production batch')
        verbose_name_plural = _('production batches')
    
    def __str__(self):
        return f"Batch {self.batch_number} - {self.get_status_display()}"
    
    @property
    def duration(self):
        """Calculate the duration of the production batch."""
        if self.end_date:
            return self.end_date - self.start_date
        return timezone.now() - self.start_date

class ProductionStage(models.Model):
    """Model representing a stage in the production process."""
    STAGE_TYPES = (
        ('harvesting', 'Harvesting'),
        ('cleaning', 'Cleaning'),
        ('crushing', 'Crushing'),
        ('juice_extraction', 'Juice Extraction'),
        ('clarification', 'Clarification'),
        ('evaporation', 'Evaporation'),
        ('crystallization', 'Crystallization'),
        ('centrifugation', 'Centrifugation'),
        ('drying', 'Drying'),
        ('packaging', 'Packaging'),
    )
    
    name = models.CharField(_('stage name'), max_length=100)
    stage_type = models.CharField(
        _('stage type'),
        max_length=20,
        choices=STAGE_TYPES,
        unique=True
    )
    description = models.TextField(_('description'), blank=True)
    standard_duration = models.DurationField(
        _('standard duration'),
        null=True,
        blank=True,
        help_text=_('Expected duration for this stage (HH:MM:SS)')
    )
    is_active = models.BooleanField(_('is active'), default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = _('production stage')
        verbose_name_plural = _('production stages')
    
    def __str__(self):
        return self.name

class BatchStage(models.Model):
    """Model representing a stage in a specific production batch."""
    batch = models.ForeignKey(
        ProductionBatch,
        on_delete=models.CASCADE,
        related_name='batch_stages',
        verbose_name=_('production batch')
    )
    stage = models.ForeignKey(
        ProductionStage,
        on_delete=models.PROTECT,
        related_name='batch_instances',
        verbose_name=_('production stage')
    )
    start_time = models.DateTimeField(_('start time'))
    end_time = models.DateTimeField(_('end time'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=(
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('skipped', 'Skipped'),
        ),
        default='pending'
    )
    notes = models.TextField(_('notes'), blank=True)
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='supervised_stages',
        verbose_name=_('supervisor')
    )
    
    class Meta:
        ordering = ['batch', 'start_time']
        verbose_name = _('batch stage')
        verbose_name_plural = _('batch stages')
        unique_together = ('batch', 'stage')
    
    def __str__(self):
        return f"{self.batch} - {self.stage}"
    
    @property
    def duration(self):
        """Calculate the duration of this stage."""
        if self.end_time:
            return self.end_time - self.start_time
        return timezone.now() - self.start_time

class ProductionOutput(models.Model):
    """Model representing the output from a production batch."""
    OUTPUT_TYPES = (
        ('raw_juice', 'Raw Juice'),
        ('clarified_juice', 'Clarified Juice'),
        ('syrup', 'Syrup'),
        ('molasses', 'Molasses'),
        ('raw_sugar', 'Raw Sugar'),
        ('refined_sugar', 'Refined Sugar'),
        ('bagasse', 'Bagasse'),
        ('filter_cake', 'Filter Cake'),
    )
    
    batch = models.ForeignKey(
        ProductionBatch,
        on_delete=models.CASCADE,
        related_name='outputs',
        verbose_name=_('production batch')
    )
    output_type = models.CharField(
        _('output type'),
        max_length=20,
        choices=OUTPUT_TYPES
    )
    quantity = models.DecimalField(
        _('quantity'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Quantity in kilograms')
    )
    quality_rating = models.PositiveSmallIntegerField(
        _('quality rating'),
        null=True,
        blank=True,
        help_text=_('Quality rating from 1 to 10')
    )
    notes = models.TextField(_('notes'), blank=True)
    recorded_at = models.DateTimeField(_('recorded at'), auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_outputs',
        verbose_name=_('recorded by')
    )
    
    class Meta:
        ordering = ['-recorded_at']
        verbose_name = _('production output')
        verbose_name_plural = _('production outputs')
    
    def __str__(self):
        return f"{self.get_output_type_display()} - {self.quantity}kg"


class CrushingMachine(models.Model):
    """Model representing a crushing machine in the factory."""
    MACHINE_STATUS = (
        ('operational', 'Operational'),
        ('maintenance', 'Under Maintenance'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    )
    
    machine_id = models.CharField(_('machine ID'), max_length=50, unique=True)
    name = models.CharField(_('machine name'), max_length=100)
    model = models.CharField(_('model'), max_length=100, blank=True)
    manufacturer = models.CharField(_('manufacturer'), max_length=100, blank=True)
    installation_date = models.DateField(_('installation date'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=MACHINE_STATUS,
        default='operational'
    )
    last_maintenance = models.DateTimeField(_('last maintenance'), null=True, blank=True)
    next_maintenance = models.DateTimeField(_('next maintenance'), null=True, blank=True)
    notes = models.TextField(_('notes'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)
    
    # Optimal operating parameters
    optimal_pressure = models.DecimalField(
        _('optimal pressure (bar)'),
        max_digits=6,
        decimal_places=2,
        default=100.0
    )
    optimal_temperature = models.DecimalField(
        _('optimal temperature (°C)'),
        max_digits=5,
        decimal_places=2,
        default=30.0
    )
    optimal_rotation_speed = models.DecimalField(
        _('optimal rotation speed (RPM)'),
        max_digits=6,
        decimal_places=2,
        default=15.0
    )
    
    class Meta:
        ordering = ['machine_id']
        verbose_name = _('crushing machine')
        verbose_name_plural = _('crushing machines')
    
    def __str__(self):
        return f"{self.machine_id} - {self.name}"


class SensorReading(models.Model):
    """Model for storing real-time sensor data from crushing machines."""
    machine = models.ForeignKey(
        CrushingMachine,
        on_delete=models.CASCADE,
        related_name='sensor_readings',
        verbose_name=_('machine')
    )
    batch = models.ForeignKey(
        ProductionBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sensor_readings',
        verbose_name=_('production batch')
    )
    timestamp = models.DateTimeField(_('timestamp'), default=timezone.now, db_index=True)
    
    # Sensor measurements
    pressure = models.DecimalField(
        _('pressure (bar)'),
        max_digits=6,
        decimal_places=2,
        help_text=_('Hydraulic pressure in crushing rollers')
    )
    temperature = models.DecimalField(
        _('temperature (°C)'),
        max_digits=5,
        decimal_places=2,
        help_text=_('Operating temperature')
    )
    rotation_speed = models.DecimalField(
        _('rotation speed (RPM)'),
        max_digits=6,
        decimal_places=2,
        help_text=_('Roller rotation speed')
    )
    torque = models.DecimalField(
        _('torque (Nm)'),
        max_digits=8,
        decimal_places=2,
        help_text=_('Motor torque')
    )
    vibration = models.DecimalField(
        _('vibration (mm/s)'),
        max_digits=6,
        decimal_places=2,
        help_text=_('Vibration level')
    )
    power_consumption = models.DecimalField(
        _('power consumption (kW)'),
        max_digits=8,
        decimal_places=2,
        help_text=_('Electrical power consumption')
    )
    feed_rate = models.DecimalField(
        _('feed rate (tons/hour)'),
        max_digits=6,
        decimal_places=2,
        help_text=_('Sugarcane feed rate')
    )
    moisture_content = models.DecimalField(
        _('moisture content (%)'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Moisture content in cane')
    )
    brix_level = models.DecimalField(
        _('brix level (%)'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Sugar content in juice')
    )
    
    # Calculated/derived values
    extraction_rate = models.DecimalField(
        _('extraction rate (%)'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Juice extraction efficiency')
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('sensor reading')
        verbose_name_plural = _('sensor readings')
        indexes = [
            models.Index(fields=['machine', '-timestamp']),
            models.Index(fields=['batch', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.machine.machine_id} - {self.timestamp}"


class AnomalyAlert(models.Model):
    """Model for storing detected anomalies and alerts."""
    SEVERITY_LEVELS = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    ALERT_STATUS = (
        ('open', 'Open'),
        ('acknowledged', 'Acknowledged'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    )
    
    machine = models.ForeignKey(
        CrushingMachine,
        on_delete=models.CASCADE,
        related_name='anomaly_alerts',
        verbose_name=_('machine')
    )
    sensor_reading = models.ForeignKey(
        SensorReading,
        on_delete=models.CASCADE,
        related_name='anomaly_alerts',
        verbose_name=_('sensor reading')
    )
    detected_at = models.DateTimeField(_('detected at'), default=timezone.now, db_index=True)
    severity = models.CharField(
        _('severity'),
        max_length=20,
        choices=SEVERITY_LEVELS
    )
    anomaly_score = models.DecimalField(
        _('anomaly score'),
        max_digits=6,
        decimal_places=4,
        help_text=_('ML model anomaly score')
    )
    description = models.TextField(_('description'))
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=ALERT_STATUS,
        default='open'
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts',
        verbose_name=_('acknowledged by')
    )
    acknowledged_at = models.DateTimeField(_('acknowledged at'), null=True, blank=True)
    resolved_at = models.DateTimeField(_('resolved at'), null=True, blank=True)
    resolution_notes = models.TextField(_('resolution notes'), blank=True)
    
    class Meta:
        ordering = ['-detected_at']
        verbose_name = _('anomaly alert')
        verbose_name_plural = _('anomaly alerts')
        indexes = [
            models.Index(fields=['machine', '-detected_at']),
            models.Index(fields=['status', '-detected_at']),
        ]
    
    def __str__(self):
        return f"{self.machine.machine_id} - {self.get_severity_display()} - {self.detected_at}"


class OptimizationRecommendation(models.Model):
    """Model for storing AI-generated optimization recommendations."""
    machine = models.ForeignKey(
        CrushingMachine,
        on_delete=models.CASCADE,
        related_name='optimization_recommendations',
        verbose_name=_('machine')
    )
    batch = models.ForeignKey(
        ProductionBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='optimization_recommendations',
        verbose_name=_('production batch')
    )
    created_at = models.DateTimeField(_('created at'), default=timezone.now, db_index=True)
    
    # Current parameters
    current_pressure = models.DecimalField(_('current pressure'), max_digits=6, decimal_places=2)
    current_temperature = models.DecimalField(_('current temperature'), max_digits=5, decimal_places=2)
    current_rotation_speed = models.DecimalField(_('current rotation speed'), max_digits=6, decimal_places=2)
    current_feed_rate = models.DecimalField(_('current feed rate'), max_digits=6, decimal_places=2)
    current_yield = models.DecimalField(_('current yield'), max_digits=8, decimal_places=2)
    
    # Recommended parameters
    recommended_pressure = models.DecimalField(_('recommended pressure'), max_digits=6, decimal_places=2)
    recommended_temperature = models.DecimalField(_('recommended temperature'), max_digits=5, decimal_places=2)
    recommended_rotation_speed = models.DecimalField(_('recommended rotation speed'), max_digits=6, decimal_places=2)
    recommended_feed_rate = models.DecimalField(_('recommended feed rate'), max_digits=6, decimal_places=2)
    expected_yield = models.DecimalField(_('expected yield'), max_digits=8, decimal_places=2)
    
    # Improvement metrics
    expected_improvement = models.DecimalField(
        _('expected improvement (%)'),
        max_digits=5,
        decimal_places=2
    )
    confidence_score = models.DecimalField(
        _('confidence score'),
        max_digits=4,
        decimal_places=2,
        help_text=_('ML model confidence (0-100)')
    )
    
    # Implementation status
    is_applied = models.BooleanField(_('is applied'), default=False)
    applied_at = models.DateTimeField(_('applied at'), null=True, blank=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_recommendations',
        verbose_name=_('applied by')
    )
    actual_yield = models.DecimalField(
        _('actual yield'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Actual yield after applying recommendation')
    )
    notes = models.TextField(_('notes'), blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('optimization recommendation')
        verbose_name_plural = _('optimization recommendations')
        indexes = [
            models.Index(fields=['machine', '-created_at']),
            models.Index(fields=['is_applied', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.machine.machine_id} - {self.created_at} - {self.expected_improvement}% improvement"
