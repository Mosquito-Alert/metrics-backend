
from datetime import datetime
from celery import shared_task
from django.db import IntegrityError, transaction, models
from django.utils import timezone
from anomaly_detection.utils.datetime import generate_date_range


@shared_task
def refresh_prediction_task(metric_id, refresh_progress=True):
    """
    Invokes the predictor and assign the Prediction fields.
    """
    from anomaly_detection.predictions.models import Metric, MetricPredictionProgress, Predictor

    try:
        metric = Metric.objects.get(id=metric_id)
    except Metric.DoesNotExist:
        return

    aware_datetime = timezone.make_aware(
        datetime.combine(metric.date, datetime.min.time())
    )

    if not getattr(metric, 'predictor', None):
        try:
            metric.predictor = Predictor.objects.get_not_expired(region_id=metric.region, date=aware_datetime)
        except Predictor.DoesNotExist:
            try:
                with transaction.atomic():
                    metric.predictor = Predictor.objects.create(
                        region_id=metric.region_id,
                        last_training_date=aware_datetime,
                    )
            except IntegrityError:
                # If the IntegrityError is raised, it means that another process has already created the predictor
                # and we can safely ignore this error.
                metric.predictor = Predictor.objects.get_not_expired(region_id=metric.region, date=aware_datetime)
        finally:
            metric.save(update_fields=['predictor'])

    results = metric.predictor.predict(dates=[metric.date,])
    if not results:
        return
    try:
        if result := results[0]:
            metric.predicted_value = result['yhat']
            metric.upper_value = result['yhat_upper']
            metric.lower_value = result['yhat_lower']
            metric.save()
    except IndexError:
        pass

    if refresh_progress:
        MetricPredictionProgress.refresh(date=metric.date)


@shared_task
def predict_batch_task(from_date, to_date, region_id=None):
    """
    Update the predicted values in the Metric model, given their assigned predictor.
    """
    from anomaly_detection.predictions.models import Metric, Predictor

    predictor_qs = Predictor.objects.filter(
        models.Exists(
            Metric.objects.filter(
                predictor=models.OuterRef('pk'),
                date__gte=from_date,
                date__lte=to_date
            )
        )
    )
    if region_id:
        predictor_qs = predictor_qs.filter(region_id=region_id)

    for predictor in predictor_qs.iterator(chunk_size=2000):
        batch_update_metrics_for_predictor_task.delay(
            predictor_id=predictor.id,
            from_date=from_date,
            to_date=to_date
        )


@shared_task
def batch_update_metrics_for_predictor_task(predictor_id, from_date, to_date):
    """
    Update the predicted values in the Metric model for a specific predictor
    """
    from anomaly_detection.predictions.models import Metric, Predictor, MetricPredictionProgress

    try:
        predictor = Predictor.objects.get(id=predictor_id)
    except Predictor.DoesNotExist:
        return

    date_to_pk = {
        metric.date: metric
        for metric in predictor.metrics.filter(date__gte=from_date, date__lte=to_date).iterator(chunk_size=1000)
    }

    metric_to_update = []
    for result in predictor.predict(dates=list(generate_date_range(from_date, to_date))):
        if metric := date_to_pk.get(result['datetime'].date(), None):
            metric.predicted_value = result['yhat']
            metric.upper_value = result['yhat_upper']
            metric.lower_value = result['yhat_lower']
            metric_to_update.append(metric)

    if metric_to_update:
        Metric.objects.bulk_update(
            metric_to_update,
            batch_size=2000,
            fields=['predicted_value', 'upper_value', 'lower_value']
        )

        # Refresh the prediction progress for every date in the range
        for date in generate_date_range(from_date, to_date):
            MetricPredictionProgress.refresh(date=date)
