import math
from datetime import datetime
from typing import Optional, TypedDict

from django_lifecycle import LifecycleModelMixin
import h3
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework.fields import MaxValueValidator, MinValueValidator

from src.metrics.managers import MetricValueManager
from src.utils.database_features import H3Field, H3IsValidCell, RealField
from src.utils.datetime import clean_time_field


class PredictionResult(TypedDict):
    datetime: datetime
    yhat: float
    yhat_upper: float
    yhat_lower: float


class Metric(models.Model):
    """
    Model to store the different metrics.
    For example, the Bites Index, the Suitability Index, etc.
    """
    class TimeDimensionStepType(models.IntegerChoices):
        """
        Time dimension step for the metric.
        """
        DAILY = 1, _('Daily')
        HOURLY = 2, _('Hourly')

    name = models.CharField(
        max_length=255,
        unique=True, null=False, blank=False,
        verbose_name=_('Name'),
        help_text=_('The name of the metric.')
    )
    code = models.SlugField(
        max_length=32,
        unique=True, null=False, blank=False,
        verbose_name=_('Code'),
        help_text=_('The code of the metric, used for identification purposes. Example: bites.'),
    )
    time_dimension_step = models.PositiveSmallIntegerField(
        choices=TimeDimensionStepType.choices,
        null=False, blank=True,
        default=TimeDimensionStepType.DAILY,
        verbose_name=_('Time Dimension Step'),
        help_text=_('The time dimension step for the metric. Minutes are the smallest unit.')
    )
    is_predictable = models.BooleanField(
        null=False, blank=False,
        verbose_name=_('Is Predictable'),
        help_text=_('Whether the metric is predictable or not. If true, the metric will have a predictor '
                    'associated to it, and the values will be predicted.'),
    )
    h3_resolution = models.PositiveSmallIntegerField(
        default=6,
        null=False, blank=False,
        verbose_name=_('H3 Resolution'),
        help_text=_('The H3 resolution of the metric. This is used to determine the H3 index of the metric.'),
        validators=[MinValueValidator(0), MaxValueValidator(15)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Metric')
        verbose_name_plural = _('Metrics')

    def __str__(self):
        return self.name


class PredictorConfig(models.Model):
    """
    Model to store the configuration of the predictor.
    """
    metric = models.OneToOneField(
        Metric,
        on_delete=models.CASCADE,
        related_name='predictor_config',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the predictor configuration.')
    )
    yearly_seasonality = models.BooleanField(
        null=False, blank=False,
        default=True,
        verbose_name=_('Yearly Seasonality'),
        help_text=_('Whether the predictor should consider yearly seasonality.')
    )
    weekly_seasonality = models.BooleanField(
        null=False, blank=False,
        default=False,
        verbose_name=_('Weekly Seasonality'),
        help_text=_('Whether the predictor should consider weekly seasonality.')
    )
    daily_seasonality = models.BooleanField(
        null=False, blank=False,
        default=False,
        verbose_name=_('Daily Seasonality'),
        help_text=_('Whether the predictor should consider daily seasonality.')
    )
    growth = models.CharField(
        max_length=32,
        null=False, blank=False,
        default='logistic',
        verbose_name=_('Growth'),
        help_text=_('The growth model to use for the predictor.'),
    )

    def __str__(self):
        return f"Predictor Config for {self.metric.name}"

    class Meta:
        verbose_name = _('Predictor Config')
        verbose_name_plural = _('Predictor Configs')


class MetricValue(models.Model, LifecycleModelMixin):
    """
    Model to store the raw and predicted values of a metric.
    """
    pk = models.CompositePrimaryKey(
        'metric', 'h3_index', 'time',
        verbose_name=_('Primary Key'),
        help_text=_('The primary key of the metric value, composed by the metric, h3 index and time.')
    )
    metric = models.ForeignKey(
        Metric,
        blank=True,
        on_delete=models.CASCADE,
        related_name='values',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the value.')
    )
    h3_index = H3Field(
        null=False,
        blank=True,
        verbose_name=_('H3 Index'),
        help_text=_(
            'The H3 index of the metric value boundary, used for spatial queries. '
            'This is stored as a bigInt to avoid issues with large indices, '
            'so it should be converted to/from hex strings if necessary.'
        ),
    )
    time = models.DateTimeField(
        null=False, blank=True,
        verbose_name=_('Time'),
        help_text=_('The time in which the raw value was recorded. Maximum precision is one minute.'),
    )
    value = RealField(
        null=True, blank=True,
        verbose_name=_('Value'),
        help_text=_('The actual value of the raw data.'),
    )
    time_dimension = models.ForeignObject(
        'MetricTimeDimension',
        blank=False,
        on_delete=models.CASCADE,
        from_fields=['metric', 'time'],
        to_fields=['metric', 'time'],
        related_name='metric_values',
    )
    spatial_dimension = models.ForeignObject(
        'MetricSpatialDimension',
        blank=False,
        on_delete=models.CASCADE,
        from_fields=['metric', 'h3_index'],
        to_fields=['metric', 'h3_index'],
        related_name='metric_values',
    )
    # Predictor fields
    # NOTE: We can't separate these fields into a different model because TimescaleDB needs a composite
    # primary key to work properly, and having a separate model would need three additional fields
    # (metric_id, h3_index, time) to be able to link that model with the MetricValue model.
    # It is preferible then to have these fields nullable (null takes only 1 bit per nullable field).
    predicted_value = RealField(
        null=True, blank=True,
        verbose_name=_('Value'),
        help_text=_('The predicted value.')
    )
    lower_confidence_band = RealField(
        null=True, blank=True,
        verbose_name=_('Lower Confidence Band'),
        help_text=_('The lower confidence band of the predicted value.')
    )
    upper_confidence_band = RealField(
        null=True, blank=True,
        verbose_name=_('Upper Confidence Band'),
        help_text=_('The upper confidence band of the predicted value.')
    )
    anomaly_degree = RealField(
        null=True, blank=True,
        verbose_name=_('Anomaly Degree'),
        help_text=_('The degree of the anomaly, a range of values that starts on -1 (a lower anomaly of the '
                    'highest degree) and ends on +1 (a upper anomaly of the highest degree). The 0 value means that '
                    'there is no anomaly. This value will be estimated at creation.')
    )

    objects = MetricValueManager()

    def refresh_prediction(self) -> None:
        """
        (Async) Invokes the predictor and assign the Prediction fields.
        """
        pass
        # refresh_prediction_task(self.metric.id, self.h3_index, self.time, refresh_progress=refresh_progress)
        # refresh_prediction_task.delay(self.metric.id, self.h3_index, self.time, refresh_progress=refresh_progress)

    def calculate_anomaly_degree(self) -> Optional[float]:
        """
        Calculates the anomaly degree based on the value and confidence bands.
        """
        anomaly_degree = None
        if self.value is not None and self.lower_confidence_band is not None and self.upper_confidence_band is not None:
            if self.value == 0:
                # Handle the value == 0 case explicitly
                if self.upper_confidence_band < 0:
                    anomaly_degree = 1.0
                elif self.lower_confidence_band > 0:
                    anomaly_degree = -1.0
                else:
                    anomaly_degree = 0.0
            # Value above upper confidence band
            elif self.value > self.upper_confidence_band:
                anomaly_degree = (self.value - self.upper_confidence_band) / self.value
            # Value below lower confidence band
            elif self.value < self.lower_confidence_band:
                anomaly_degree = (self.value - self.lower_confidence_band) / self.value
            # Value within confidence bands
            else:
                anomaly_degree = 0.0

        return anomaly_degree

    def clean(self):
        # Raise validationerror if time_dimension is not provided:
        try:
            self.time_dimension
        except ObjectDoesNotExist:
            raise ValidationError("Time dimension must be provided.")
        try:
            self.spatial_dimension
        except ObjectDoesNotExist:
            raise ValidationError("Spatial dimension must be provided.")
        if self.time_dimension.metric != self.spatial_dimension.metric:
            raise ValidationError("Time and spatial dimensions must be from the same metric.")

        # H3 Index Validation
        try:
            int(self.h3_index, 16)
        except TypeError:
            raise ValidationError("Invalid H3 index. Needs to be hexadecimal.")
        if not h3.is_valid_cell(self.h3_index):
            raise ValidationError(
                "The H3 index must be a valid H3 cell."
            )
        if h3.get_resolution(self.h3_index) != self.metric.h3_resolution:
            raise ValidationError(
                f"The H3 index ({self.h3_index}) must have the same resolution as the metric."
            )

        # Value Validation
        if self.value is not None and math.isnan(self.value):
            self.value = None
        if self.value is None and self.predicted_value is None:
            raise ValidationError(
                "Either 'value' or 'predicted_value' must be provided."
            )
        if self._state.adding or self.has_changed(field_name='time'):
            self.time = clean_time_field(self.time, self.metric)

        super().clean()

    def save(self, *args, **kwargs):
        self.clean()

        self.anomaly_degree = self.calculate_anomaly_degree()

        is_adding = self._state.adding

        super().save(*args, **kwargs)

        if is_adding:  # A new object is being created
            self.time_dimension.increase_total_cells()
            if self.metric.is_predictable:
                # If the Metric is being created, we need to assign a predictor and refresh the prediction
                self.refresh_prediction()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['metric', 'h3_index', 'time'], name='unique_metric'
            ),
            models.CheckConstraint(
                check=H3IsValidCell(models.F('h3_index')),
                name='h3_index_must_be_valid',
            ),
            models.CheckConstraint(
                check=models.Q(value__isnull=False) | models.Q(predicted_value__isnull=False),
                name='value_or_predicted_value_must_be_present',
            )
        ]
        ordering = ['metric', 'h3_index', '-time']
        indexes = [
            models.Index(fields=['metric', 'h3_index', 'time'],)
        ]
        verbose_name = _('Metric Value')
        verbose_name_plural = _('Metric Values')

    def __str__(self):
        return f"{self.metric.name} on {self.time} for {self.h3_index}: {self.value}"


