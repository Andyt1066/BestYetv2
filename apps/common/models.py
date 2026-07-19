from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """created_at/updated_at on every table, maintained automatically (spec §5)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(TimeStampedModel):
    """User-generated rows soft-delete (invariant 3); hard delete only via admin.

    The default manager (`objects`) excludes soft-deleted rows everywhere,
    including related-manager traversals; `all_objects` sees everything.
    """

    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # noqa: DJ012 - order is compliant; rule misreads dual managers

    # NB: the base manager stays unfiltered so FK dereferences to soft-deleted
    # rows (e.g. history pointing at a deleted routine) still resolve.
    class Meta:
        abstract = True
        default_manager_name = "objects"

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)
