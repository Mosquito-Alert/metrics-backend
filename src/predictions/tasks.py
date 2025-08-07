
from datetime import datetime
from celery import shared_task
from django.db import IntegrityError, transaction, models
from django.utils import timezone
from src.utils.datetime import generate_date_range
from src.utils.redis_functions import redis_lock


@shared_task
def refresh_prediction_task(raw_value_id, refresh_progress=True):
    """
    Invokes the predictor and assign the Prediction fields.
    """
    from src.predictions.models import MetricPredictionProgress, Predictor, RawValue

    try:
        raw_value = RawValue.objects.get(id=raw_value_id)
    except RawValue.DoesNotExist:
        return

    predicted_value = raw_value.predicted_value

    aware_datetime = timezone.make_aware(
        datetime.combine(raw_value.time, datetime.min.time())
    )

    if not getattr(predicted_value, 'predictor', None):
        lock_key = f"predictor_lock_{raw_value.boundary}_"
        with redis_lock(lock_key) as lock_acquired:
            if not lock_acquired:
                # If we couldn't acquire the lock, we skip this metric
                return
        try:
            predicted_value.predictor = Predictor.objects.get_not_expired(
                region_id=raw_value.boundary, date=aware_datetime)
        except Predictor.DoesNotExist:
            try:
                with transaction.atomic():
                    predicted_value.predictor = Predictor.objects.create(
                        region_id=raw_value.boundary,
                        last_training_date=aware_datetime,
                    )
            except IntegrityError:
                # If the IntegrityError is raised, it means that another process has already created the predictor
                # and we can safely ignore this error.
                predicted_value.predictor = Predictor.objects.get_not_expired(
                    region_id=raw_value.boundary, date=aware_datetime)
        finally:
            predicted_value.save(update_fields=['predictor'])

    results = predicted_value.predictor.predict(dates=[raw_value.time,])
    if not results:
        return
    try:
        if result := results[0]:
            predicted_value.predicted_value = result['yhat']
            predicted_value.upper_confidence_band = result['yhat_upper']
            predicted_value.lower_confidence_band = result['yhat_lower']
            predicted_value.save()
    except IndexError:
        pass

    if refresh_progress:
        MetricPredictionProgress.refresh(date=raw_value.time)


@shared_task
def predict_batch_task(from_date, to_date, metric_id, boundary_id=None):
    """
    Update the predicted values in the PredictedValue model, given their assigned predictor.
    """
    from src.predictions.models import PredictedValue, Predictor

    predictor_qs = Predictor.objects.filter(
        models.Exists(
            PredictedValue.objects.filter(
                predictor=models.OuterRef('pk'),
                raw_value_time__gte=from_date,
                raw_value_time__lte=to_date,
                raw_value__metric_id=metric_id
            )
        )
    )
    if boundary_id:
        predictor_qs = predictor_qs.filter(boundary_id=boundary_id)

    for predictor in predictor_qs.iterator(chunk_size=2000):
        batch_update_metrics_for_predictor_task.delay(
            predictor_id=predictor.id,
            from_date=from_date,
            to_date=to_date
        )


@shared_task
def batch_update_metrics_for_predictor_task(predictor_id, from_date, to_date):
    """
    Update the predicted values in the PredictedValue model for a specific predictor
    """
    from src.predictions.models import PredictedValue, Predictor, MetricPredictionProgress

    try:
        predictor = Predictor.objects.get(id=predictor_id)
    except Predictor.DoesNotExist:
        return

    results = predictor.predict(dates=list(generate_date_range(from_date, to_date)))
    if not results:
        return

    date_to_pk = {
        predicted_value.raw_value_time: predicted_value
        for predicted_value in predictor.predicted_values.filter(raw_value_time__gte=from_date,
                                                                 raw_value_time__lte=to_date).iterator(chunk_size=1000)
    }

    predicted_value_to_update = []
    for result in results:
        if predicted_value := date_to_pk.get(result['datetime'], None):
            predicted_value.predicted_value = result['yhat']
            predicted_value.upper_confidence_band = result['yhat_upper']
            predicted_value.lower_confidence_band = result['yhat_lower']
            predicted_value_to_update.append(predicted_value)

    if predicted_value_to_update:
        PredictedValue.objects.bulk_update(
            predicted_value_to_update,
            batch_size=2000,
            fields=['predicted_value', 'upper_confidence_band', 'lower_confidence_band']
        )

        # Refresh the prediction progress for every date in the range
        for date in generate_date_range(from_date, to_date):
            MetricPredictionProgress.refresh(time=date)
