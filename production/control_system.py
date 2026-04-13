"""
Closed-Loop Control System for Sugar Extraction Optimization
Automatically adjusts machine parameters based on AI recommendations.
"""

import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from .models import (
    CrushingMachine, SensorReading, AnomalyAlert, 
    OptimizationRecommendation, ProductionBatch
)
from .ml_models import YieldPredictor, AnomalyDetector, ParameterOptimizer

logger = logging.getLogger(__name__)


class ControlSystem:
    """
    Main control system for managing machine optimization.
    Integrates ML models with real-time control.
    """
    
    def __init__(self):
        self.yield_predictor = YieldPredictor()
        self.anomaly_detector = AnomalyDetector()
        self.parameter_optimizer = None
        
        # Load trained models
        try:
            self.yield_predictor.load()
            self.anomaly_detector.load()
            self.parameter_optimizer = ParameterOptimizer(self.yield_predictor)
            logger.info("ML models loaded successfully")
        except FileNotFoundError:
            logger.warning("ML models not found. System will operate in monitoring mode only.")
    
    def process_sensor_reading(self, machine, sensor_data, batch=None, auto_adjust=False):
        """
        Process a new sensor reading and take appropriate actions.
        
        Args:
            machine: CrushingMachine instance
            sensor_data: Dict with sensor measurements
            batch: Optional ProductionBatch instance
            auto_adjust: Whether to automatically apply optimizations
            
        Returns:
            dict with processing results
        """
        results = {
            'sensor_reading_id': None,
            'anomaly_detected': False,
            'anomaly_alert_id': None,
            'optimization_generated': False,
            'recommendation_id': None,
            'parameters_adjusted': False
        }
        
        # Save sensor reading
        sensor_reading = self._save_sensor_reading(machine, sensor_data, batch)
        results['sensor_reading_id'] = sensor_reading.id
        
        # Check for anomalies
        if self.anomaly_detector.is_trained:
            anomaly_result = self._check_anomaly(machine, sensor_reading, sensor_data)
            if anomaly_result:
                results['anomaly_detected'] = True
                results['anomaly_alert_id'] = anomaly_result['alert_id']
                results['anomaly_severity'] = anomaly_result['severity']
                
                # Don't optimize if critical anomaly detected
                if anomaly_result['severity'] == 'critical':
                    logger.warning(f"Critical anomaly detected on {machine.machine_id}. Skipping optimization.")
                    return results
        
        # Generate optimization recommendation
        if self.parameter_optimizer:
            optimization = self._generate_optimization(machine, sensor_data, batch)
            if optimization:
                results['optimization_generated'] = True
                results['recommendation_id'] = optimization['recommendation_id']
                results['expected_improvement'] = optimization['expected_improvement']
                
                # Auto-apply if enabled and improvement is significant
                if auto_adjust and optimization['expected_improvement'] > 2.0:
                    applied = self._apply_optimization(machine, optimization['recommendation_id'])
                    results['parameters_adjusted'] = applied
        
        return results
    
    def _save_sensor_reading(self, machine, sensor_data, batch):
        """Save sensor reading to database."""
        sensor_reading = SensorReading.objects.create(
            machine=machine,
            batch=batch,
            pressure=Decimal(str(sensor_data['pressure'])),
            temperature=Decimal(str(sensor_data['temperature'])),
            rotation_speed=Decimal(str(sensor_data['rotation_speed'])),
            torque=Decimal(str(sensor_data['torque'])),
            vibration=Decimal(str(sensor_data['vibration'])),
            power_consumption=Decimal(str(sensor_data['power_consumption'])),
            feed_rate=Decimal(str(sensor_data['feed_rate'])),
            moisture_content=Decimal(str(sensor_data.get('moisture_content', 70))),
            brix_level=Decimal(str(sensor_data.get('brix_level', 14))),
        )
        return sensor_reading
    
    def _check_anomaly(self, machine, sensor_reading, sensor_data):
        """Check for anomalies in sensor data."""
        try:
            anomaly_result = self.anomaly_detector.detect(sensor_data)
            
            if anomaly_result['is_anomaly']:
                # Create anomaly alert
                alert = AnomalyAlert.objects.create(
                    machine=machine,
                    sensor_reading=sensor_reading,
                    severity=anomaly_result['severity'],
                    anomaly_score=Decimal(str(anomaly_result['anomaly_score'])),
                    description=self._generate_anomaly_description(sensor_data, anomaly_result)
                )
                
                logger.warning(
                    f"Anomaly detected on {machine.machine_id}: "
                    f"Severity={anomaly_result['severity']}, Score={anomaly_result['anomaly_score']:.4f}"
                )
                
                return {
                    'alert_id': alert.id,
                    'severity': anomaly_result['severity'],
                    'score': anomaly_result['anomaly_score']
                }
        except Exception as e:
            logger.error(f"Error checking anomaly: {e}")
        
        return None
    
    def _generate_anomaly_description(self, sensor_data, anomaly_result):
        """Generate human-readable anomaly description."""
        descriptions = []
        
        # Check which parameters are out of normal range
        if sensor_data['pressure'] > 120 or sensor_data['pressure'] < 80:
            descriptions.append(f"Pressure: {sensor_data['pressure']} bar (normal: 80-120)")
        
        if sensor_data['temperature'] > 35 or sensor_data['temperature'] < 25:
            descriptions.append(f"Temperature: {sensor_data['temperature']}°C (normal: 25-35)")
        
        if sensor_data['vibration'] > 10:
            descriptions.append(f"High vibration: {sensor_data['vibration']} mm/s")
        
        if sensor_data['rotation_speed'] > 20 or sensor_data['rotation_speed'] < 10:
            descriptions.append(f"Rotation speed: {sensor_data['rotation_speed']} RPM (normal: 10-20)")
        
        if descriptions:
            return "Anomalous readings detected: " + "; ".join(descriptions)
        else:
            return f"Anomaly detected with score {anomaly_result['anomaly_score']:.4f}"
    
    def _generate_optimization(self, machine, sensor_data, batch):
        """Generate optimization recommendation."""
        try:
            # Get current yield prediction
            current_yield = self.yield_predictor.predict(sensor_data)
            
            # Optimize parameters
            current_params = {
                'pressure': sensor_data['pressure'],
                'temperature': sensor_data['temperature'],
                'rotation_speed': sensor_data['rotation_speed'],
                'feed_rate': sensor_data['feed_rate'],
                'torque': sensor_data['torque'],
                'moisture_content': sensor_data.get('moisture_content', 70),
                'brix_level': sensor_data.get('brix_level', 14)
            }
            
            optimization = self.parameter_optimizer.optimize(current_params)
            
            if optimization and optimization['improvement'] > 0:
                # Create recommendation
                recommendation = OptimizationRecommendation.objects.create(
                    machine=machine,
                    batch=batch,
                    current_pressure=Decimal(str(current_params['pressure'])),
                    current_temperature=Decimal(str(current_params['temperature'])),
                    current_rotation_speed=Decimal(str(current_params['rotation_speed'])),
                    current_feed_rate=Decimal(str(current_params['feed_rate'])),
                    current_yield=Decimal(str(current_yield)),
                    recommended_pressure=Decimal(str(optimization['optimal_parameters']['pressure'])),
                    recommended_temperature=Decimal(str(optimization['optimal_parameters']['temperature'])),
                    recommended_rotation_speed=Decimal(str(optimization['optimal_parameters']['rotation_speed'])),
                    recommended_feed_rate=Decimal(str(optimization['optimal_parameters']['feed_rate'])),
                    expected_yield=Decimal(str(optimization['expected_yield'])),
                    expected_improvement=Decimal(str((optimization['improvement'] / current_yield) * 100)),
                    confidence_score=Decimal('85.0')  # Can be calculated from model
                )
                
                logger.info(
                    f"Optimization generated for {machine.machine_id}: "
                    f"{recommendation.expected_improvement}% improvement expected"
                )
                
                return {
                    'recommendation_id': recommendation.id,
                    'expected_improvement': float(recommendation.expected_improvement)
                }
        except Exception as e:
            logger.error(f"Error generating optimization: {e}")
        
        return None
    
    def _apply_optimization(self, machine, recommendation_id):
        """Apply optimization recommendation to machine."""
        try:
            recommendation = OptimizationRecommendation.objects.get(id=recommendation_id)
            
            # In a real system, this would send commands to the PLC/SCADA system
            # For now, we'll just mark it as applied
            recommendation.is_applied = True
            recommendation.applied_at = timezone.now()
            recommendation.save()
            
            logger.info(
                f"Optimization applied to {machine.machine_id}: "
                f"P={recommendation.recommended_pressure}, "
                f"T={recommendation.recommended_temperature}, "
                f"S={recommendation.recommended_rotation_speed}"
            )
            
            return True
        except Exception as e:
            logger.error(f"Error applying optimization: {e}")
            return False
    
    def monitor_machine(self, machine_id, duration_minutes=60):
        """
        Continuous monitoring mode for a specific machine.
        
        Args:
            machine_id: Machine identifier
            duration_minutes: How long to monitor
            
        Returns:
            dict with monitoring summary
        """
        try:
            machine = CrushingMachine.objects.get(machine_id=machine_id)
        except CrushingMachine.DoesNotExist:
            return {'error': f'Machine {machine_id} not found'}
        
        # Get recent sensor readings
        recent_readings = SensorReading.objects.filter(
            machine=machine,
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=duration_minutes)
        ).order_by('-timestamp')
        
        # Get recent alerts
        recent_alerts = AnomalyAlert.objects.filter(
            machine=machine,
            detected_at__gte=timezone.now() - timezone.timedelta(minutes=duration_minutes)
        )
        
        # Get recent recommendations
        recent_recommendations = OptimizationRecommendation.objects.filter(
            machine=machine,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=duration_minutes)
        )
        
        return {
            'machine_id': machine_id,
            'machine_name': machine.name,
            'status': machine.status,
            'monitoring_period': f'{duration_minutes} minutes',
            'total_readings': recent_readings.count(),
            'total_alerts': recent_alerts.count(),
            'critical_alerts': recent_alerts.filter(severity='critical').count(),
            'total_recommendations': recent_recommendations.count(),
            'applied_recommendations': recent_recommendations.filter(is_applied=True).count(),
            'average_yield_improvement': self._calculate_average_improvement(recent_recommendations)
        }
    
    def _calculate_average_improvement(self, recommendations):
        """Calculate average yield improvement from recommendations."""
        if not recommendations.exists():
            return 0.0
        
        total_improvement = sum(
            float(r.expected_improvement) 
            for r in recommendations
        )
        return total_improvement / recommendations.count()
    
    def get_system_status(self):
        """Get overall system status."""
        return {
            'yield_predictor_trained': self.yield_predictor.is_trained,
            'anomaly_detector_trained': self.anomaly_detector.is_trained,
            'optimizer_available': self.parameter_optimizer is not None,
            'total_machines': CrushingMachine.objects.filter(is_active=True).count(),
            'operational_machines': CrushingMachine.objects.filter(
                is_active=True, 
                status='operational'
            ).count(),
            'open_alerts': AnomalyAlert.objects.filter(status='open').count(),
            'pending_recommendations': OptimizationRecommendation.objects.filter(
                is_applied=False
            ).count()
        }


