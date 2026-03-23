from collections import defaultdict
from django.db import transaction
from django.db.models import Manager

from src.metrics.querysets import MetricValueQuerySet


class MetricValueManager(Manager):
    """
    Custom manager for the MetricValue model.
    """

    def get_queryset(self):
        # return super().get_queryset().filter(value__isnull=False) # CHECK:
        return MetricValueQuerySet(self.model, using=self._db).filter(value__isnull=False)

    def bulk_create(self, objs, **kwargs):
        """
        Create multiple MetricValue instances in bulk.
        Limitation: all MetricValues must be of the same metric.
        """
        if not objs:
            return []

        values_grouped_by_datetime = defaultdict(list)
        for obj in objs:
            values_grouped_by_datetime[obj.time].append(obj)

        result = []
        with transaction.atomic():
            for grouped_values in values_grouped_by_datetime.values():
                result.extend(super().bulk_create(grouped_values, **kwargs))

        return result

    def filter_by_polygon(self, *args, **kwargs):
        return self.get_queryset().filter_by_polygon(*args, **kwargs)
