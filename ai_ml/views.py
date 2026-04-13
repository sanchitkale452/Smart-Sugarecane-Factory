"""
AI/ML Dashboard Views
Displays AI predictions, insights, and analytics
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None
import os
import json
from django.db.models import Avg, F, FloatField, ExpressionWrapper
from django.db import models
from django.db.models.functions import Coalesce
from django.utils.safestring import mark_safe

from production.models import CrushingMachine, SensorReading, AnomalyAlert
from farms.models import Farm, FarmCropCycle
from inventory.models import Item, InventoryTransaction
from .anomaly_detection import MachineAnomalyDetector
from .farm_yield_prediction import FarmYieldPredictor
from .inventory_forecasting import InventoryDemandForecaster, SeasonalDemandAnalyzer


@login_required
def ai_dashboard(request):
    """Main AI/ML insights dashboard."""
    
    # Get recent anomalies
    recent_anomalies = AnomalyAlert.objects.filter(
        status__in=['open', 'acknowledged']
    ).select_related('machine')[:10]
    
    # Get machines with high failure risk
    machines = CrushingMachine.objects.filter(is_active=True)
    high_risk_machines = []
    
    model_path = 'ai_ml/trained_models/anomaly_detector.pkl'
    if os.path.exists(model_path):
        detector = MachineAnomalyDetector()
        detector.load_model(model_path)
        
        for machine in machines:
            recent_readings = machine.sensor_readings.all()[:50]
            if recent_readings.exists():
                try:
                    # Get readings as list of dicts
                    readings_list = list(recent_readings.values(
                        'pressure', 'temperature', 'rotation_speed', 'torque',
                        'vibration', 'power_consumption', 'feed_rate',
                        'moisture_content', 'brix_level'
                    ))
                    
                    if readings_list:
                        if pd is None:
                            continue
                        df = pd.DataFrame(readings_list)
                        prediction = detector.predict_failure(df, window_hours=24)
                        
                        if prediction['failure_risk'] in ['high', 'critical']:
                            high_risk_machines.append({
                                'machine': machine,
                                'risk': prediction['failure_risk'],
                                'probability': prediction['probability'],
                                'recommendation': prediction['recommendation']
                            })
                except Exception as e:
                    # Skip this machine if there's an error
                    continue
    
    # Get farms with yield predictions
    active_farms = Farm.objects.filter(status='active')[:5]
    farm_predictions = []
    
    predictor_path = 'ai_ml/trained_models/yield_predictor.pkl'
    if os.path.exists(predictor_path):
        predictor = FarmYieldPredictor()
        if predictor.load_model(predictor_path):
            for farm in active_farms:
                active_cycle = farm.crop_cycles.filter(
                    current_stage__in=['growing', 'mature']
                ).first()

                if active_cycle:
                    try:
                        prediction = predictor.predict_yield({
                            'area': float(farm.area),
                            'soil_type': farm.soil_type,
                            'variety': active_cycle.variety,
                            'planting_date': active_cycle.planting_date
                        })

                        farm_predictions.append({
                            'farm': farm,
                            'cycle': active_cycle,
                            'predicted_yield': prediction['predicted_yield'],
                            'confidence': prediction['confidence_interval']
                        })
                    except:
                        pass
    
    # Get inventory items needing attention
    low_stock_items = Item.objects.filter(is_active=True)[:10]
    inventory_alerts = []
    
    forecaster_path = 'ai_ml/trained_models/inventory_forecaster.pkl'
    if os.path.exists(forecaster_path):
        forecaster = InventoryDemandForecaster()
        if forecaster.load_model(forecaster_path):
            for item in low_stock_items:
                try:
                    prediction = forecaster.predict_demand(item.id, days_ahead=7)

                    if prediction['reorder_urgency'] in ['high', 'critical']:
                        inventory_alerts.append({
                            'item': item,
                            'predicted_demand': prediction['predicted_demand'],
                            'recommended_order': prediction['recommended_order_qty'],
                            'urgency': prediction['reorder_urgency']
                        })
                except:
                    pass
    
    # AI Statistics
    total_predictions = len(high_risk_machines) + len(farm_predictions) + len(inventory_alerts)
    
    context = {
        'recent_anomalies': recent_anomalies,
        'high_risk_machines': high_risk_machines,
        'farm_predictions': farm_predictions,
        'inventory_alerts': inventory_alerts,
        'total_predictions': total_predictions,
        'anomaly_count': recent_anomalies.count(),
        'risk_machine_count': len(high_risk_machines),
    }
    
    return render(request, 'ai_ml/dashboard.html', context)


@login_required
def machine_health_detail(request, machine_id):
    """Detailed AI analysis for a specific machine."""
    machine = get_object_or_404(CrushingMachine, id=machine_id)

    # Get recent sensor readings
    recent_readings = machine.sensor_readings.all()[:100]

    context = {
        'machine': machine,
        'recent_readings': recent_readings[:20],
        'anomalies': [],
        'health_prediction': None,
        'maintenance_recommendations': [],
    }

    if recent_readings.exists():
        model_path = 'ai_ml/trained_models/anomaly_detector.pkl'
        detector = MachineAnomalyDetector()
        model_loaded = os.path.exists(model_path) and detector.load_model(model_path)

        # Detect anomalies using .values() to avoid Django internal state keys
        sensor_fields = (
            'pressure', 'temperature', 'rotation_speed', 'torque',
            'vibration', 'power_consumption', 'feed_rate',
            'moisture_content', 'brix_level',
        )
        readings_qs = recent_readings[:20]
        readings_list = list(readings_qs.values('id', 'timestamp', *sensor_fields))

        anomalies = []
        if model_loaded:
            for reading_dict in readings_list:
                try:
                    sensor_data = {k: float(v) for k, v in reading_dict.items()
                                   if k in sensor_fields and v is not None}
                    result = detector.detect_anomaly(sensor_data)
                    if result['is_anomaly']:
                        result['reading_id'] = reading_dict['id']
                        result['reading_timestamp'] = reading_dict['timestamp']
                        # Normalise keys for template
                        result.setdefault('type', result.get('severity', 'unknown').title())
                        anomalies.append(result)
                except Exception:
                    continue

        # Predict failure risk
        failure_prediction = None
        if model_loaded and pd is not None and readings_list:
            try:
                df = pd.DataFrame([
                    {k: float(v) for k, v in r.items() if k in sensor_fields and v is not None}
                    for r in readings_list
                ])
                if not df.empty:
                    failure_prediction = detector.predict_failure(df)
            except Exception:
                pass

        # Build health_prediction dict expected by the template
        risk_level = (failure_prediction or {}).get('failure_risk', 'unknown')
        anomaly_rate = (failure_prediction or {}).get('anomaly_rate', 0)
        health_score = max(0, round((1 - anomaly_rate) * 100, 1)) if failure_prediction else None

        priority_map = {'critical': 'urgent', 'high': 'high', 'medium': 'medium', 'low': 'low', 'unknown': 'low'}
        health_prediction = {
            'health_score': health_score,
            'risk_level': risk_level,
            'maintenance_priority': priority_map.get(risk_level, 'low'),
            'recommendation': (failure_prediction or {}).get('recommendation', ''),
        } if failure_prediction else None

        # Maintenance recommendations as a list for the template
        raw_rec = detector.get_maintenance_recommendations(anomalies)
        maintenance_recommendations = [
            {
                'action': action,
                'description': f"Sensor issue detected: {', '.join(raw_rec.get('affected_sensors', []))}",
                'priority': raw_rec.get('priority', 'low'),
                'estimated_time': raw_rec.get('estimated_downtime', 'TBD'),
            }
            for action in raw_rec.get('actions', [])
        ]

        context.update({
            'anomalies': anomalies,
            'health_prediction': health_prediction,
            'maintenance_recommendations': maintenance_recommendations,
        })

    return render(request, 'ai_ml/machine_health.html', context)


@login_required
def farm_yield_analysis(request, farm_id):
    """AI-powered yield analysis for a farm."""
    farm = get_object_or_404(Farm, id=farm_id)
    
    # Get active crop cycle
    active_cycle = farm.crop_cycles.filter(
        current_stage__in=['growing', 'mature']
    ).first()
    
    context = {
        'farm': farm,
        'active_cycle': active_cycle,
        'prediction': None,
        'variety_recommendations': None,
        'planting_recommendations': None
    }
    
    predictor_path = 'ai_ml/trained_models/yield_predictor.pkl'
    if os.path.exists(predictor_path):
        predictor = FarmYieldPredictor()
        if predictor.load_model(predictor_path):
            if active_cycle:
                prediction = predictor.predict_yield({
                    'area': float(farm.area),
                    'soil_type': farm.soil_type,
                    'variety': active_cycle.variety,
                    'planting_date': active_cycle.planting_date
                })
                context['prediction'] = prediction

            variety_rec = predictor.recommend_variety(farm.soil_type, float(farm.area))
            context['variety_recommendations'] = variety_rec

            planting_rec = predictor.optimal_planting_time(farm.location.split(',')[0])
            context['planting_recommendations'] = planting_rec
    
    # Build historical yield and comparison data for charts
    try:
        # Historical: prefer actual_yield; fall back to estimated_yield
        cycles_qs = farm.crop_cycles.filter(
            models.Q(actual_yield__isnull=False) | models.Q(estimated_yield__isnull=False)
        ).order_by('planting_date')
        hist_labels = []
        hist_values = []
        for c in cycles_qs:
            year = c.actual_harvest_date.year if c.actual_harvest_date else c.planting_date.year
            hist_labels.append(str(year))
            # per-acre yield if area available
            base_yield = float(c.actual_yield or c.estimated_yield or 0)
            per_acre = (base_yield / float(farm.area)) if farm.area and float(farm.area) > 0 else base_yield
            hist_values.append(round(per_acre, 2))

        # Comparison: this farm average vs overall average vs best
        # Compute per-acre yield using actual or estimated where possible
        per_acre_expr = ExpressionWrapper(
            Coalesce(F('actual_yield'), F('estimated_yield')) / F('farm__area'),
            output_field=FloatField()
        )
        global_cycles = FarmCropCycle.objects.filter(
            models.Q(farm__area__gt=0) & (
                models.Q(actual_yield__isnull=False) | models.Q(estimated_yield__isnull=False)
            )
        ).annotate(per_acre=per_acre_expr)

        this_farm_vals = list(global_cycles.filter(farm=farm).values_list('per_acre', flat=True))
        this_farm_avg = round(sum(this_farm_vals) / len(this_farm_vals), 2) if this_farm_vals else 0.0
        avg_all = round(global_cycles.aggregate(avg=Avg('per_acre'))['avg'] or 0.0, 2)
        best = 0.0
        try:
            others = list(global_cycles.exclude(farm=farm).values_list('per_acre', flat=True)[:1000])
            combined = this_farm_vals + others
            best = round(max(combined), 2) if combined else 0.0
        except ValueError:
            best = 0.0

        context.update({
            'yield_history_labels': mark_safe(json.dumps(hist_labels)),
            'yield_history_values': mark_safe(json.dumps(hist_values)),
            'yield_comparison_labels': mark_safe(json.dumps(['This Farm', 'Average', 'Best'])),
            'yield_comparison_values': mark_safe(json.dumps([this_farm_avg, avg_all, best]))
        })
    except Exception:
        # If anything fails, just let charts use defaults
        pass

    return render(request, 'ai_ml/farm_yield.html', context)


@login_required
def inventory_forecast_view(request, item_id):
    """AI-powered inventory forecasting for an item."""
    item = get_object_or_404(Item, id=item_id)
    
    # Get transaction history
    transactions = item.inventory_transactions.all()[:90]
    
    context = {
        'item': item,
        'transactions': transactions[:10],
        'forecast': None,
        'seasonal_analysis': None,
        'reorder_recommendation': None
    }
    
    if transactions.exists():
        forecaster_path = 'ai_ml/trained_models/inventory_forecaster.pkl'
        if os.path.exists(forecaster_path):
            forecaster = InventoryDemandForecaster()
            if forecaster.load_model(forecaster_path):
                forecast = forecaster.predict_demand(item.id, days_ahead=7)
                context['forecast'] = forecast

                analyzer = SeasonalDemandAnalyzer()
                if pd is not None:
                    df = pd.DataFrame(list(transactions.values()))
                    if len(df) > 30:
                        seasonal = analyzer.detect_seasonality(df)
                        context['seasonal_analysis'] = seasonal

                        current_month = timezone.now().month
                        seasonal_rec = analyzer.recommend_seasonal_stock(
                            float(item.min_quantity), current_month
                        )
                        context['reorder_recommendation'] = seasonal_rec
    
    return render(request, 'ai_ml/inventory_forecast.html', context)


# API Endpoints for AJAX calls

@login_required
def api_detect_anomaly(request, machine_id):
    """API endpoint to detect anomaly in real-time."""
    machine = get_object_or_404(CrushingMachine, id=machine_id)
    sensor_fields = (
        'pressure', 'temperature', 'rotation_speed', 'torque',
        'vibration', 'power_consumption', 'feed_rate',
        'moisture_content', 'brix_level',
    )
    latest = machine.sensor_readings.values(*sensor_fields).first()

    if not latest:
        return JsonResponse({'error': 'No sensor data available'}, status=404)

    model_path = 'ai_ml/trained_models/anomaly_detector.pkl'
    if not os.path.exists(model_path):
        return JsonResponse({'error': 'Model not trained'}, status=404)

    detector = MachineAnomalyDetector()
    detector.load_model(model_path)

    sensor_data = {k: float(v) for k, v in latest.items() if v is not None}
    result = detector.detect_anomaly(sensor_data)

    return JsonResponse(result)


@login_required
def api_predict_yield(request, farm_id):
    """API endpoint to predict farm yield."""
    farm = get_object_or_404(Farm, id=farm_id)
    active_cycle = farm.crop_cycles.filter(
        current_stage__in=['growing', 'mature']
    ).first()
    
    if not active_cycle:
        return JsonResponse({'error': 'No active crop cycle'}, status=404)
    
    predictor_path = 'ai_ml/trained_models/yield_predictor.pkl'
    if not os.path.exists(predictor_path):
        return JsonResponse({'error': 'Model not trained'}, status=404)
    
    predictor = FarmYieldPredictor()
    predictor.load_model(predictor_path)
    
    prediction = predictor.predict_yield({
        'area': float(farm.area),
        'soil_type': farm.soil_type,
        'variety': active_cycle.variety,
        'planting_date': active_cycle.planting_date
    })
    
    return JsonResponse(prediction)


@login_required
def api_forecast_demand(request, item_id):
    """API endpoint to forecast inventory demand."""
    item = get_object_or_404(Item, id=item_id)
    days_ahead = int(request.GET.get('days', 7))
    
    forecaster_path = 'ai_ml/trained_models/inventory_forecaster.pkl'
    if not os.path.exists(forecaster_path):
        return JsonResponse({'error': 'Model not trained'}, status=404)
    
    forecaster = InventoryDemandForecaster()
    forecaster.load_model(forecaster_path)
    
    forecast = forecaster.predict_demand(item.id, days_ahead=days_ahead)
    
    return JsonResponse(forecast)
