"""
Management command to train all AI/ML models
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import pandas as pd
import os

from production.models import SensorReading, ProductionBatch, CrushingMachine
from farms.models import Farm, FarmCropCycle
from inventory.models import InventoryTransaction
from ai_ml.anomaly_detection import MachineAnomalyDetector
from ai_ml.farm_yield_prediction import FarmYieldPredictor
from ai_ml.inventory_forecasting import InventoryDemandForecaster


class Command(BaseCommand):
    help = 'Train all AI/ML models with current data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            choices=['all', 'anomaly', 'yield', 'inventory'],
            default='all',
            help='Which model to train'
        )

    def handle(self, *args, **options):
        model_type = options['model']
        
        self.stdout.write(self.style.SUCCESS('Starting AI/ML model training...'))
        
        if model_type in ['all', 'anomaly']:
            self.train_anomaly_detection()
        
        if model_type in ['all', 'yield']:
            self.train_yield_prediction()
        
        if model_type in ['all', 'inventory']:
            self.train_inventory_forecasting()
        
        self.stdout.write(self.style.SUCCESS('SUCCESS: All models trained successfully!'))

    def train_anomaly_detection(self):
        """Train anomaly detection model for machines."""
        self.stdout.write('Training anomaly detection model...')
        
        # Get normal sensor readings (last 30 days, no alerts)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        normal_readings = SensorReading.objects.filter(
            timestamp__gte=thirty_days_ago
        ).exclude(
            anomaly_alerts__isnull=False
        ).values(
            'pressure', 'temperature', 'rotation_speed', 'torque',
            'vibration', 'power_consumption', 'feed_rate',
            'moisture_content', 'brix_level'
        )
        
        if normal_readings.count() < 100:
            self.stdout.write(self.style.WARNING(
                'WARNING: Insufficient data for anomaly detection (need at least 100 readings)'
            ))
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(list(normal_readings))
        
        # Train model
        detector = MachineAnomalyDetector(contamination=0.05)
        result = detector.train(df)
        
        # Save model
        model_dir = 'ai_ml/trained_models'
        os.makedirs(model_dir, exist_ok=True)
        detector.save_model(f'{model_dir}/anomaly_detector.pkl')
        
        self.stdout.write(self.style.SUCCESS(
            f'SUCCESS: Anomaly detection trained on {result["samples_trained"]} samples'
        ))

    def train_yield_prediction(self):
        """Train farm yield prediction model."""
        self.stdout.write('Training yield prediction model...')
        
        # Get completed crop cycles with actual yields
        completed_cycles = FarmCropCycle.objects.filter(
            current_stage='harvested',
            actual_yield__isnull=False
        ).select_related('farm')
        
        if completed_cycles.count() < 10:
            self.stdout.write(self.style.WARNING(
                'WARNING: Insufficient data for yield prediction (need at least 10 completed cycles)'
            ))
            return
        
        # Prepare data
        farm_data = []
        yields = []
        
        for cycle in completed_cycles:
            farm_data.append({
                'area': float(cycle.farm.area),
                'soil_type': cycle.farm.soil_type,
                'variety': cycle.variety,
                'planting_date': cycle.planting_date
            })
            yields.append(float(cycle.actual_yield))
        
        df = pd.DataFrame(farm_data)
        
        # Train model
        predictor = FarmYieldPredictor()
        result = predictor.train(df, yields)
        
        # Save model
        model_dir = 'ai_ml/trained_models'
        os.makedirs(model_dir, exist_ok=True)
        predictor.save_model(f'{model_dir}/yield_predictor.pkl')
        
        self.stdout.write(self.style.SUCCESS(
            f'SUCCESS: Yield prediction trained - R2: {result["test_r2"]:.3f}'
        ))

    def train_inventory_forecasting(self):
        """Train inventory demand forecasting model."""
        self.stdout.write('Training inventory forecasting model...')
        
        # Get transaction history (last 90 days)
        ninety_days_ago = timezone.now() - timedelta(days=90)
        transactions = InventoryTransaction.objects.filter(
            created_at__gte=ninety_days_ago
        ).values('created_at', 'quantity', 'item_id')
        
        if transactions.count() < 50:
            self.stdout.write(self.style.WARNING(
                'WARNING: Insufficient data for inventory forecasting (need at least 50 transactions)'
            ))
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(list(transactions))
        
        # Train model for each item (simplified - train on all for now)
        forecaster = InventoryDemandForecaster()
        
        try:
            result = forecaster.train(df)
            
            # Save model
            model_dir = 'ai_ml/trained_models'
            os.makedirs(model_dir, exist_ok=True)
            forecaster.save_model(f'{model_dir}/inventory_forecaster.pkl')
            
            self.stdout.write(self.style.SUCCESS(
                f'SUCCESS: Inventory forecasting trained - R2: {result["test_r2"]:.3f}'
            ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f'WARNING: Could not train inventory forecaster: {str(e)}'
            ))
