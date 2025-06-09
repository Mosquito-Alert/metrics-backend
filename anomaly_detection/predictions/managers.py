from datetime import timedelta
from django.db.models import Manager, Prefetch

from anomaly_detection.regions.models import Municipality


class RegionSelectedManager(Manager):
    """
    Custom manager for the Metric model with the Region selected.
    """

    def get_queryset(self):
        """
        Override the default queryset to return the results with the region selected, and
        the geometry field of the region deferred.
        These are useful for performance reasons (one query and not retrieving the geometry field
        by default).
        """
        return super().get_queryset().select_related('region').defer('region__geometry')

    def with_geometry(self):
        """
        Return the queryset with the geometry field included.
        This is useful for when you need to access the geometry data.
        """
        return super().get_queryset().select_related('region').prefetch_related(
            Prefetch('region', queryset=Municipality.objects.with_geometry().defer(
                'predictor'))  # .filter(pk=OuterRef('region'))
        )


class PredictorManager(Manager):
    """
    Custom manager for the Predictor model.
    """

    def get_not_expired(self, region_id, date):
        """
        Get the last predictor that is not expired for a given region and date.
        """
        return super().get_queryset().filter(
            region_id=region_id,
            last_training_date__lte=date,
            last_training_date__gte=(date - timedelta(days=self.model.EXPIRY_DAYS))
        ).latest('last_training_date')
