from django.db.models import Manager


class RegionManager(Manager):
    """
    Custom manager for the Region model.
    """

    def get_queryset(self):
        """
        Override the default queryset to return the results without the geometry field.
        This is useful for performance reasons when the geometry field is not needed.
        """
        return super().get_queryset().defer('geometry')

    # TODO: Custom queryset that defers the geometry, so I can chain it in different parts of the chain.

    def with_geometry(self):
        """
        Return the queryset with the geometry field included.
        This is useful for when you need to access the geometry data.
        """
        return super().get_queryset()
