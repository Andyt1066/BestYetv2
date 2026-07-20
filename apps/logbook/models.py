import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.models import SoftDeleteModel
from apps.exercises.models import LoadType, Metric


class Side(models.TextChoices):
    LEFT = "left", "Left"
    RIGHT = "right", "Right"


class SetType(models.TextChoices):
    NORMAL = "normal", "Normal"
    WARMUP = "warmup", "Warm-up"
    DROPSET = "dropset", "Drop set"


class Activity(models.TextChoices):
    TREADMILL = "treadmill", "Treadmill"
    BIKE = "bike", "Bike"
    ROWER = "rower", "Rower"
    STAIRMASTER = "stairmaster", "Stairmaster"
    OUTDOOR_RUN = "outdoor_run", "Outdoor run"
    WALK = "walk", "Walk"
    SWIM = "swim", "Swim"
    OTHER = "other", "Other"


class WorkoutSession(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions"
    )
    routine = models.ForeignKey(
        "routines.Routine", on_delete=models.SET_NULL, null=True, blank=True
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    # Set on any mutation after finish; drives the visible "edited" marker.
    edited_at = models.DateTimeField(null=True, blank=True)
    session_rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta(SoftDeleteModel.Meta):
        indexes = [models.Index(fields=["user", "started_at"])]

    def __str__(self):
        return f"{self.user} session {self.started_at:%Y-%m-%d}"

    def clean(self):
        if self.started_at and self.started_at > timezone.now():
            raise ValidationError({"started_at": "Session start cannot be in the future."})
        if self.ended_at and self.started_at and self.ended_at < self.started_at:
            raise ValidationError({"ended_at": "Session end cannot precede its start."})

    @property
    def is_finished(self):
        return self.ended_at is not None

    def mark_edited(self):
        self.edited_at = timezone.now()
        self.save(update_fields=["edited_at", "updated_at"])


class SetLog(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name="sets")
    exercise = models.ForeignKey("exercises.Exercise", on_delete=models.PROTECT)
    position = models.PositiveIntegerField()
    set_type = models.CharField(max_length=7, choices=SetType, default=SetType.NORMAL)
    superset_group = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2)
    reps = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    distance_m = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    side = models.CharField(max_length=5, choices=Side, blank=True, default="")
    rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    completed_at = models.DateTimeField(default=timezone.now)
    # Denormalised copy of the exercise's load_type so the negative-weight check
    # constraint can be enforced without a join; resynced on every save.
    _load_type = models.CharField(max_length=15, editable=False, default=LoadType.EXTERNAL)

    class Meta(SoftDeleteModel.Meta):
        ordering = ["position", "completed_at"]
        indexes = [models.Index(fields=["exercise", "session"])]
        constraints = [
            # weight_kg may be negative only for bodyweight_plus exercises (inv 7).
            # A negative weight requires that load_type; the ORM writes the FK,
            # so this guards the stored value against a non-bodyweight_plus row.
            models.CheckConstraint(
                condition=Q(weight_kg__gte=0) | Q(_load_type=LoadType.BODYWEIGHT_PLUS),
                name="negative_weight_only_bodyweight_plus",
            ),
        ]

    def __str__(self):
        return f"{self.exercise} {self.weight_kg}kg x {self.reps}"

    def save(self, *args, **kwargs):
        if self.exercise_id:
            self._load_type = self.exercise.load_type
        super().save(*args, **kwargs)

    def clean(self):
        if not self.exercise_id:
            return
        # Keep the denormalised copy current so constraint validation in
        # full_clean() sees the real load_type, not the stale default.
        self._load_type = self.exercise.load_type
        metric = self.exercise.metric
        if metric == Metric.WEIGHT_REPS and self.reps is None:
            raise ValidationError({"reps": "Reps are required for this exercise."})
        if metric == Metric.WEIGHT_TIME and self.duration_seconds is None:
            raise ValidationError({"duration_seconds": "Duration is required for this exercise."})
        if metric == Metric.WEIGHT_DISTANCE_TIME and self.distance_m is None:
            raise ValidationError({"distance_m": "Distance is required for this exercise."})
        if self.exercise.unilateral and not self.side:
            raise ValidationError({"side": "Side is required for a unilateral exercise."})
        if not self.exercise.unilateral and self.side:
            raise ValidationError({"side": "Side applies only to unilateral exercises."})
        if self.weight_kg is not None and self.weight_kg < 0:
            if self.exercise.load_type != LoadType.BODYWEIGHT_PLUS:
                raise ValidationError(
                    {"weight_kg": "Negative load is allowed only for bodyweight-plus exercises."}
                )


class CardioLog(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cardio"
    )
    session = models.ForeignKey(
        WorkoutSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="cardio"
    )
    activity = models.CharField(max_length=12, choices=Activity)
    duration_seconds = models.PositiveIntegerField()
    distance_m = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    performed_at = models.DateTimeField()
    notes = models.TextField(blank=True, default="")

    class Meta(SoftDeleteModel.Meta):
        indexes = [models.Index(fields=["user", "performed_at"])]

    def __str__(self):
        return f"{self.user} {self.get_activity_display()} {self.performed_at:%Y-%m-%d}"