class DataCollector:
    """
    Utility class for collecting and preprocessing sensor data.
    """
    
    @staticmethod
    def collect_training_data(machine=None, start_date=None, end_date=None):
        """
        Collect historical sensor data for model training.
        
        Args:
            machine: Optional specific machine
            start_date: Start date for data collection
            end_date: End date for data collection
            
        Returns:
            DataFrame with sensor data
        """
        import pandas as pd
        
        queryset = SensorReading.objects.all()
        
        if machine:
            queryset = queryset.filter(machine=machine)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Convert to DataFrame
        data = list(queryset.values(
            'pressure', 'temperature', 'rotation_speed', 'torque',
            'vibration', 'power_consumption', 'feed_rate',
            'moisture_content', 'brix_level', 'extraction_rate'
        ))
        
        df = pd.DataFrame(data)
        
        # Handle missing values
        df = df.fillna(df.mean())
        
        return df
    
    @staticmethod
    def validate_sensor_data(sensor_data):
        """
        Validate sensor data before processing.
        
        Args:
            sensor_data: Dict with sensor readings
            
        Returns:
            tuple (is_valid, error_message)
        """
        required_fields = [
            'pressure', 'temperature', 'rotation_speed', 'torque',
            'vibration', 'power_consumption', 'feed_rate'
        ]
        
        # Check required fields
        for field in required_fields:
            if field not in sensor_data:
                return False, f"Missing required field: {field}"
        
        # Validate ranges
        validations = {
            'pressure': (0, 200, 'bar'),
            'temperature': (-10, 100, '°C'),
            'rotation_speed': (0, 50, 'RPM'),
            'torque': (0, 1000, 'Nm'),
            'vibration': (0, 50, 'mm/s'),
            'power_consumption': (0, 10000, 'kW'),
            'feed_rate': (0, 200, 'tons/hour')
        }
        
        for field, (min_val, max_val, unit) in validations.items():
            value = sensor_data[field]
            if not (min_val <= value <= max_val):
                return False, f"{field} out of range: {value} {unit} (expected {min_val}-{max_val})"
        
        return True, None
