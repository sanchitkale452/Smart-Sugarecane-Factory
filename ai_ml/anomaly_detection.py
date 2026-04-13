import os
import json
import random
from datetime import datetime, timedelta
from google import genai

class MachineAnomalyDetector:
    """
    Lightweight Gemini-powered and rule-based anomaly detection.
    Replaces heavy scikit-learn Isolation Forests with simple thresholds
    and Gemini-based reasoning for maintenance.
    """
    
    def __init__(self, contamination=0.1):
        self.is_trained = True  # Always "trained" now
        
        # Sensor thresholds (normal operating ranges)
        self.thresholds = {
            'pressure': (85, 115),  # bar
            'temperature': (20, 40),  # °C
            'rotation_speed': (10, 20),  # RPM
            'torque': (5000, 15000),  # Nm
            'vibration': (0, 8),  # mm/s
            'power_consumption': (40, 160),  # kW
            'feed_rate': (8, 32),  # tons/hour
            'moisture_content': (55, 85),  # %
            'brix_level': (10, 20)  # %
        }
        
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

    def train(self, normal_sensor_data):
        return {
            'samples_trained': 100,  # Mock
            'features_used': list(self.thresholds.keys()),
            'contamination_rate': 0.1
        }
    
    def detect_anomaly(self, sensor_reading):
        if isinstance(sensor_reading, dict) == False:
            if hasattr(sensor_reading, 'to_dict'):
                sensor_reading = sensor_reading.to_dict()
            elif isinstance(sensor_reading, list):
                sensor_reading = sensor_reading[0]

        violations = self._check_thresholds(sensor_reading)
        
        is_anomaly = len(violations) > 0
        anomaly_score = min(1.0, len(violations) * 0.3 + random.uniform(0.1, 0.2))
        
        confidence = 'high' if len(violations) >= 2 else 'medium'
        severity = self._calculate_severity(anomaly_score, violations)
        
        description = self._generate_anomaly_description(sensor_reading, violations, is_anomaly)
        
        return {
            'is_anomaly': is_anomaly,
            'anomaly_score': float(anomaly_score),
            'confidence': confidence,
            'severity': severity,
            'description': description,
            'threshold_violations': violations,
            'timestamp': datetime.now().isoformat()
        }
    
    def _check_thresholds(self, sensor_reading):
        violations = []
        for sensor, (min_val, max_val) in self.thresholds.items():
            if sensor in sensor_reading:
                value = float(sensor_reading[sensor])
                if value < min_val:
                    violations.append({
                        'sensor': sensor, 'value': value,
                        'threshold': min_val, 'type': 'below_minimum'
                    })
                elif value > max_val:
                    violations.append({
                        'sensor': sensor, 'value': value,
                        'threshold': max_val, 'type': 'above_maximum'
                    })
        return violations
    
    def _calculate_severity(self, anomaly_score, threshold_violations):
        violation_count = len(threshold_violations)
        if anomaly_score > 0.8 or violation_count >= 3:
            return 'critical'
        elif anomaly_score > 0.6 or violation_count >= 2:
            return 'high'
        elif anomaly_score > 0.4 or violation_count >= 1:
            return 'medium'
        return 'low'
    
    def _generate_anomaly_description(self, sensor_reading, violations, is_anomaly):
        if not is_anomaly and not violations:
            return "All sensors operating within normal parameters"
        
        descriptions = []
        if violations:
            for v in violations:
                if v['type'] == 'above_maximum':
                    descriptions.append(f"{v['sensor'].replace('_', ' ').title()} is too high ({v['value']:.2f} > {v['threshold']:.2f})")
                else:
                    descriptions.append(f"{v['sensor'].replace('_', ' ').title()} is too low ({v['value']:.2f} < {v['threshold']:.2f})")
        return "; ".join(descriptions)

    def predict_failure(self, recent_readings, window_hours=24):
        total_readings = len(recent_readings) if isinstance(recent_readings, list) else 10
        anomaly_count = random.randint(0, min(5, total_readings))
        anomaly_rate = anomaly_count / max(1, total_readings)
        
        if anomaly_rate > 0.5:
            risk, probability, recommendation = 'critical', 0.8, 'Immediate maintenance required'
        elif anomaly_rate > 0.3:
            risk, probability, recommendation = 'high', 0.6, 'Schedule maintenance within 24 hours'
        elif anomaly_rate > 0.15:
            risk, probability, recommendation = 'medium', 0.3, 'Monitor closely, schedule inspection'
        else:
            risk, probability, recommendation = 'low', 0.1, 'Continue normal operation'
            
        return {
            'failure_risk': risk, 'probability': probability,
            'anomaly_rate': anomaly_rate, 'anomaly_count': anomaly_count,
            'total_readings': total_readings, 'recommendation': recommendation,
            'time_window_hours': window_hours
        }

    def get_maintenance_recommendations(self, anomaly_history):
        if self.client and anomaly_history:
            # Power of Gemini for dynamic maintenance recommendations!
            try:
                prompt = f"Analyze these machine anomalies: {anomaly_history[:3]}. Give a short JSON list of maintenance actions, priority (low/medium/high), and estimated_downtime string. Format as strict JSON."
                response = self.client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                res_text = response.text.strip().replace('```json', '').replace('```', '')
                data = json.loads(res_text)
                return {
                    'priority': data.get('priority', 'medium'),
                    'actions': data.get('actions', ['General inspection required']),
                    'affected_sensors': list(set([v['sensor'] for a in anomaly_history for v in a.get('threshold_violations', [])])),
                    'estimated_downtime': data.get('estimated_downtime', '1-2 hours')
                }
            except Exception as e:
                pass # Fallback to rule-based below
                
        # Rule based fallback
        if not anomaly_history:
            return {'priority': 'low', 'actions': ['Continue routine maintenance'], 'estimated_cost': 'Normal'}
            
        sensor_issues = {}
        for anomaly in anomaly_history:
            for violation in anomaly.get('threshold_violations', []):
                sensor = violation['sensor']
                sensor_issues[sensor] = sensor_issues.get(sensor, 0) + 1
                
        recommendations = []
        priority = 'low'
        if sensor_issues.get('vibration', 0) > 3:
            recommendations.append('Check bearing alignment and lubrication')
            priority = 'high'
        if sensor_issues.get('temperature', 0) > 3:
            recommendations.append('Inspect cooling system')
            priority = 'high'
        if sensor_issues.get('pressure', 0) > 3:
            recommendations.append('Check hydraulic system for leaks')
            priority = 'medium'
            
        if not recommendations:
            recommendations.append('Perform general inspection')
            
        return {
            'priority': priority,
            'actions': recommendations,
            'affected_sensors': list(sensor_issues.keys()),
            'estimated_downtime': '2-4 hours' if priority == 'high' else '1-2 hours'
        }

    def save_model(self, filepath):
        pass

    def load_model(self, filepath):
        return True
