from collections import defaultdict
from django.db import transaction
from django.db.models import Manager


class MetricValueManager(Manager):
    """
    Custom manager for the MetricValue model.
    """

    def get_queryset(self):
        return super().get_queryset().filter(value__isnull=False)

    def bulk_create(self, objs, **kwargs):
        """
        Create multiple MetricValue instances in bulk.
        Limitation: all MetricValues must be of the same metric.
        """
        from src.metrics.models import MetricStatistics
        if not objs:
            return []

        values_grouped_by_datetime = defaultdict(list)
        for obj in objs:
            values_grouped_by_datetime[obj.time].append(obj)

        result = []
        with transaction.atomic():
            for time_value, grouped_values in values_grouped_by_datetime.items():
                result.extend(super().bulk_create(grouped_values, **kwargs))

                # Ensure MetricStatistics exists for this time
                MetricStatistics.objects.get_or_create(
                    time=time_value,
                    defaults={'metric': grouped_values[0].metric}
                )

        return result
