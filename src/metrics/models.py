import math
from datetime import datetime
from typing import Optional, TypedDict

from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.fields import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError

from src.metrics.managers import MetricValueManager
# from src.metrics.tasks import refresh_prediction_task
from src.utils.database_features import H3Field, H3IsValidCell, RealField


class PredictionResult(TypedDict):
    datetime: datetime
    yhat: float
    yhat_upper: float
    yhat_lower: float


class H3Model(models.Model):
    """
    Model mixin to store the h3 index of a metric.
    """
    h3_index = H3Field(
        null=False,
        blank=False,
        verbose_name=_('H3 Index'),
        help_text=_(
            'The H3 index of the metric value boundary, used for spatial queries. '
            'This is stored as a bigInt to avoid issues with large indices, '
            'so it should be converted to/from hex strings if necessary.'
        ),
    )

    class Meta:
        abstract = True


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

    name = models.CharField(max_length=255, unique=True, blank=False,
                            null=False,
                            verbose_name=_('Name'),
                            help_text=_('The name of the metric.'))
    code = models.SlugField(
        max_length=32,
        unique=True,
        blank=False,
        null=False,
        verbose_name=_('Code'),
        help_text=_('The code of the metric, used for identification purposes. Example: bites.'),
    )
    time_dimension_step = models.PositiveSmallIntegerField(
        choices=TimeDimensionStepType.choices,
        null=False,
        blank=True,
        default=TimeDimensionStepType.DAILY,
        verbose_name=_('Time Dimension Step'),
        help_text=_('The time dimension step for the metric. Minutes are the smallest unit.')
    )
    is_predictable = models.BooleanField(
        blank=False,
        null=False,
        verbose_name=_('Is Predictable'),
        help_text=_('Whether the metric is predictable or not. If true, the metric will have a predictor '
                    'associated to it, and the values will be predicted.'),
    )
    h3_resolution = models.PositiveSmallIntegerField(
        default=6,
        blank=False,
        null=False,
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


class MetricValue(H3Model):
    """
    Model to store the raw and predicted values of a metric.
    """
    class MetricValueType(models.IntegerChoices):
        """
        Type of the metric value.
        """
        REANALYSIS = 1, _('Reanalysis')
        FORECAST = 2, _('Forecast')

    pk = models.CompositePrimaryKey(
        'metric', 'h3_index', 'time',
        verbose_name=_('Primary Key'),
        help_text=_('The primary key of the metric value, composed by the metric, h3 index and time.')
    )
    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name='values',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the value.')
    )
    time = models.DateTimeField(
        null=False,
        blank=False,
        verbose_name=_('Time'),
        help_text=_('The time in which the raw value was recorded. Maximum precision is one minute.'),
    )
    value = RealField(
        null=True,
        blank=True,
        verbose_name=_('Value'),
        help_text=_('The actual value of the raw data.'),
    )
    type = models.PositiveSmallIntegerField(
        choices=MetricValueType.choices,
        null=False,
        blank=False,
        verbose_name=_('Type'),
        help_text=_('The type of the raw value.')
    )
    # Predictor fields
    # NOTE: We can't separate these fields into a different model because TimescaleDB needs a composite
    # primary key to work properly, and having a separate model would need three additional fields
    # (metric_id, h3_index, time) to be able to link that model with the MetricValue model.
    # It is preferible then to have these fields nullable (null takes only 1 bit per nullable field).
    predicted_value = RealField(
        null=True,
        blank=True,
        verbose_name=_('Value'),
        help_text=_('The predicted value.')
    )
    lower_confidence_band = RealField(
        null=True,
        blank=True,
        verbose_name=_('Lower Confidence Band'),
        help_text=_('The lower confidence band of the predicted value.')
    )
    upper_confidence_band = RealField(
        null=True,
        blank=True,
        verbose_name=_('Upper Confidence Band'),
        help_text=_('The upper confidence band of the predicted value.')
    )
    anomaly_degree = RealField(
        null=True,
        blank=True,
        verbose_name=_('Anomaly Degree'),
        help_text=_('The degree of the anomaly, a range of values that starts on -1 (a lower anomaly of the '
                    'highest degree) and ends on +1 (a upper anomaly of the highest degree). The 0 value means that '
                    'there is no anomaly. This value will be estimated at creation.')
    )

    objects = MetricValueManager()

    def refresh_prediction(self, refresh_progress: bool = True) -> None:
        """
        (Async) Invokes the predictor and assign the Prediction fields.
        """
        # refresh_prediction_task(self.metric.id, self.h3_index, self.time, refresh_progress=refresh_progress)
        # refresh_prediction_task.delay(self.metric.id, self.h3_index, self.time, refresh_progress=refresh_progress)

    def calculate_anomaly_degree(self) -> Optional[float]:
        """
        Calculates the anomaly degree based on the value and confidence bands.
        """
        anomaly_degree = None
        if self.value is not None:
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

    def save(self, *args, **kwargs):
        is_adding = self._state.adding  # A new object is being created
        # TODO: From kwargs get the update_fields and depending if the "value" or "time" is in there,
        # execute the following code or not.
        if self.value is not None and math.isnan(self.value):
            self.value = None

        # Round time to minute precision
        self.time = self.time.replace(second=0, microsecond=0)
        # Round time to Metric.time_dimension_step precision
        if self.metric.time_dimension_step == Metric.TimeDimensionStepType.HOURLY:
            self.time = self.time.replace(minute=0)
        elif self.metric.time_dimension_step == Metric.TimeDimensionStepType.DAILY:
            self.time = self.time.replace(hour=0, minute=0)

        # Save the initial Metric with the prediction values and the predictor to None.
        super().save(*args, **kwargs)

        # Assign a predictor to the Metric and set the prediction values.
        if is_adding:
            MetricStatistics.objects.get_or_create(
                time=self.time,
                metric=self.metric,
            )
            if self.metric.is_predictable:
                # If the Metric is being created, we need to assign a predictor and refresh the prediction
                self.refresh_prediction()

    def clean(self):
        super().clean()
        if self.value is None and self.predicted_value is None:
            raise ValidationError(
                "Either 'value' or 'predicted_value' must be provided."
            )

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
        verbose_name = _('Value')
        verbose_name_plural = _('Values')

    def __str__(self):
        return f"{self.metric.name} on {self.time} for {self.h3_index}: {self.value}"


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
        default=True,
        blank=False,
        null=False,
        verbose_name=_('Yearly Seasonality'),
        help_text=_('Whether the predictor should consider yearly seasonality.')
    )
    weekly_seasonality = models.BooleanField(
        default=False,
        blank=False,
        null=False,
        verbose_name=_('Weekly Seasonality'),
        help_text=_('Whether the predictor should consider weekly seasonality.')
    )
    daily_seasonality = models.BooleanField(
        default=False,
        blank=False,
        null=False,
        verbose_name=_('Daily Seasonality'),
        help_text=_('Whether the predictor should consider daily seasonality.')
    )
    growth = models.CharField(
        max_length=32,
        default='logistic',
        blank=False,
        null=False,
        verbose_name=_('Growth'),
        help_text=_('The growth model to use for the predictor.'),
    )
    # TODO: Not days, but depending on the time_dimension_step
    expiry_days = models.PositiveIntegerField(
        default=30,
        blank=False,
        null=False,
        verbose_name=_('Expiry Days'),
        help_text=_('The number of days the predictor is valid for.')
    )
    # TODO: Maybe delete this columns and get the value from the smaller seasonality active.length * 2
    # Si el count es menor de  30 puntos, esperar a tener más datos
    # Antes de tener datos entrenados, banda con los valores max y min del histórico no entrenado.
    min_days_for_training = models.PositiveIntegerField(
        default=30,
        blank=False,
        null=False,
        verbose_name=_('Minimum Days for Training'),
        help_text=_('The minimum number of days of historical data required for training the predictor.')
    )

    def __str__(self):
        return f"Predictor Config for {self.metric.name}"

    class Meta:
        verbose_name = _('Predictor Config')
        verbose_name_plural = _('Predictor Configs')


