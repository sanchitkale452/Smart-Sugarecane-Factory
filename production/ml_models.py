"""
Machine Learning Models for Sugar Extraction Optimization
This module contains ML models for yield prediction and anomaly detection.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import os
from django.conf import settings


class YieldPredictor:
    """
    Machine Learning model to predict sugar yield based on sensor data.
    Uses Random Forest Regression for robust predictions.
    """
    
    def __init__(self):
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.feature_names = [
            'pressure', 'temperature', 'rotation_speed', 'torque',
            'feed_rate', 'moisture_content', 'brix_level'
        ]
        self.is_trained = False
        
    def prepare_features(self, data):
        """
        Prepare features from sensor data.
        
        Args:
            data: DataFrame or dict with sensor readings
            
        Returns:
            numpy array of features
        """
        if isinstance(data, dict):
            data = pd.DataFrame([data])
        
        # Ensure all required features are present
        for feature in self.feature_names:
            if feature not in data.columns:
                raise ValueError(f"Missing required feature: {feature}")
        
        features = data[self.feature_names].values
        return features
    
    def train(self, X, y, test_size=0.2):
        """
        Train the yield prediction model.
        
        Args:
            X: Feature matrix (sensor data)
            y: Target variable (sugar yield)
            test_size: Proportion of data for testing
            
        Returns:
            dict with training metrics
        """
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True
        
        # Evaluate
        y_pred_train = self.model.predict(X_train_scaled)
        y_pred_test = self.model.predict(X_test_scaled)
        
        metrics = {
            'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
            'train_r2': r2_score(y_train, y_pred_train),
            'test_r2': r2_score(y_test, y_pred_test),
            'feature_importance': dict(zip(
                self.feature_names,
                self.model.feature_importances_
            ))
        }
        
        return metrics
    
    def predict(self, sensor_data):
        """
        Predict sugar yield from sensor data.
        
        Args:
            sensor_data: Dict or DataFrame with sensor readings
            
        Returns:
            Predicted yield value
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        features = self.prepare_features(sensor_data)
        features_scaled = self.scaler.transform(features)
        prediction = self.model.predict(features_scaled)
        
        return float(prediction[0])
    
    def predict_with_confidence(self, sensor_data):
        """
        Predict yield with confidence interval using tree predictions.
        
        Args:
            sensor_data: Dict or DataFrame with sensor readings
            
        Returns:
            dict with prediction, lower_bound, upper_bound
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        features = self.prepare_features(sensor_data)
        features_scaled = self.scaler.transform(features)
        
        # Get predictions from all trees
        tree_predictions = np.array([
            tree.predict(features_scaled) 
            for tree in self.model.estimators_
        ])
        
        prediction = np.mean(tree_predictions)
        std = np.std(tree_predictions)
        
        return {
            'prediction': float(prediction),
            'lower_bound': float(prediction - 1.96 * std),
            'upper_bound': float(prediction + 1.96 * std),
            'confidence_interval': float(1.96 * std)
        }
    
    def save(self, filepath=None):
        """Save model to disk."""
        if filepath is None:
            filepath = os.path.join(settings.BASE_DIR, 'ml_models', 'yield_predictor.pkl')
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained
        }, filepath)
    
    def load(self, filepath=None):
        """Load model from disk."""
        if filepath is None:
            filepath = os.path.join(settings.BASE_DIR, 'ml_models', 'yield_predictor.pkl')
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        data = joblib.load(filepath)
        self.model = data['model']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.is_trained = data['is_trained']


class AnomalyDetector:
    """
    Anomaly detection system for identifying machine malfunctions.
    Uses Isolation Forest algorithm.
    """
    
    def __init__(self, contamination=0.1):
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
            max_samples='auto',
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.feature_names = [
            'pressure', 'temperature', 'rotation_speed', 'torque',
            'vibration', 'power_consumption', 'feed_rate'
        ]
        self.is_trained = False
        self.anomaly_threshold = -0.5  # Anomaly score threshold
        
    def prepare_features(self, data):
        """Prepare features from sensor data."""
        if isinstance(data, dict):
            data = pd.DataFrame([data])
        
        for feature in self.feature_names:
            if feature not in data.columns:
                raise ValueError(f"Missing required feature: {feature}")
        
        features = data[self.feature_names].values
        return features
    
    def train(self, X):
        """
        Train the anomaly detection model on normal operating data.
        
        Args:
            X: Feature matrix of normal operating conditions
            
        Returns:
            dict with training info
        """
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model.fit(X_scaled)
        self.is_trained = True
        
        # Get anomaly scores for training data
        scores = self.model.score_samples(X_scaled)
        
        return {
            'n_samples': len(X),
            'mean_score': float(np.mean(scores)),
            'std_score': float(np.std(scores)),
            'min_score': float(np.min(scores)),
            'max_score': float(np.max(scores))
        }
    
    def detect(self, sensor_data):
        """
        Detect anomalies in sensor data.
        
        Args:
            sensor_data: Dict or DataFrame with sensor readings
            
        Returns:
            dict with anomaly detection results
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before detection")
        
        features = self.prepare_features(sensor_data)
        features_scaled = self.scaler.transform(features)
        
        # Predict (-1 for anomaly, 1 for normal)
        prediction = self.model.predict(features_scaled)[0]
        
        # Get anomaly score (lower is more anomalous)
        score = self.model.score_samples(features_scaled)[0]
        
        # Determine severity
        if score < -0.7:
            severity = 'critical'
        elif score < -0.5:
            severity = 'high'
        elif score < -0.3:
            severity = 'medium'
        else:
            severity = 'low'
        
        return {
            'is_anomaly': prediction == -1,
            'anomaly_score': float(score),
            'severity': severity,
            'confidence': float(abs(score))
        }
    
    def detect_batch(self, sensor_data_batch):
        """
        Detect anomalies in a batch of sensor readings.
        
        Args:
            sensor_data_batch: DataFrame with multiple sensor readings
            
        Returns:
            DataFrame with anomaly detection results
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before detection")
        
        features = self.prepare_features(sensor_data_batch)
        features_scaled = self.scaler.transform(features)
        
        predictions = self.model.predict(features_scaled)
        scores = self.model.score_samples(features_scaled)
        
        results = pd.DataFrame({
            'is_anomaly': predictions == -1,
            'anomaly_score': scores
        })
        
        return results
    
    def save(self, filepath=None):
        """Save model to disk."""
        if filepath is None:
            filepath = os.path.join(settings.BASE_DIR, 'ml_models', 'anomaly_detector.pkl')
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained,
            'anomaly_threshold': self.anomaly_threshold
        }, filepath)
    
    def load(self, filepath=None):
        """Load model from disk."""
        if filepath is None:
            filepath = os.path.join(settings.BASE_DIR, 'ml_models', 'anomaly_detector.pkl')
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        data = joblib.load(filepath)
        self.model = data['model']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.is_trained = data['is_trained']
        self.anomaly_threshold = data['anomaly_threshold']


class ParameterOptimizer:
    """
    Optimization system for suggesting optimal machine parameters.
    """
    
    def __init__(self, yield_predictor):
        self.yield_predictor = yield_predictor
        
        # Define parameter ranges (min, max, step)
        self.parameter_ranges = {
            'pressure': (80, 120, 2),  # bar
            'temperature': (25, 35, 0.5),  # °C
            'rotation_speed': (10, 20, 0.5),  # RPM
            'feed_rate': (50, 100, 5),  # tons/hour
        }
        
        # Fixed parameters (not optimized)
        self.fixed_params = {
            'torque': 85,
            'moisture_content': 70,
            'brix_level': 14
        }
    
    def optimize(self, current_params, constraints=None):
        """
        Find optimal parameters to maximize yield.
        
        Args:
            current_params: Current sensor readings
            constraints: Optional dict of parameter constraints
            
        Returns:
            dict with optimal parameters and expected yield
        """
        best_yield = -float('inf')
        best_params = None
        
        # Grid search over parameter space
        for pressure in np.arange(*self.parameter_ranges['pressure']):
            for temp in np.arange(*self.parameter_ranges['temperature']):
                for speed in np.arange(*self.parameter_ranges['rotation_speed']):
                    for feed in np.arange(*self.parameter_ranges['feed_rate']):
                        
                        # Create parameter combination
                        params = {
                            'pressure': pressure,
                            'temperature': temp,
                            'rotation_speed': speed,
                            'feed_rate': feed,
                            **self.fixed_params
                        }
                        
                        # Check constraints
                        if constraints and not self._check_constraints(params, constraints):
                            continue
                        
                        # Predict yield
                        try:
                            predicted_yield = self.yield_predictor.predict(params)
                            
                            if predicted_yield > best_yield:
                                best_yield = predicted_yield
                                best_params = params.copy()
                        except:
                            continue
        
        if best_params is None:
            return None
        
        # Calculate adjustments needed
        adjustments = {}
        for param in ['pressure', 'temperature', 'rotation_speed', 'feed_rate']:
            if param in current_params:
                adjustments[param] = best_params[param] - current_params[param]
        
        return {
            'optimal_parameters': best_params,
            'expected_yield': float(best_yield),
            'adjustments': adjustments,
            'improvement': float(best_yield - self.yield_predictor.predict(current_params))
        }
    
    def _check_constraints(self, params, constraints):
        """Check if parameters satisfy constraints."""
        for param, value in params.items():
            if param in constraints:
                min_val, max_val = constraints[param]
                if value < min_val or value > max_val:
                    return False
        return True
    
    def suggest_adjustment(self, current_params, target_yield):
        """
        Suggest parameter adjustments to reach target yield.
        
        Args:
            current_params: Current sensor readings
            target_yield: Desired yield value
            
        Returns:
            dict with suggested adjustments
        """
        current_yield = self.yield_predictor.predict(current_params)
        
        if current_yield >= target_yield:
            return {
                'message': 'Current parameters already meet target yield',
                'current_yield': float(current_yield),
                'target_yield': float(target_yield)
            }
        
        # Find parameters that achieve target yield
        optimal = self.optimize(current_params)
        
        if optimal and optimal['expected_yield'] >= target_yield:
            return {
                'message': 'Adjustments suggested to reach target',
                'current_yield': float(current_yield),
                'target_yield': float(target_yield),
                'expected_yield': optimal['expected_yield'],
                'adjustments': optimal['adjustments']
            }
        else:
            return {
                'message': 'Target yield may not be achievable with current constraints',
                'current_yield': float(current_yield),
                'target_yield': float(target_yield),
                'max_achievable': optimal['expected_yield'] if optimal else None
            }
