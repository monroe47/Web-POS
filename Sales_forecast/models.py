from django.db import models
from Inventory.models import Item
from django.utils import timezone

class ForecastRun(models.Model):
    """
    Metadata for each training run. Stores parameters, metrics and artifact path.
    """
    model_name = models.CharField(max_length=255, default='xgb.XGBRegressor')
    train_start = models.DateField(null=True, blank=True)
    train_end = models.DateField(null=True, blank=True)
    horizon = models.PositiveIntegerField(default=7)
    params = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    artifact_path = models.CharField(max_length=1024, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"ForecastRun {self.id} ({self.model_name}) @ {self.created_at.isoformat()}"


class ForecastResult(models.Model):
    """
    Stores forecasted values (and optional actuals) per date and per product.
    """
    run = models.ForeignKey(ForecastRun, related_name='results', on_delete=models.CASCADE)
    date = models.DateField()
    product = models.ForeignKey('Inventory.Item', on_delete=models.CASCADE, null=True, blank=True)
    actual = models.FloatField(null=True, blank=True)
    predicted = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']
        indexes = [
            models.Index(fields=['date']),
            # models.Index(fields=['product_id']) # Removed as product_id is replaced by product ForeignKey,
        ]

    def __str__(self):
        pid = self.product.name if self.product else "TOTAL"
        return f"{self.date} - {pid} -> {self.predicted}"