class MetricTimeDimension(models.Model, LifecycleModelMixin):
    """
    Model to store the metric time dimension related attributes.
    """
    class MetricValueType(models.IntegerChoices):
        """
        Type of the metric value.
        """
        REANALYSIS = 1, _('Reanalysis')
        FORECAST = 2, _('Forecast')

    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name='time_dimensions',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the time dimensions.')
    )
    time = models.DateTimeField(
        null=False, blank=False,
        verbose_name=_('Time'),
        help_text=_('The date and time of the metric values.')
    )
    type = models.PositiveSmallIntegerField(
        choices=MetricValueType.choices,
        null=False, blank=False,
        verbose_name=_('Type'),
        help_text=_('The type of the raw value.')
    )
    total_cells = models.IntegerField(
        null=False, blank=True, default=0,
        verbose_name=_('Total Cells'),
        help_text=_('The total number of cells.')
    )
    total_cells_predicted = models.IntegerField(
        null=True, blank=True,
        verbose_name=_('Total Cells Completed'),
        help_text=_('The total number of cells processed with a prediction.'),
    )
    prediction_progress = models.GeneratedField(
        expression=models.Case(
            models.When(total_cells_predicted__isnull=True, then=models.Value(None)),
            default=models.F('total_cells_predicted') * 1.0 / models.F('total_cells')
        ),
        output_field=RealField(),
        # If db_persist is set to false, then the field will not be persisted in the database
        # and the computed value will be calculated on the READ queries, which is not optimal.
        db_persist=True,
        null=True, blank=True,
        verbose_name=_('Prediction Progress'),
        help_text=_('The percentage of cells completed with a prediction.'),
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )

    def increase_total_cells_predicted(self, inc_value=1):
        """
        Increment the total finished count.
        """
        self.total_cells_predicted = models.Case(
            models.When(total_cells_predicted__isnull=True, then=models.Value(inc_value)),
            default=models.F('total_cells_predicted') + inc_value
        )
        self.save(update_fields=['total_cells_predicted'])
        self.refresh_from_db(fields=['total_cells_predicted'])

    def increase_total_cells(self, inc_value=1):
        """
        Increment the total cells count.
        """
        self.total_cells = models.F('total_cells') + inc_value
        self.save(update_fields=['total_cells'])
        self.refresh_from_db(fields=['total_cells'])

    def save(self, *args, **kwargs):
        if self._state.adding or self.has_changed(field_name='time'):
            self.time = clean_time_field(self.time, self.metric)
            self.total_cells = self.metric.values.filter(time=self.time).count()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Statistics for the metric {self.metric.name} at {self.time}."

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['metric', 'time'], name='unique_metric_time_dimension'
            ),
        ]
        ordering = ['metric', '-time']
        indexes = [
            models.Index(fields=['metric', 'time'])
        ]
        verbose_name = "Metric Time Dimension"
        verbose_name_plural = "Metric Time Dimensions"


