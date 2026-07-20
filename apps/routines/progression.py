"""Progression suggestion engine (spec §5.3).

Suggestions are display-only (invariant 6) and computed from history at read
time — never stored (invariant 10). Only sessions where the exercise was
actually performed count, and sessions falling within any DeloadPeriod are
excluded from progression and stall evaluation entirely (invariant 19).

Conventions (stated, tunable): double = progress when every working set hit
`target_reps_high` (and RPE within `target_rpe` when both set); linear =
progress when every working set hit `target_reps_low`. Warm-up and drop sets
are excluded. AMRAP sets are evaluated against `target_reps_high` like any
other set. The engine applies to `weight_reps` exercises only; everything
else is prefill.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from apps.exercises.models import Metric
from apps.logbook.models import SetLog, SetType
from apps.routines.models import DeloadPeriod, ProgressionStyle


@dataclass
class Suggestion:
    kind: str  # progress | hold | deload | deload_week | prefill | fresh
    weight_kg: Decimal | None = None
    reps_low: int | None = None
    reps_high: int | None = None
    stall_count: int = 0
    note: str = ""


def _round_to_increment(weight, increment):
    increment = Decimal(increment)
    steps = (Decimal(weight) / increment).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return steps * increment


def _qualifying_sessions(user, exercise):
    """Completed sessions with working (normal) sets of this exercise, most
    recent first, excluding any that fall within a deload window."""
    periods = list(DeloadPeriod.objects.filter(user=user).values_list("start_date", "end_date"))

    def in_deload(on_date):
        return any(start <= on_date <= end for start, end in periods)

    rows = (
        SetLog.objects.filter(session__user=user, exercise=exercise, set_type=SetType.NORMAL)
        .exclude(session__ended_at__isnull=True)
        .select_related("session")
        .order_by("-session__started_at")
    )
    grouped = {}
    for row in rows:
        session = row.session
        if in_deload(session.started_at.date()):
            continue
        grouped.setdefault(session.id, {"session": session, "sets": []})["sets"].append(row)
    # Preserve most-recent-first ordering by started_at.
    return sorted(grouped.values(), key=lambda g: g["session"].started_at, reverse=True)


def _condition_met(sets, style, reps_low, reps_high, target_rpe):
    if style == ProgressionStyle.LINEAR:
        target = reps_low
        return target is not None and all(s.reps is not None and s.reps >= target for s in sets)
    # double: every working set reaches the top of the range
    target = reps_high
    if target is None:
        return False
    if not all(s.reps is not None and s.reps >= target for s in sets):
        return False
    if target_rpe is not None:
        # Only gate on sets that recorded an RPE.
        gate = Decimal(target_rpe)
        return all(s.rpe is None or s.rpe <= gate for s in sets)
    return True


def suggest(routine_exercise, user, today):
    rx = routine_exercise
    exercise = rx.exercise
    reps_low, reps_high = rx.target_reps_low, rx.target_reps_high

    history = _qualifying_sessions(user, exercise)
    if not history:
        return Suggestion(kind="fresh", reps_low=reps_low, reps_high=reps_high)

    recent = history[0]
    last_weight = max(s.weight_kg for s in recent["sets"])

    # Prefill-only: non-rep metrics, or the "none" style.
    if exercise.metric != Metric.WEIGHT_REPS or rx.progression_style == ProgressionStyle.NONE:
        return Suggestion(
            kind="prefill", weight_kg=last_weight, reps_low=reps_low, reps_high=reps_high
        )

    # Deload week mode scales every suggestion off the last working weight.
    if DeloadPeriod.objects.active_for(user, today=today) is not None:
        percent = Decimal(user.profile.deload_week_percent)
        weight = _nearest_loadable(last_weight * percent / Decimal(100), exercise, user)
        return Suggestion(
            kind="deload_week", weight_kg=weight, reps_low=reps_low, reps_high=reps_high
        )

    increment = rx.progression_increment_kg
    met = _condition_met(recent["sets"], rx.progression_style, reps_low, reps_high, rx.target_rpe)
    if met:
        return Suggestion(
            kind="progress",
            weight_kg=last_weight + increment,
            reps_low=reps_low,
            reps_high=reps_high,
        )

    # Not met: count consecutive recent failures at this weight for a stall deload.
    streak = 0
    for group in history:
        weight = max(s.weight_kg for s in group["sets"])
        if weight != last_weight:
            break
        if _condition_met(group["sets"], rx.progression_style, reps_low, reps_high, rx.target_rpe):
            break
        streak += 1

    if streak >= user.profile.deload_after_failures:
        percent = Decimal(user.profile.deload_percent)
        weight = _round_to_increment(
            last_weight * (Decimal(100) - percent) / Decimal(100), increment
        )
        return Suggestion(
            kind="deload",
            weight_kg=weight,
            reps_low=reps_low,
            reps_high=reps_high,
            stall_count=streak,
        )

    return Suggestion(kind="hold", weight_kg=last_weight, reps_low=reps_low, reps_high=reps_high)


def _nearest_loadable(weight, exercise, user):
    from apps.logbook.plates import nearest_loadable

    inventory = user.profile.plate_inventory
    return nearest_loadable(weight, exercise.bar_weight_kg, inventory)
