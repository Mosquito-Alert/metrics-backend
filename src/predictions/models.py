import math
from datetime import datetime
from typing import List, Optional, TypedDict
from django.forms import BooleanField
import pandas as pd

from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import Case, F, Value, When
from django.utils.translation import gettext_lazy as _
from prophet import Prophet
from prophet.plot import seasonality_plot_df
from prophet.serialize import model_to_json as prophet_model_to_json
from rest_framework.fields import MaxValueValidator, MinValueValidator
from timescale.db.models.fields import TimescaleDateTimeField


from src.predictions.managers import PredictorManager
from src.predictions.tasks import refresh_prediction_task
from src.utils.postgresTypes import RealField


class PredictionResult(TypedDict):
    datetime: datetime
    yhat: float
    yhat_upper: float
    yhat_lower: float


class RawValueType(models.IntegerChoices):
    """
    Type of the raw value.
    """
    REANALYSIS = 1, _('Reanalysis')
    FORECAST = 2, _('Forecast')


class Boundary(models.Model):
    """
    Model to store the boundaries of a metric.
    """
    # CHECK: Maybe use string
    _h3_index = models.BigIntegerField(
        db_column='h3_index',
        null=False,
        blank=False,
        verbose_name=_('H3 Index'),
        help_text=_(
            'The H3 index of the raw value boundary, used for spatial queries. '
            'This is stored as a bigint to avoid issues with large indices, '
            'so it should be converted to/from hex strings.'
        ),
    )

    @property
    def h3_index(self) -> str:
        """Return H3 index as a hex string."""
        return f"{self._h3_index:x}"  # lowercase hex without 0x

    @h3_index.setter
    def h3_index(self, hex_value: str):
        """Store H3 index from a hex string."""
        self._h3_index = int(hex_value, 16)

    class Meta:
        verbose_name = _('Boundary')
        verbose_name_plural = _('Boundaries')


class Metric(models.Model):
    """
    Model to store the different metrics.
    For example, the Bites Index, the Suitability Index, etc.
    """
    name = models.CharField(max_length=255, unique=True, blank=False,
                            null=False,
                            verbose_name=_('Name'),
                            help_text=_('The name of the metric.'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Metric')
        verbose_name_plural = _('Metrics')

    def __str__(self):
        return self.name


class RawValue(models.Model):
    """
    Model to store the raw values of a metric.
    """
    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name='raw_values',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the raw value.')
    )
    time = TimescaleDateTimeField(
        null=False,
        blank=False,
        verbose_name=_('Time'),
        help_text=_('The time in which the raw value was recorded.'),
        # TODO: All the past data should be a single interval, and then, from today to the future, another.
        interval='7 days',  # TimescaleDB specific, sets the time interval for the hypertable
    )
    value = RealField(
        null=False,
        blank=False,
        verbose_name=_('Value'),
        help_text=_('The actual value of the raw data. The number is multiplied by 1000.'),
    )
    type = models.PositiveSmallIntegerField(
        choices=RawValueType.choices,
        null=False,
        blank=False,
        verbose_name=_('Type'),
        help_text=_('The type of the raw value.')
    )
    boundary = models.ForeignKey(
        Boundary,
        on_delete=models.CASCADE,
        related_name='raw_values',
        null=False,
        blank=False,
        verbose_name=_('Boundary'),
        help_text=_('The boundary associated to the raw value. This is used for spatial queries.'),
    )

    # CHECK: These methods should be in this model?
    def refresh_prediction(self, refresh_progress: bool = True) -> None:
        """
        (Async) Invokes the predictor and assign the Prediction fields.
        """
        refresh_prediction_task.delay(self.id, refresh_progress=refresh_progress)

    def save(self, *args, **kwargs):
        is_adding = self._state.adding  # A new object is being created

        if self.value is not None and math.isnan(self.value):
            self.value = None

        # Save the initial Metric with the prediction values and the predictor to None.
        super().save(*args, **kwargs)

        # Assign a predictor to the Metric and set the prediction values.
        if is_adding and self.metric.predictor_config.is_enabled:
            # If the Metric is being created, we need to assign a predictor and refresh the prediction
            self.refresh_prediction()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['metric', 'boundary', 'time'], name='unique_metric'
            )
        ]
        ordering = ['boundary', '-time']
        indexes = [
            models.Index(fields=['boundary', 'time']),
        ]
        verbose_name = _('Raw Value')
        verbose_name_plural = _('Raw Values')

    def __str__(self):
        return f"{self.metric.name} on {self.date} for {self.boundary.h3_index}: {self.value}"


