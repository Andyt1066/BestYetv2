import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class MuscleGroup(TimeStampedModel):
    name = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return self.name


class Force(models.TextChoices):
    PUSH = "push", "Push"
    PULL = "pull", "Pull"
    STATIC = "static", "Static"


class Mechanic(models.TextChoices):
    COMPOUND = "compound", "Compound"
    ISOLATION = "isolation", "Isolation"


class LoadType(models.TextChoices):
    EXTERNAL = "external", "External load"
    BODYWEIGHT_PLUS = "bodyweight_plus", "Bodyweight plus added load"


class Metric(models.TextChoices):
    WEIGHT_REPS = "weight_reps", "Weight x reps"
    WEIGHT_TIME = "weight_time", "Weight x time"
    WEIGHT_DISTANCE_TIME = "weight_distance_time", "Weight x distance (x time)"


class Source(models.TextChoices):
    SEED = "seed", "Seed"
    CUSTOM = "custom", "Custom"


class MuscleRole(models.TextChoices):
    PRIMARY = "primary", "Primary"
    SECONDARY = "secondary", "Secondary"


class Exercise(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    force = models.CharField(max_length=6, choices=Force, blank=True, default="")
    mechanic = models.CharField(max_length=9, choices=Mechanic, blank=True, default="")
    equipment = models.CharField(max_length=60, blank=True, default="")
    load_type = models.CharField(max_length=15, choices=LoadType, default=LoadType.EXTERNAL)
    # Non-null only for barbell lifts; enables the plate calculator (invariant 11).
    bar_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    metric = models.CharField(max_length=20, choices=Metric, default=Metric.WEIGHT_REPS)
    unilateral = models.BooleanField(default=False)
    is_mobility = models.BooleanField(default=False)
    dots_eligible = models.BooleanField(default=False)
    instructions = models.TextField(blank=True, default="")
    image_paths = models.JSONField(null=True, blank=True)
    source = models.CharField(max_length=6, choices=Source, default=Source.CUSTOM)
    active = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    muscles = models.ManyToManyField(
        MuscleGroup, through="ExerciseMuscle", related_name="exercises"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(bar_weight_kg__isnull=True) | Q(load_type=LoadType.EXTERNAL),
                name="bar_weight_only_on_external",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.bar_weight_kg is not None and self.load_type != LoadType.EXTERNAL:
            raise ValidationError(
                {"bar_weight_kg": "Bar weight may be set only on external-load exercises."}
            )


class ExerciseMuscle(TimeStampedModel):
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    muscle_group = models.ForeignKey(MuscleGroup, on_delete=models.CASCADE)
    role = models.CharField(max_length=9, choices=MuscleRole)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exercise", "muscle_group"], name="one_role_per_exercise_muscle"
            ),
        ]

    def __str__(self):
        return f"{self.exercise} - {self.muscle_group} ({self.role})"
