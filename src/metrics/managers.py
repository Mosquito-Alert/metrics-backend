from django.db import transaction
from django.db.models import Manager


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