class PredictedValue(models.Model):
    """
    Model to store the predicted values of a metric.
    """
    # Relation OneToOne with RawValue. This is the Primary Key.
    raw_value = models.OneToOneField(
        RawValue,
        on_delete=models.CASCADE,
        primary_key=True,
        unique=True,
        related_name='predicted_value',
        verbose_name=_('Raw Value'),
        help_text=_('The raw value associated to the predicted value.')
    )
    predictor = models.ForeignKey(
        'Predictor',
        on_delete=models.CASCADE,
        null=True,  # CHECK:
        blank=True,  # CHECK:
        related_name='predicted_values',
        verbose_name=_('Predictor'),
        help_text=_('The predictor associated to the predicted value.')
    )
    value = RealField(
        null=False,
        blank=False,
        verbose_name=_('Value'),
        help_text=_('The predicted value.')
    )
    lower_confidence_band = RealField(
        null=False,
        blank=False,
        verbose_name=_('Lower Confidence Band'),
        help_text=_('The lower confidence band of the predicted value.')
    )
    upper_confidence_band = RealField(
        null=False,
        blank=False,
        verbose_name=_('Upper Confidence Band'),
        help_text=_('The upper confidence band of the predicted value.')
    )
    anomaly_degree = models.GeneratedField(
        expression=Case(
            When(predicted_value__isnull=True, then=Value(None)),
            default=Case(
                # Handle value == 0 case explicitly
                When(
                    value=0,
                    then=Case(
                        When(upper_confidence_band__lt=0, then=Value(1.0)),
                        When(lower_confidence_band__gt=0, then=Value(-1.0)),
                        default=Value(0.0),
                        output_field=RealField()
                    )
                ),
                # Normal anomaly detection cases
                When(value__gt=F('upper_confidence_band'),
                     then=(F('raw_value__value') - F('upper_confidence_band')) / F('raw_value__value')),
                When(value__lt=F('lower_confidence_band'),
                     then=(F('raw_value__value') - F('lower_confidence_band')) / F('raw_value__value')),
                default=Value(0.0),
                output_field=RealField(),
            ),
        ),
        output_field=RealField(),
        # If db_persist is set to false, then the field will not be persisted in the database
        # and the computed value will be calculated on the READ queries, which is not optimal.
        db_persist=True,
        blank=True,
        null=True,
        verbose_name=_('Anomaly degree'),
        help_text=_('The degree of the anomaly, a range of values that starts on -1 (a lower anomaly of the \
            highest degree) and ends on +1 (a upper anomaly of the highest degree). The 0 value means that \
            these is no anomaly. This value will be estimated at creation.')
    )

    def __str__(self):
        return f"Predicted Value for {self.raw_value.metric.name} on {self.raw_value.time} for " \
            f"{self.raw_value.boundary.h3_index}: {self.value}"

    class Meta:
        ordering = ['raw_value']
        verbose_name = _('Predicted Value')
        verbose_name_plural = _('Predicted Values')


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
    yearly_seasonality = BooleanField(
        default=True,
        blank=False,
        null=False,
        verbose_name=_('Yearly Seasonality'),
        help_text=_('Whether the predictor should consider yearly seasonality.')
    )
    weekly_seasonality = BooleanField(
        default=False,
        blank=False,
        null=False,
        verbose_name=_('Weekly Seasonality'),
        help_text=_('Whether the predictor should consider weekly seasonality.')
    )
    daily_seasonality = BooleanField(
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
    is_enabled = models.BooleanField(
        default=True,
        blank=False,
        null=False,
        verbose_name=_('Is Enabled'),
        help_text=_(
            'Whether the predictor is enabled or not.'
            'If disabled, the predictor will not be used for predictions.'
        ),
    )

    def __str__(self):
        return f"Predictor Config for {self.metric.name}"

    class Meta:
        verbose_name = _('Predictor Config')
        verbose_name_plural = _('Predictor Configs')


class Predictor(models.Model):
    """
    Model to store the predictor model and the prediction results.
    """
    metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name='predictors',
        verbose_name=_('Metric'),
        help_text=_('The metric associated to the predictor.')
    )
    boundary = models.ForeignKey(
        Boundary,
        on_delete=models.CASCADE,
        related_name='predictors',
        null=False,  # CHECK:
        blank=False,  # CHECK:
        verbose_name=_('Boundary'),
        help_text=_('The boundary associated to the predictor. This is used for spatial queries.'),
    )
    last_training_date = models.DateTimeField(
        null=False,
        blank=False,
        verbose_name=_('Last Training Date'),
        help_text=_('The last value date used to train the model.')
    )
    weights = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Weights'),
        help_text=_('The predictor model itself, serialized as JSON.')
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
    trend = ArrayField(
        base_field=RealField(),
        null=True,
        blank=True,
        verbose_name=_('Trend'),
        help_text=_('The predicted trend for the metric.')
    )

    objects = PredictorManager()

    @property
    def is_trained(self) -> bool:
        """
        Whether the predictor is trained or not.
        """
        return self.weights is not None

    @staticmethod
    def _predict(prophet, df) -> pd.DataFrame:
        df_new = df.copy()
        df_new['cap'] = 1
        df_new['floor'] = 0

        return prophet.predict(df_new)

    def predict(self, dates: List[datetime]) -> Optional[List[PredictionResult]]:
        """
        Predicts the values for the specified data.
        """
        from prophet.serialize import model_from_json
        if not self.is_trained:
            self.train()
        if not self.is_trained:
            # This second comprobation is needed for the first iterations (first 30 days)
            return

        prophet = model_from_json(self.weights)

        # If dates is not an array, convert to arary.
        if not isinstance(dates, list):
            dates = [dates, ]

        df = pd.DataFrame(dates, columns=['ds',])
        forecast: PredictionResult = [
            PredictionResult(**res)
            for res in self._predict(prophet=prophet, df=df)[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].rename(
                columns={'ds': 'datetime'}).to_dict(orient='records')
        ]
        return forecast

    def train(self, force: bool = False) -> None:
        """
        Trains the predictor model with past data.
        """
        # We need to set the logger to avoid the warning of the prophet library.
        import logging
        logger = logging.getLogger('cmdstanpy')
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        logger.setLevel(logging.CRITICAL)

        import warnings
        warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

        if self.is_trained and not force:
            return

        # NOTE: Do not delete the order by date, as it is needed for the Prophet model.
        metric_value_qs = self.metric.raw_values.filter(
            time__lt=self.last_training_date, boundary=self.boundary).order_by('time')

        df = pd.DataFrame.from_records(
            ({'ds': obj.date, 'y': obj.value} for obj in metric_value_qs.iterator())  # Generator
        )
        # TODO: Apply Savitzky-Golay filter with safeguards. Maybe, create a new field in Metric (smoothed_value)

        if df.empty or df['y'].isna().all() or df['y'].eq(0).all():
            return

        first_non_zero = df[df["y"] != 0].iloc[0]
        # See: https://facebook.github.io/prophet/docs/outliers.html
        df.loc[df['ds'] < first_non_zero['ds'], "y"] = None

        if df["y"].count() < self.MIN_DAYS_FOR_TRAINING:
            # If there are not enough quality data to train the model, do not train it.
            return

        model = Prophet(
            growth=self.metric.predictor_config.growth,
            yearly_seasonality=self.metric.predictor_config.yearly_seasonality,
            weekly_seasonality=self.metric.predictor_config.weekly_seasonality,
            daily_seasonality=self.metric.predictor_config.daily_seasonality,
        )
        # Logistic growth and boundaries between 0 and 1 are specifict to the bite risk model, which value is a
        # probability. If ever needs to use other kind of metric set the boundaries on the MetricType model.
        df.loc[:, 'cap'] = 1
        df.loc[:, 'floor'] = 0
        model.fit(df)

        # Trend
        future = model.make_future_dataframe(periods=0)
        future['cap'] = 1  # Ensure the future data has the cap
        future['floor'] = 0  # Ensure the future data has the floor
        forecast = model.predict(future)

        # Seasonality
        if self.metric.predictor_config.yearly_seasonality:
            # Generate the seasonality plot dataframe for yearly seasonality
            df_y = seasonality_plot_df(m=model, ds=pd.date_range(start='2017-01-01', periods=365, freq='D'))
            seas_df = model.predict_seasonal_components(df_y)
            self.yearly_seasonality = seas_df.reset_index(inplace=False)['yearly'].to_list()
        if self.metric.predictor_config.weekly_seasonality:
            # Generate the seasonality plot dataframe for weekly seasonality
            df_w = seasonality_plot_df(m=model, ds=pd.date_range(start='2017-01-01', periods=7, freq='D'))
            seas_df = model.predict_seasonal_components(df_w)
            self.weekly_seasonality = seas_df.reset_index(inplace=False)['weekly'].to_list()
        if self.metric.predictor_config.daily_seasonality:
            # Generate the seasonality plot dataframe for daily seasonality
            df_d = seasonality_plot_df(m=model, ds=pd.date_range(start='2017-01-01', periods=24, freq='H'))
            seas_df = model.predict_seasonal_components(df_d)
            self.daily_seasonality = seas_df.reset_index(inplace=False)['daily'].to_list()

        # Save
        self.weights = prophet_model_to_json(model)
        self.trend = forecast['trend'].to_list()
        self.save()

    def __str__(self):
        return f"Predictor for {self.metric.name} on {self.boundary.h3_index} trained at {self.last_training_date}"

    class Meta:
        ordering = ['metric', 'boundary', '-last_training_date']
        indexes = [
            models.Index(fields=['metric', 'boundary', 'last_training_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['metric', 'boundary', 'last_training_date'], name='unique_predictor'
            )
        ]
        verbose_name = _('Predictor')
        verbose_name_plural = _('Predictors')


class MetricPredictionProgress(models.Model):
    """
    Model to store the data prediction progress information.
    Every time the metric values are updated, a prediction will be executed.
    """
    time = models.DateTimeField(
        unique=True,
        null=False,
        blank=False,
        verbose_name=_('Time'),
        help_text=_('The date and time of the execution.')
    )
    # Percentage of values successfully predicted and saved.
    success_percentage = models.FloatField(
        null=False,
        blank=False,
        default=0,
        verbose_name=_('Success percentage'),
        help_text=_('The percentage of success of the execution.'),
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )

    @classmethod
    def refresh(cls, time: datetime):
        with transaction.atomic():
            total_raw_values = RawValue.objects.filter(time__date=time.date()).count()
            total_predicted = PredictedValue.objects.filter(
                raw_value__time__date=time,
                value__isnull=False
            ).count()

            success_percentage = 0
            if total_raw_values > 0:
                success_percentage = total_predicted / total_raw_values

            cls.objects.update_or_create(
                time=time,
                defaults={'success_percentage': success_percentage}
            )

    def __str__(self):
        return f"Metric Execution of the day {self.date} with result: {self.success_percentage}"

    class Meta:
        ordering = ['date']
        indexes = [
            models.Index(fields=['-date'])
        ]
        verbose_name = "Metric Prediction Progress"
        verbose_name_plural = "Metric Prediction Progressses"
