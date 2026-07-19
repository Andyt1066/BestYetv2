from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


def default_plate_inventory():
    return [25, 20, 15, 10, 5, 2.5, 1.25]


class Units(models.TextChoices):
    KG = "kg", "kg"
    LB = "lb", "lb"


class BodyweightUnit(models.TextChoices):
    KG = "kg", "kg"
    ST_LB = "st_lb", "st & lb"
    LB = "lb", "lb"


class Sex(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"


class Profile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    display_name = models.CharField(max_length=80)
    preferred_units = models.CharField(max_length=2, choices=Units, default=Units.KG)
    bodyweight_unit = models.CharField(
        max_length=5, choices=BodyweightUnit, default=BodyweightUnit.KG
    )
    bodyweight_goal_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    share_history = models.BooleanField(default=False)
    plate_inventory = models.JSONField(default=default_plate_inventory)
    deload_after_failures = models.PositiveSmallIntegerField(default=3)
    deload_percent = models.DecimalField(max_digits=4, decimal_places=1, default=10)
    deload_week_percent = models.DecimalField(max_digits=4, decimal_places=1, default=50)
    # Used solely for DOTS coefficient selection; unset excludes from DOTS boards.
    sex = models.CharField(max_length=6, choices=Sex, blank=True, default="")
    pseudonym = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return f"Profile({self.user.username})"

    def regenerate_pseudonym(self):
        from apps.accounts import pseudonyms

        self.pseudonym = pseudonyms.generate_unique(
            lambda candidate: Profile.objects.filter(pseudonym=candidate).exists()
        )
        self.save(update_fields=["pseudonym", "updated_at"])
