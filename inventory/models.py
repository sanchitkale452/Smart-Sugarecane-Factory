from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

class Category(models.Model):
    """Model representing an inventory category."""
    name = models.CharField(_('name'), max_length=100, unique=True)
    description = models.TextField(_('description'), blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories',
        verbose_name=_('parent category')
    )
    is_active = models.BooleanField(_('is active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def full_path(self):
        """Return the full category path as a string."""
        path = [self.name]
        parent = self.parent
        while parent is not None:
            path.insert(0, parent.name)
            parent = parent.parent
        return ' > '.join(path)

class UnitOfMeasure(models.Model):
    """Model representing units of measure for inventory items."""
    name = models.CharField(_('name'), max_length=50, unique=True)
    abbreviation = models.CharField(_('abbreviation'), max_length=10, unique=True)
    description = models.TextField(_('description'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)

    class Meta:
        verbose_name = _('unit of measure')
        verbose_name_plural = _('units of measure')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

class Item(models.Model):
    """Model representing an inventory item."""
    ITEM_TYPES = (
        ('raw_material', _('Raw Material')),
        ('finished_good', _('Finished Good')),
        ('consumable', _('Consumable')),
        ('equipment', _('Equipment')),
        ('spare_part', _('Spare Part')),
    )

    name = models.CharField(_('name'), max_length=200)
    sku = models.CharField(_('SKU'), max_length=50, unique=True, blank=True, null=True)
    barcode = models.CharField(_('barcode'), max_length=100, blank=True, null=True)
    description = models.TextField(_('description'), blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
        verbose_name=_('category')
    )
    item_type = models.CharField(
        _('item type'),
        max_length=20,
        choices=ITEM_TYPES,
        default='raw_material'
    )
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='items',
        verbose_name=_('unit of measure')
    )
    min_quantity = models.DecimalField(
        _('minimum quantity'),
        max_digits=12,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(0)]
    )
    max_quantity = models.DecimalField(
        _('maximum quantity'),
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    reorder_point = models.DecimalField(
        _('reorder point'),
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_('Quantity at which to reorder')
    )
    is_active = models.BooleanField(_('is active'), default=True)
    is_serialized = models.BooleanField(
        _('is serialized'),
        default=False,
        help_text=_('Whether this item requires serial number tracking')
    )
    is_lot_tracked = models.BooleanField(
        _('is lot tracked'),
        default=False,
        help_text=_('Whether this item requires lot/batch tracking')
    )
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_items',
        verbose_name=_('created by')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('inventory item')
        verbose_name_plural = _('inventory items')
        ordering = ['name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['item_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_item_type_display()})"

    def save(self, *args, **kwargs):
        # Generate SKU if not provided
        if not self.sku and self.name:
            from django.utils.text import slugify
            from django.utils import timezone
            
            # Create a base SKU from the item name
            base_sku = slugify(self.name).upper()[:20]
            
            # Add a timestamp to ensure uniqueness
            timestamp = timezone.now().strftime('%y%m%d%H%M')
            
            # Set the SKU
            self.sku = f"{base_sku}-{timestamp}"
            
        super().save(*args, **kwargs)

    @property
    def current_quantity(self):
        """Calculate the current quantity in stock."""
        return self.inventory_transactions.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

    @property
    def is_below_reorder_point(self):
        """Check if the current quantity is below the reorder point (only for items with transactions)."""
        if not self.reorder_point:
            return False
        if not self.inventory_transactions.exists():
            return False
        return self.current_quantity < self.reorder_point

class Location(models.Model):
    """Model representing a physical storage location."""
    LOCATION_TYPES = (
        ('warehouse', _('Warehouse')),
        ('shelf', _('Shelf')),
        ('bin', _('Bin')),
        ('room', _('Room')),
        ('area', _('Area')),
    )

    name = models.CharField(_('name'), max_length=100)
    code = models.CharField(_('location code'), max_length=20, unique=True)
    location_type = models.CharField(
        _('location type'),
        max_length=20,
        choices=LOCATION_TYPES,
        default='shelf'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sublocations',
        verbose_name=_('parent location')
    )
    description = models.TextField(_('description'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)
    address = models.TextField(_('address'), blank=True)
    max_capacity = models.PositiveIntegerField(
        _('maximum capacity'),
        null=True,
        blank=True,
        help_text=_('Maximum number of items that can be stored in this location')
    )
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('location')
        verbose_name_plural = _('locations')
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_location_type_display()})"

    @property
    def current_occupancy(self):
        """Calculate the current number of items in this location."""
        from django.db.models import Count
        return self.inventory_items.aggregate(
            total=Count('id')
        )['total'] or 0

    @property
    def is_full(self):
        """Check if the location is at or over capacity."""
        if self.max_capacity is None:
            return False
        return self.current_occupancy >= self.max_capacity

