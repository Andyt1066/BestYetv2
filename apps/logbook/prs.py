"""Read-time PR and e1RM computation. No PR state is ever stored (spec §5.5).

Conventions (stated, not universal): Epley e1RM = weight x (1 + reps/30);
warm-up sets excluded; sets over 12 reps excluded from e1RM.
"""

from decimal import ROUND_HALF_UP, Decimal

from apps.exercises.models import Metric
from apps.logbook.models import SetLog, SetType

E1RM_REP_CAP = 12
_CENTS = Decimal("0.01")


def epley_e1rm(weight_kg, reps):
    """Estimated 1RM, or None when reps fall outside the usable range."""
    if reps is None or reps < 1 or reps > E1RM_REP_CAP:
        return None
    estimate = Decimal(weight_kg) * (1 + Decimal(reps) / Decimal(30))
    return estimate.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _prior_sets(entry):
    """This user's completed working sets of the same exercise, before this one."""
    return (
        SetLog.objects.filter(
            session__user_id=entry.session.user_id,
            exercise_id=entry.exercise_id,
            set_type=SetType.NORMAL,
        )
        .exclude(pk=entry.pk)
        .exclude(session__deleted_at__isnull=False)
    )


def pr_check(entry):
    """Return which PR types `entry` sets against the user's prior history.

    Keys: max_weight, best_e1rm, max_reps_at_weight (weight_reps only), and
    `any`. Warm-up sets never count as PRs.
    """
    result = {"max_weight": False, "best_e1rm": False, "max_reps_at_weight": False, "any": False}
    if entry.set_type == SetType.WARMUP:
        return result

    metric = entry.exercise.metric
    prior = list(_prior_sets(entry).values("weight_kg", "reps"))

    if metric == Metric.WEIGHT_REPS:
        if entry.weight_kg is not None:
            heavier = [p["weight_kg"] for p in prior if p["weight_kg"] is not None]
            result["max_weight"] = not heavier or entry.weight_kg > max(heavier)
            same_weight_reps = [
                p["reps"]
                for p in prior
                if p["weight_kg"] == entry.weight_kg and p["reps"] is not None
            ]
            if entry.reps is not None:
                result["max_reps_at_weight"] = not same_weight_reps or entry.reps > max(
                    same_weight_reps
                )

        this_e1rm = epley_e1rm(entry.weight_kg, entry.reps)
        if this_e1rm is not None:
            prior_e1rms = [
                e for p in prior if (e := epley_e1rm(p["weight_kg"], p["reps"])) is not None
            ]
            result["best_e1rm"] = not prior_e1rms or this_e1rm > max(prior_e1rms)

    result["any"] = result["max_weight"] or result["best_e1rm"] or result["max_reps_at_weight"]
    return result
