
from datetime import datetime
from celery import shared_task
from django.db import IntegrityError, transaction, models
from django.utils import timezone
from src.utils.datetime import generate_date_range
from src.utils.redis_functions import redis_lock


@shared_task
def refresh_prediction_task(metric_id, h3_index, time, refresh_progress=True):
    """
    Invokes the predictor and assign the Prediction fields.
    """
    from src.metrics.models import MetricPredictionProgress, Predictor, MetricValue

    try:
        metric_value = MetricValue.objects.get(
            metric_id=metric_id, h3_index=h3_index, time__date=time.date()
        )
    except MetricValue.DoesNotExist:
        return

    # TODO: Review if this is still needed
    aware_datetime = timezone.make_aware(
        datetime.combine(metric_value.time, datetime.min.time())
    )

    if not getattr(metric_value, 'predictor', None):
        lock_key = f"predictor_lock_{metric_value.h3_index}_"
        with redis_lock(lock_key) as lock_acquired:
            if not lock_acquired:
                # If we couldn't acquire the lock, we skip this metric
                return
        try:
            metric_value.predictor = Predictor.objects.get_not_expired(
                region_id=metric_value.h3_index, date=aware_datetime)
        except Predictor.DoesNotExist:
            try:
                with transaction.atomic():
                    metric_value.predictor = Predictor.objects.create(
                        metric_id=metric_value.metric_id,
                        region_id=metric_value.h3_index,
                        last_training_date=aware_datetime,
                    )
            except IntegrityError:
                # If the IntegrityError is raised, it means that another process has already created the predictor
                # and we can safely ignore this error.
                metric_value.predictor = Predictor.objects.get_not_expired(
                    metric_id=metric_value.metric_id,
                    region_id=metric_value.h3_index, date=aware_datetime)
        finally:
            metric_value.save(update_fields=['predictor'])

    results = metric_value.predictor.predict(dates=[metric_value.time,])
    if not results:
        return
    try:
        if result := results[0]:
            metric_value.predicted_value = result['yhat']
            metric_value.upper_confidence_band = result['yhat_upper']
            metric_value.lower_confidence_band = result['yhat_lower']
            metric_value.anomaly_degree = metric_value.calculate_anomaly_degree()
            metric_value.save()
    except IndexError:
        pass

    if refresh_progress:
        MetricPredictionProgress.refresh(metric=metric_value.metric, date=metric_value.time)


# @shared_task
# def predict_batch_task(from_date, to_date, metric_id, h3_index=None):
#     """
#     Update the predicted values in the MetricValue model, given their assigned predictor.
#     """
#     from src.metrics.models import MetricValue, Predictor

#     predictor_qs = Predictor.objects.filter(
#         models.Exists(
#             MetricValue.objects.filter(
#                 predictor=models.OuterRef('pk'),
#                 time__gte=from_date,
#                 time__lte=to_date,
#                 metric_id=metric_id
#             )
#         )
#     )
#     if h3_index:
#         predictor_qs = predictor_qs.filter(h3_index=h3_index)

#     for predictor in predictor_qs.iterator(chunk_size=2000):
#         batch_update_metrics_for_predictor_task.delay(
#             predictor_id=predictor.id,
#             from_date=from_date,
#             to_date=to_date
#         )


# @shared_task
# def batch_update_metrics_for_predictor_task(predictor_id, from_date, to_date):
#     """
#     Update the predicted values in the MetricValue model for a specific predictor
#     """
#     from src.metrics.models import MetricValue, Predictor, MetricPredictionProgress

#     try:
#         predictor = Predictor.objects.get(id=predictor_id)
#     except Predictor.DoesNotExist:
#         return

#     results = predictor.predict(dates=list(generate_date_range(from_date, to_date)))
#     if not results:
#         return

#     date_to_pk = {
#         value.time: value
#         for value in predictor.values.filter(time__gte=from_date, time__lte=to_date).iterator(chunk_size=1000)
#     }

#     metric_value_to_update = []
#     for result in results:
#         if metric_value := date_to_pk.get(result['datetime'], None):
#             metric_value.predicted_value = result['yhat']
#             metric_value.upper_confidence_band = result['yhat_upper']
#             metric_value.lower_confidence_band = result['yhat_lower']
#             metric_value_to_update.append(metric_value)

#     if metric_value_to_update:
#         MetricValue.objects.bulk_update(
#             metric_value_to_update,
#             batch_size=2000,
#             fields=['predicted_value', 'upper_confidence_band', 'lower_confidence_band']
#         )

#         # Refresh the prediction progress for every date in the range
#         for date in generate_date_range(from_date, to_date):
#             MetricPredictionProgress.refresh(time=date)