class MetricSpatialDimension(models.Model):
    """
    Model to store the metric spatial dimension related attributes.
    """
    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name='spatial_dimensions',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the spatial dimensions.')
    )
    h3_index = H3Field(
        null=False, blank=False,
        verbose_name=_('H3 Index'),
        help_text=_('The H3 index of the region.'),
    )
    trend = ArrayField(
        base_field=RealField(),
        null=True, blank=True,
        verbose_name=_('Trend'),
        help_text=_('The predicted trend for the metric.')
    )
    yearly_seasonality = ArrayField(  # ! CAREFUL: The type ArrayField only works in PostgreSQL
        base_field=RealField(),  # ! CAREFUL: The type RealField only works in PostgreSQL
        size=365,
        null=True, blank=True,
        verbose_name=_('Yearly Seasonality'),
        help_text=_('The predicted yearly seasonality for the metric.')
    )
    weekly_seasonality = ArrayField(
        base_field=RealField(),
        size=7,
        null=True, blank=True,
        verbose_name=_('Weekly Seasonality'),
        help_text=_('The predicted weekly seasonality for the metric.')
    )
    daily_seasonality = ArrayField(
        base_field=RealField(),
        size=24,
        null=True, blank=True,
        verbose_name=_('Daily Seasonality'),
        help_text=_('The predicted daily seasonality for the metric.')
    )

    def clean(self):
        # H3 Index Validation
        try:
            int(self.h3_index, 16)
        except TypeError:
            raise ValidationError("Invalid H3 index. Needs to be hexadecimal.")
        if not h3.is_valid_cell(self.h3_index):
            raise ValidationError(
                "The H3 index must be a valid H3 cell."
            )
        if h3.get_resolution(self.h3_index) != self.metric.h3_resolution:
            raise ValidationError(
                f"The H3 index ({self.h3_index}) must have the same resolution as the metric."
            )

        super().clean()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['metric', 'h3_index'],
                name='spaial_dimension_unique_metric_h3_index'
            ),
            models.CheckConstraint(
                check=H3IsValidCell(models.F('h3_index')),
                name='spatial_dimension_h3_index_must_be_valid'
            ),
        ]
        ordering = ['metric', 'h3_index']
        indexes = [
            models.Index(fields=['metric', 'h3_index'])
        ]
        verbose_name = _('Metric Spatial Dimension')
        verbose_name_plural = _('Metric Spatial Dimensions')

    def __str__(self):
        return f"Spatial Dimension for metric {self.metric.name} in H3 cell {self.h3_index}"
