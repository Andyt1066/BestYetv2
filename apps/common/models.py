from django.db import models


class TimeStampedModel(models.Model):
    """created_at/updated_at on every table, maintained automatically (spec §5)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
