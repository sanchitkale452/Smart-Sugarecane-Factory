from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
import random

from farms.models import Farm, FarmCropCycle, FarmActivity
from production.models import (
    ProductionBatch, ProductionStage, BatchStage, ProductionOutput,
    CrushingMachine, SensorReading, AnomalyAlert, OptimizationRecommendation
)
from inventory.models import (
    Category, UnitOfMeasure, Item, Location, InventoryTransaction,
    InventoryItem, Supplier
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with demo data for the sugarcane factory'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding demo data...')
        
        # Create users
        users = self.create_users()
        self.stdout.write(self.style.SUCCESS(f'Created {len(users)} users'))
        
        # Create farms
        farms = self.create_farms(users)
        self.stdout.write(self.style.SUCCESS(f'Created {len(farms)} farms'))
        
        # Create crop cycles
        crop_cycles = self.create_crop_cycles(farms)
        self.stdout.write(self.style.SUCCESS(f'Created {len(crop_cycles)} crop cycles'))
        
        # Create farm activities
        activities = self.create_farm_activities(farms, users)
        self.stdout.write(self.style.SUCCESS(f'Created {len(activities)} farm activities'))
        
        # Create inventory data
        categories = self.create_categories()
        units = self.create_units()
        suppliers = self.create_suppliers()
        locations = self.create_locations()
        items = self.create_items(categories, units, users)
        inv_items = self.create_inventory_items(items, locations, suppliers)
        transactions = self.create_inventory_transactions(items, locations, users)
        self.stdout.write(self.style.SUCCESS(f'Created inventory data'))
        
        # Create production data
        machines = self.create_machines()
        stages = self.create_production_stages()
        batches = self.create_production_batches(farms, users)
        batch_stages = self.create_batch_stages(batches, stages, users)
        outputs = self.create_production_outputs(batches, users)
        sensor_readings = self.create_sensor_readings(machines)
        alerts = self.create_anomaly_alerts(machines, sensor_readings, users)
        recommendations = self.create_optimization_recommendations(machines, batches, users)
        self.stdout.write(self.style.SUCCESS(f'Created production data'))
        
        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully!'))

    def create_users(self):
        users = []
        # Create admin user
        if not User.objects.filter(email='abcd@123').exists():
            # If old admin exists, migrate to new credentials
            old_admin = User.objects.filter(email='admin@factory.com').first()
            if old_admin:
                old_admin.email = 'abcd@123'
                old_admin.username = old_admin.username or 'admin'
                old_admin.set_password('abcd123')
                old_admin.is_staff = True
                old_admin.is_superuser = True
                old_admin.first_name = old_admin.first_name or 'Admin'
                old_admin.last_name = old_admin.last_name or 'User'
                old_admin.save()
                admin = old_admin
            else:
                admin = User.objects.create_superuser(
                    username='admin',
                    email='abcd@123',
                    password='abcd123',
                    first_name='Admin',
                    last_name='User'
                )
            users.append(admin)
        else:
            users.append(User.objects.get(email='abcd@123'))
        
        # Create regular users
        user_data = [
            ('rajesh.patil', 'rajesh@factory.com', 'Rajesh', 'Patil'),
            ('priya.desai', 'priya@factory.com', 'Priya', 'Desai'),
            ('suresh.jadhav', 'suresh@factory.com', 'Suresh', 'Jadhav'),
            ('anita.kulkarni', 'anita@factory.com', 'Anita', 'Kulkarni'),
        ]
        
        for username, email, first_name, last_name in user_data:
            if not User.objects.filter(email=email).exists():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='password123',
                    first_name=first_name,
                    last_name=last_name
                )
                users.append(user)
            else:
                users.append(User.objects.get(email=email))
        
        return users

    def create_farms(self, users):
        farms = []
        farm_data = [
            ('Green Valley Farm', 'Maharashtra, India', 150.5, 'loamy'),
            ('Sunshine Acres', 'Uttar Pradesh, India', 200.0, 'clay'),
            ('River Bend Farm', 'Karnataka, India', 175.25, 'sandy'),
            ('Golden Fields', 'Tamil Nadu, India', 225.0, 'loamy'),
            ('Hilltop Plantation', 'Andhra Pradesh, India', 180.75, 'silty'),
        ]
        
        for name, location, area, soil_type in farm_data:
            farm, created = Farm.objects.get_or_create(
                name=name,
                defaults={
                    'owner': random.choice(users),
                    'location': location,
                    'area': Decimal(str(area)),
                    'soil_type': soil_type,
                    'status': random.choice(['active', 'active', 'active', 'inactive']),
                    'description': f'A productive sugarcane farm in {location}'
                }
            )
            farms.append(farm)
        
        return farms

    def create_crop_cycles(self, farms):
        cycles = []
        varieties = ['Co 86032', 'Co 0238', 'CoC 671', 'Co 99004', 'Co 0118']
        
        for farm in farms:
            # Create some completed cycles with actual yields for AI training
            for i in range(random.randint(3, 5)):
                planting_date = date.today() - timedelta(days=random.randint(30, 730))
                expected_yield = Decimal(str(random.uniform(50, 150)))
                
                # 60% chance of being harvested (for AI training)
                is_harvested = random.random() < 0.6
                
                cycle, created = FarmCropCycle.objects.get_or_create(
                    farm=farm,
                    variety=random.choice(varieties),
                    planting_date=planting_date,
                    defaults={
                        'expected_harvest_date': planting_date + timedelta(days=random.randint(300, 365)),
                        'current_stage': 'harvested' if is_harvested else random.choice(['growing', 'mature']),
                        'estimated_yield': expected_yield,
                        'actual_yield': expected_yield * Decimal(str(random.uniform(0.85, 1.15))) if is_harvested else None,
                        'actual_harvest_date': planting_date + timedelta(days=random.randint(300, 400)) if is_harvested else None,
                        'notes': f'Crop cycle for {farm.name}'
                    }
                )
                cycles.append(cycle)
        
        return cycles

    def create_farm_activities(self, farms, users):
        activities = []
        activity_types = ['plowing', 'planting', 'fertilizing', 'irrigation', 'pest_control', 'harvesting']
        
        for farm in farms:
            for i in range(random.randint(5, 10)):
                activity, created = FarmActivity.objects.get_or_create(
                    farm=farm,
                    activity_type=random.choice(activity_types),
                    date=date.today() - timedelta(days=random.randint(1, 180)),
                    defaults={
                        'description': f'{random.choice(activity_types).replace("_", " ").title()} activity',
                        'performed_by': random.choice(users),
                        'cost': Decimal(str(random.uniform(500, 5000))),
                        'notes': 'Routine farm maintenance'
                    }
                )
                activities.append(activity)
        
        return activities

    def create_categories(self):
        categories = []
        cat_data = [
            ('Raw Materials', None),
            ('Finished Products', None),
            ('Equipment', None),
            ('Chemicals', 'Raw Materials'),
            ('Packaging', 'Raw Materials'),
        ]
        
        for name, parent_name in cat_data:
            parent = Category.objects.filter(name=parent_name).first() if parent_name else None
            cat, created = Category.objects.get_or_create(
                name=name,
                defaults={'parent': parent, 'description': f'{name} category'}
            )
            categories.append(cat)
        
        return categories

    def create_units(self):
        units = []
        unit_data = [
            ('Kilogram', 'kg'),
            ('Ton', 'ton'),
            ('Liter', 'L'),
            ('Piece', 'pcs'),
            ('Box', 'box'),
        ]
        
        for name, abbr in unit_data:
            unit, created = UnitOfMeasure.objects.get_or_create(
                abbreviation=abbr,
                defaults={'name': name}
            )
            units.append(unit)
        
        return units

    def create_suppliers(self):
        suppliers = []
        supplier_data = [
            ('ABC Chemicals Ltd', 'Ramesh Kumar', 'ramesh@abc.com'),
            ('XYZ Packaging Co', 'Sunita Sharma', 'sunita@xyz.com'),
            ('Bharat Equipment Works', 'Vijay Shinde', 'vijay@bharatequip.com'),
        ]
        
        for name, contact, email in supplier_data:
            supplier, created = Supplier.objects.get_or_create(
                name=name,
                defaults={
                    'contact_person': contact,
                    'email': email,
                    'phone': f'+91-{random.randint(7000000000, 9999999999)}'
                }
            )
            suppliers.append(supplier)
        
        return suppliers

    def create_locations(self):
        locations = []
        loc_data = [
            ('WH-01', 'Main Warehouse', 'warehouse'),
            ('WH-02', 'Storage Area A', 'area'),
            ('SH-01', 'Shelf 1', 'shelf'),
            ('SH-02', 'Shelf 2', 'shelf'),
        ]
        
        for code, name, loc_type in loc_data:
            loc, created = Location.objects.get_or_create(
                code=code,
                defaults={'name': name, 'location_type': loc_type}
            )
            locations.append(loc)
        
        return locations

    def create_items(self, categories, units, users):
        items = []
        item_data = [
            ('Raw Sugar', 'finished_good', 'Kilogram'),
            ('Refined Sugar', 'finished_good', 'Kilogram'),
            ('Molasses', 'finished_good', 'Liter'),
            ('Lime', 'raw_material', 'Kilogram'),
            ('Sulfur Dioxide', 'raw_material', 'Kilogram'),
            ('Packaging Bags', 'consumable', 'Piece'),
        ]
        
        for name, item_type, unit_name in item_data:
            unit = UnitOfMeasure.objects.get(name=unit_name)
            category = random.choice(categories)
            item, created = Item.objects.get_or_create(
                name=name,
                defaults={
                    'item_type': item_type,
                    'unit_of_measure': unit,
                    'category': category,
                    'min_quantity': Decimal('10'),
                    'reorder_point': Decimal('50'),
                    'created_by': random.choice(users)
                }
            )
            items.append(item)
        
        return items

    def create_inventory_items(self, items, locations, suppliers):
        inv_items = []
        for item in items[:10]:
            for i in range(random.randint(1, 3)):
                inv_item = InventoryItem.objects.create(
                    item=item,
                    quantity=Decimal(str(random.uniform(10, 1000))),
                    location=random.choice(locations),
                    supplier=random.choice(suppliers),
                    purchase_date=date.today() - timedelta(days=random.randint(1, 90)),
                    purchase_price=Decimal(str(random.uniform(100, 10000)))
                )
                inv_items.append(inv_item)
        
        return inv_items

    def create_inventory_transactions(self, items, locations, users):
        transactions = []
        trans_types = ['purchase', 'production', 'consumption', 'adjustment']
        
        for item in items[:10]:
            for i in range(random.randint(3, 7)):
                trans = InventoryTransaction.objects.create(
                    item=item,
                    transaction_type=random.choice(trans_types),
                    quantity=Decimal(str(random.uniform(10, 500))),
                    unit_cost=Decimal(str(random.uniform(10, 100))),
                    location=random.choice(locations),
                    reference=f'REF-{random.randint(1000, 9999)}',
                    created_by=random.choice(users)
                )
                transactions.append(trans)
        
        return transactions

    def create_machines(self):
        machines = []
        for i in range(1, 6):
            machine, created = CrushingMachine.objects.get_or_create(
                machine_id=f'CM-{i:03d}',
                defaults={
                    'name': f'Crushing Machine {i}',
                    'model': f'Model-{random.choice(["A", "B", "C"])}{random.randint(100, 999)}',
                    'manufacturer': random.choice(['Walchandnagar Industries', 'Triveni Engineering', 'KCP Limited']),
                    'status': random.choice(['operational', 'operational', 'operational', 'maintenance']),
                    'optimal_pressure': Decimal(str(random.uniform(90, 110))),
                    'optimal_temperature': Decimal(str(random.uniform(25, 35))),
                    'optimal_rotation_speed': Decimal(str(random.uniform(12, 18)))
                }
            )
            machines.append(machine)
        
        return machines

    def create_production_stages(self):
        stages = []
        stage_data = [
            ('Harvesting', 'harvesting'),
            ('Cleaning', 'cleaning'),
            ('Crushing', 'crushing'),
            ('Juice Extraction', 'juice_extraction'),
            ('Clarification', 'clarification'),
            ('Evaporation', 'evaporation'),
            ('Crystallization', 'crystallization'),
            ('Centrifugation', 'centrifugation'),
            ('Drying', 'drying'),
            ('Packaging', 'packaging'),
        ]
        
        for name, stage_type in stage_data:
            stage, created = ProductionStage.objects.get_or_create(
                stage_type=stage_type,
                defaults={'name': name, 'description': f'{name} stage'}
            )
            stages.append(stage)
        
        return stages

    def create_production_batches(self, farms, users):
        batches = []
        for i in range(15):
            batch_num = f'BATCH-{timezone.now().year}-{i+1:04d}'
            batch, created = ProductionBatch.objects.get_or_create(
                batch_number=batch_num,
                defaults={
                    'farm': random.choice(farms),
                    'status': random.choice(['pending', 'in_progress', 'completed']),
                    'expected_yield': Decimal(str(random.uniform(5000, 15000))),
                    'created_by': random.choice(users)
                }
            )
            batches.append(batch)
        
        return batches

    def create_batch_stages(self, batches, stages, users):
        batch_stages = []
        for batch in batches[:10]:
            for stage in stages[:5]:
                try:
                    bs, created = BatchStage.objects.get_or_create(
                        batch=batch,
                        stage=stage,
                        defaults={
                            'start_time': timezone.now() - timedelta(hours=random.randint(1, 48)),
                            'status': random.choice(['pending', 'in_progress', 'completed']),
                            'supervisor': random.choice(users)
                        }
                    )
                    batch_stages.append(bs)
                except:
                    pass
        
        return batch_stages

    def create_production_outputs(self, batches, users):
        outputs = []
        output_types = ['raw_juice', 'clarified_juice', 'syrup', 'molasses', 'raw_sugar', 'refined_sugar']
        
        for batch in batches[:10]:
            for i in range(random.randint(2, 4)):
                output = ProductionOutput.objects.create(
                    batch=batch,
                    output_type=random.choice(output_types),
                    quantity=Decimal(str(random.uniform(1000, 5000))),
                    quality_rating=random.randint(6, 10),
                    recorded_by=random.choice(users)
                )
                outputs.append(output)
        
        return outputs

    def create_sensor_readings(self, machines):
        readings = []
        
        for machine in machines:
            # Create 30 sensor readings per machine (150 total for AI training)
            for i in range(30):
                timestamp = timezone.now() - timedelta(hours=random.randint(1, 720))
                reading, created = SensorReading.objects.get_or_create(
                    machine=machine,
                    timestamp=timestamp,
                    defaults={
                        'pressure': Decimal(str(random.uniform(95, 105))),
                        'temperature': Decimal(str(random.uniform(25, 35))),
                        'rotation_speed': Decimal(str(random.uniform(12, 18))),
                        'torque': Decimal(str(random.uniform(8000, 12000))),
                        'vibration': Decimal(str(random.uniform(2, 6))),
                        'power_consumption': Decimal(str(random.uniform(80, 120))),
                        'feed_rate': Decimal(str(random.uniform(15, 25))),
                        'moisture_content': Decimal(str(random.uniform(65, 75))),
                        'brix_level': Decimal(str(random.uniform(12, 18))),
                    }
                )
                readings.append(reading)
        
        return readings

    def create_anomaly_alerts(self, machines, sensor_readings, users):
        alerts = []
        for i in range(10):
            alert = AnomalyAlert.objects.create(
                machine=random.choice(machines),
                sensor_reading=random.choice(sensor_readings),
                severity=random.choice(['low', 'medium', 'high']),
                anomaly_score=Decimal(str(random.uniform(0.5, 0.99))),
                description=f'Anomaly detected: {random.choice(["High pressure", "Temperature spike", "Vibration anomaly"])}',
                status=random.choice(['open', 'acknowledged', 'resolved']),
                acknowledged_by=random.choice(users) if random.random() > 0.5 else None
            )
            alerts.append(alert)
        
        return alerts

    def create_optimization_recommendations(self, machines, batches, users):
        recommendations = []
        for i in range(8):
            rec = OptimizationRecommendation.objects.create(
                machine=random.choice(machines),
                batch=random.choice(batches),
                current_pressure=Decimal(str(random.uniform(90, 110))),
                current_temperature=Decimal(str(random.uniform(25, 35))),
                current_rotation_speed=Decimal(str(random.uniform(12, 18))),
                current_feed_rate=Decimal(str(random.uniform(15, 25))),
                current_yield=Decimal(str(random.uniform(8000, 12000))),
                recommended_pressure=Decimal(str(random.uniform(95, 105))),
                recommended_temperature=Decimal(str(random.uniform(28, 32))),
                recommended_rotation_speed=Decimal(str(random.uniform(14, 16))),
                recommended_feed_rate=Decimal(str(random.uniform(18, 22))),
                expected_yield=Decimal(str(random.uniform(10000, 14000))),
                expected_improvement=Decimal(str(random.uniform(5, 15))),
                confidence_score=Decimal(str(random.uniform(75, 95))),
                is_applied=random.choice([True, False])
            )
            recommendations.append(rec)
        
        return recommendations