class MetricStatistics(models.Model):
    """
    Model to store the metric statistics  information.
    Every time the metric values are updated, a prediction will be executed.
    """
    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name='statistics',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the statistics.')
    )
    time = models.DateTimeField(
        unique=True,
        null=False,
        blank=False,
        verbose_name=_('Time'),
        help_text=_('The date and time of the execution.')
    )
    # Percentage of values successfully predicted and saved.
    prediction_progress = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Success percentage'),
        help_text=_('The percentage of success of the execution.'),
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )

    @classmethod
    def refresh(cls, metric: Metric, time: datetime) -> None:
        with transaction.atomic():
            metric_values_qs = MetricValue.objects.filter(metric=metric, time=time)
            total = metric_values_qs.count()
            total_finished = metric_values_qs.filter(predicted_value__isnull=False).count()

            prediction_progress = 0
            if total > 0:
                prediction_progress = total_finished / total

            cls.objects.update_or_create(
                time=time,
                defaults={'prediction_progress': prediction_progress}
            )

    def __str__(self):
        return f"Statistics for the metric metric {self.metric.name} at {self.time}."

    class Meta:
        ordering = ['time']
        indexes = [
            models.Index(fields=['-time'])
        ]
        verbose_name = "Metric Statistics"
        verbose_name_plural = "Metrics Statistics"


class MetricRegionalStatistics(models.Model):
    """
    Model to store the regional statistics for a metric.
    This is used to store the statistics for a specific region (H3 index).
    """
    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name='regional_statistics',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the regional statistics.')
    )
    h3_index = H3Field(
        null=False,
        blank=False,
        verbose_name=_('H3 Index'),
        help_text=_('The H3 index of the region.'),
    )
    trend = ArrayField(
        base_field=RealField(),
        null=True,
        blank=True,
        verbose_name=_('Trend'),
        help_text=_('The predicted trend for the metric.')
    )
    yearly_seasonality = ArrayField(  # ! CAREFUL: The type ArrayField only works in PostgreSQL
        base_field=RealField(),  # ! CAREFUL: The type RealField only works in PostgreSQL
        size=365,
        null=True,
        blank=True,
        verbose_name=_('Yearly Seasonality'),
        help_text=_('The predicted yearly seasonality for the metric.')
    )
    weekly_seasonality = ArrayField(
        base_field=RealField(),
        size=7,
        null=True,
        blank=True,
        verbose_name=_('Weekly Seasonality'),
        help_text=_('The predicted weekly seasonality for the metric.')
    )
    daily_seasonality = ArrayField(
        base_field=RealField(),
        size=24,
        null=True,
        blank=True,
        verbose_name=_('Daily Seasonality'),
        help_text=_('The predicted daily seasonality for the metric.')
    )

    class Meta:
        unique_together = ('metric', 'h3_index')
        verbose_name = _('MetricRegional Statistic')
        verbose_name_plural = _('Metric Regional Statistics')

    def __str__(self):
        return f"Regional Statistic for metric {self.metric.name} in H3 cell {self.h3_index}"
