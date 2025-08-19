from datetime import timedelta
from django.db import transaction
from django.db.models import Manager


class PredictorManager(Manager):
    """
    Custom manager for the Predictor model.
    """

    def get_not_expired(self, h3_id, date):
        """
        Get the last predictor that is not expired for a given H3 ID and date.
        """
        return super().get_queryset().filter(
            h3_id=h3_id,
            trained_at__lte=date,
            trained_at__gte=(date - timedelta(days=self.model.EXPIRY_DAYS))
        ).latest('trained_at')


# TODO: Create queryset method to  filter MetricValue that has value == None

class MetricValueManager(Manager):
    """
    Custom manager for the MetricValue model.
    """

    #  TODO: def get_queryset ...

    def bulk_create(self, objs, **kwargs):
        """
        Create multiple MetricValue instances in bulk.
        Limitation: all MetricValues must have the same time.
        """
        from src.metrics.models import MetricStatistics
        if not objs:
            return []

        # Since all MetricValues have the same datetime, pick the first one
        # NOTE: This is a current limitation, ideally we should handle different times
        first_time = objs[0].time

        with transaction.atomic():
            result = super().bulk_create(objs, **kwargs)

            # TODO: Itertools.groupby to group by time and create MetricStatistics for each group
            # Ensure MetricStatistics exists for this time
            MetricStatistics.objects.get_or_create(
                time=first_time,
                defaults={'metric': objs[0].metric}
            )

        return result
