import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteManager, SoftDeleteModel, TimeStampedModel


class Visibility(models.TextChoices):
    PRIVATE = "private", "Private"
    SHARED = "shared", "Shared"
    CURATED = "curated", "Curated"


class ProgressionStyle(models.TextChoices):
    NONE = "none", "None"
    DOUBLE = "double", "Double progression"
    LINEAR = "linear", "Linear progression"


class Routine(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Null owner means a curated system routine (invariant 12).
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="routines",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    visibility = models.CharField(max_length=7, choices=Visibility, default=Visibility.PRIVATE)
    cloned_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="clones"
    )
    archived = models.BooleanField(default=False)

    class Meta(SoftDeleteModel.Meta):
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(visibility=Visibility.CURATED) & Q(owner__isnull=True))
                    | (~Q(visibility=Visibility.CURATED) & Q(owner__isnull=False))
                ),
                name="curated_iff_ownerless",
            ),
        ]

    def __str__(self):
        return self.name

    def clone_for(self, user):
        """Adopt a shared or curated routine by copying it; edits never propagate."""
        clone = Routine.objects.create(
            owner=user,
            name=self.name,
            description=self.description,
            visibility=Visibility.PRIVATE,
            cloned_from=self,
        )
        for entry in self.exercises.all():
            entry.pk = None
            entry._state.adding = True
            entry.routine = clone
            entry.save()
        return clone


class RoutineExerciseManager(SoftDeleteManager):
    def get_by_natural_key(self, routine_id, position):
        return self.get(routine_id=routine_id, position=position)


class RoutineExercise(SoftDeleteModel):
    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name="exercises")

    objects = RoutineExerciseManager()
    all_objects = models.Manager()
    exercise = models.ForeignKey("exercises.Exercise", on_delete=models.PROTECT)
    position = models.PositiveIntegerField()
    # Same non-null value = performed as a superset.
    superset_group = models.PositiveIntegerField(null=True, blank=True)
    target_sets = models.PositiveSmallIntegerField()
    target_reps_low = models.PositiveSmallIntegerField(null=True, blank=True)
    target_reps_high = models.PositiveSmallIntegerField(null=True, blank=True)
    target_rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    superset_rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    last_set_amrap = models.BooleanField(default=False)
    target_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    target_distance_m = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    progression_style = models.CharField(
        max_length=6, choices=ProgressionStyle, default=ProgressionStyle.DOUBLE
    )
    progression_increment_kg = models.DecimalField(max_digits=4, decimal_places=2, default=2.5)
    notes = models.TextField(blank=True, default="")

    class Meta(SoftDeleteModel.Meta):
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.routine} #{self.position}: {self.exercise}"

    def natural_key(self):
        return (str(self.routine_id), self.position)


class RoutineRotation(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rotation"
    )
    position = models.PositiveIntegerField()
    routine = models.ForeignKey(Routine, on_delete=models.CASCADE)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "routine"], name="routine_once_per_rotation"),
        ]

    def __str__(self):
        return f"{self.user} rotation #{self.position}: {self.routine}"

    def clean(self):
        if self.routine_id and self.routine.archived:
            raise ValidationError({"routine": "Archived routines cannot be added to the rotation."})