class InventoryTransaction(models.Model):
    """Model representing inventory movement and adjustments."""
    TRANSACTION_TYPES = (
        ('purchase', _('Purchase')),
        ('sale', _('Sale')),
        ('transfer_in', _('Transfer In')),
        ('transfer_out', _('Transfer Out')),
        ('adjustment', _('Adjustment')),
        ('production', _('Production')),
        ('consumption', _('Consumption')),
        ('return', _('Return')),
        ('scrap', _('Scrap')),
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name='inventory_transactions',
        verbose_name=_('item')
    )
    transaction_type = models.CharField(
        _('transaction type'),
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    quantity = models.DecimalField(
        _('quantity'),
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0.001)]
    )
    unit_cost = models.DecimalField(
        _('unit cost'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='inventory_transactions',
        verbose_name=_('location')
    )
    reference = models.CharField(
        _('reference'),
        max_length=100,
        blank=True,
        help_text=_('Reference number or document number')
    )
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventory_transactions',
        verbose_name=_('created by')
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('inventory transaction')
        verbose_name_plural = _('inventory transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_type']),
            models.Index(fields=['reference']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.item.name} x {self.quantity}"

    @property
    def total_cost(self):
        """Calculate the total cost of this transaction."""
        if self.unit_cost is not None:
            return self.quantity * self.unit_cost
        return None

    def save(self, *args, **kwargs):
        # Ensure quantity is positive for certain transaction types
        if self.transaction_type in ['sale', 'transfer_out', 'consumption', 'scrap']:
            self.quantity = abs(self.quantity) * -1  # Make negative
        else:
            self.quantity = abs(self.quantity)  # Ensure positive
            
        super().save(*args, **kwargs)

class InventoryItem(models.Model):
    """Model representing a specific instance of an item in inventory."""
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='inventory_items',
        verbose_name=_('item')
    )
    serial_number = models.CharField(
        _('serial number'),
        max_length=100,
        blank=True,
        null=True,
        unique=True
    )
    lot_number = models.CharField(
        _('lot/batch number'),
        max_length=100,
        blank=True,
        null=True
    )
    quantity = models.DecimalField(
        _('quantity'),
        max_digits=12,
        decimal_places=3,
        default=1,
        validators=[MinValueValidator(0.001)]
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='inventory_items',
        verbose_name=_('location')
    )
    expiry_date = models.DateField(
        _('expiry date'),
        null=True,
        blank=True
    )
    manufactured_date = models.DateField(
        _('manufactured date'),
        null=True,
        blank=True
    )
    purchase_date = models.DateField(
        _('purchase date'),
        null=True,
        blank=True
    )
    purchase_price = models.DecimalField(
        _('purchase price'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    supplier = models.ForeignKey(
        'Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_items',
        verbose_name=_('supplier')
    )
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('inventory item')
        verbose_name_plural = _('inventory items')
        ordering = ['item__name', 'lot_number', 'serial_number']
        indexes = [
            models.Index(fields=['serial_number']),
            models.Index(fields=['lot_number']),
            models.Index(fields=['expiry_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['item', 'serial_number'],
                name='unique_item_serial',
                condition=models.Q(serial_number__isnull=False)
            ),
        ]

    def __str__(self):
        if self.serial_number:
            return f"{self.item.name} (S/N: {self.serial_number})"
        elif self.lot_number:
            return f"{self.item.name} (Lot: {self.lot_number})"
        return f"{self.item.name} (ID: {self.id})"

    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Validate serial number for serialized items
        if self.item.is_serialized and not self.serial_number:
            raise ValidationError({
                'serial_number': 'Serial number is required for this item.'
            })
            
        # Validate lot number for lot-tracked items
        if self.item.is_lot_tracked and not self.lot_number:
            raise ValidationError({
                'lot_number': 'Lot number is required for this item.'
            })
            
        # Validate quantity for serialized items
        if self.item.is_serialized and self.quantity != 1:
            raise ValidationError({
                'quantity': 'Quantity must be 1 for serialized items.'
            })

    def save(self, *args, **kwargs):
        # Ensure serial number is uppercase and stripped of whitespace
        if self.serial_number:
            self.serial_number = self.serial_number.strip().upper()
            
        # Ensure lot number is uppercase and stripped of whitespace
        if self.lot_number:
            self.lot_number = self.lot_number.strip().upper()
            
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if the item is expired."""
        if not self.expiry_date:
            return False
        from django.utils import timezone
        return timezone.now().date() > self.expiry_date

    @property
    def age_days(self):
        """Calculate the age of the item in days."""
        from django.utils import timezone
        if self.manufactured_date:
            return (timezone.now().date() - self.manufactured_date).days
        return None

class Supplier(models.Model):
    """Model representing a supplier/vendor."""
    name = models.CharField(_('supplier name'), max_length=200)
    contact_person = models.CharField(_('contact person'), max_length=100, blank=True)
    email = models.EmailField(_('email'), blank=True)
    phone = models.CharField(_('phone'), max_length=20, blank=True)
    address = models.TextField(_('address'), blank=True)
    tax_id = models.CharField(_('tax ID'), max_length=50, blank=True)
    website = models.URLField(_('website'), blank=True)
    payment_terms = models.TextField(_('payment terms'), blank=True)
    notes = models.TextField(_('notes'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('supplier')
        verbose_name_plural = _('suppliers')
        ordering = ['name']

    def __str__(self):
        return self.name
