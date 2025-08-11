from datetime import timedelta
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
