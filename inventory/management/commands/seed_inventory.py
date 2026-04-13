from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
import random

from inventory.models import (
    Category, UnitOfMeasure, Item, Location,
    InventoryTransaction, InventoryItem, Supplier
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed inventory with demo transactions, expiring items, and low stock data'

    def handle(self, *args, **kwargs):
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('No superuser found. Run seed_demo_data first.'))
            return

        locations = list(Location.objects.filter(is_active=True))
        if not locations:
            self.stdout.write(self.style.ERROR('No locations found. Run seed_demo_data first.'))
            return

        suppliers = list(Supplier.objects.all())
        items = list(Item.objects.filter(is_active=True))
        if not items:
            self.stdout.write(self.style.ERROR('No items found. Run seed_demo_data first.'))
            return

        self._seed_transactions(items, locations, user)
        self._seed_low_stock(items, locations, user)
        self._seed_expiring_items(items, locations, suppliers)
        self.stdout.write(self.style.SUCCESS('Inventory demo data seeded successfully!'))

    def _seed_transactions(self, items, locations, user):
        """Add realistic purchase + consumption transactions over last 30 days."""
        count = 0
        for item in items:
            # Skip if already has transactions
            if item.inventory_transactions.exists():
                continue
            loc = random.choice(locations)
            # Initial purchase
            InventoryTransaction.objects.create(
                item=item,
                transaction_type='purchase',
                quantity=Decimal(str(random.uniform(200, 800))),
                unit_cost=Decimal(str(random.uniform(10, 200))),
                location=loc,
                reference=f'PO-{random.randint(1000,9999)}',
                created_by=user,
            )
            # Several consumption transactions
            for _ in range(random.randint(2, 5)):
                InventoryTransaction.objects.create(
                    item=item,
                    transaction_type='consumption',
                    quantity=Decimal(str(random.uniform(10, 80))),
                    unit_cost=Decimal(str(random.uniform(10, 200))),
                    location=loc,
                    reference=f'USE-{random.randint(1000,9999)}',
                    created_by=user,
                )
            count += 1
        self.stdout.write(f'  Transactions added for {count} items')

    def _seed_low_stock(self, items, locations, user):
        """Drive 2-3 items below their reorder point."""
        low_stock_targets = items[:3]
        count = 0
        for item in low_stock_targets:
            if not item.reorder_point:
                continue
            current = item.current_quantity
            # Consume enough to go below reorder point
            gap = current - item.reorder_point + Decimal('1')
            if gap > 0:
                InventoryTransaction.objects.create(
                    item=item,
                    transaction_type='consumption',
                    quantity=gap,
                    location=random.choice(locations),
                    reference=f'DRAIN-{random.randint(1000,9999)}',
                    created_by=user,
                )
                count += 1
        self.stdout.write(f'  {count} items driven below reorder point')

    def _seed_expiring_items(self, items, locations, suppliers):
        """Add InventoryItem records expiring within 30 days."""
        today = date.today()
        count = 0
        for item in random.sample(items, min(4, len(items))):
            expiry = today + timedelta(days=random.randint(3, 25))
            supplier = random.choice(suppliers) if suppliers else None
            InventoryItem.objects.create(
                item=item,
                quantity=Decimal(str(random.uniform(5, 50))),
                location=random.choice(locations),
                expiry_date=expiry,
                purchase_date=today - timedelta(days=random.randint(30, 90)),
                purchase_price=Decimal(str(random.uniform(50, 500))),
                supplier=supplier,
            )
            count += 1
        self.stdout.write(f'  {count} expiring inventory items added')
