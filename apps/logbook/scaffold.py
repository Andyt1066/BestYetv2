"""Build the display-only planned-set scaffold for the active workout screen.

The scaffold is never persisted (invariant 9): it is a per-set plan rendered
in the UI, carrying targets, last-session ghost values, and the progression
suggestion. A SetLog row appears only when a set is ticked.
"""

from dataclasses import dataclass, field

from apps.logbook.models import SetLog, SetType


@dataclass
class ScaffoldSet:
    index: int
    set_type: str = SetType.NORMAL
    is_amrap: bool = False
    ghost_weight: str = ""
    ghost_reps: str = ""
    logged: object = None  # a SetLog when this set has been completed


@dataclass
class ScaffoldBlock:
    exercise: object
    target_sets: int
    target_reps_low: object = None
    target_reps_high: object = None
    target_rpe: object = None
    rest_seconds: object = None
    superset_group: object = None
    superset_rest_seconds: object = None
    last_set_amrap: bool = False
    planned_sets: list = field(default_factory=list)


def _last_performance(user, exercise):
    """Most recent completed working sets of this exercise, for ghost text."""
    last_set = (
        SetLog.objects.filter(session__user=user, exercise=exercise, set_type=SetType.NORMAL)
        .exclude(session__ended_at__isnull=True)
        .order_by("-completed_at")
        .first()
    )
    if last_set is None:
        return "", ""
    return (str(last_set.weight_kg), str(last_set.reps or ""))


def build_scaffold(user, routine, session=None):
    """A list of ScaffoldBlocks from the routine, or [] for a freeform session.

    When `session` is given, any sets already logged for a routine exercise are
    merged into that block's rows as completed sets, so resuming a session shows
    real logged values rather than blank scaffold (and the plan still fills out
    to `target_sets`). Completed rows never overwrite the stored SetLog.
    """
    if routine is None:
        return []
    logged_by_exercise = {}
    if session is not None:
        for entry in session.sets.select_related("exercise").order_by("position", "completed_at"):
            logged_by_exercise.setdefault(entry.exercise_id, []).append(entry)

    blocks = []
    for entry in routine.exercises.select_related("exercise"):
        ghost_weight, ghost_reps = _last_performance(user, entry.exercise)
        logged = logged_by_exercise.get(entry.exercise_id, [])
        planned = []
        row_count = max(entry.target_sets, len(logged))
        for i in range(row_count):
            is_amrap = entry.last_set_amrap and i == entry.target_sets - 1
            done = logged[i] if i < len(logged) else None
            planned.append(
                ScaffoldSet(
                    index=i,
                    set_type=done.set_type if done else SetType.NORMAL,
                    is_amrap=is_amrap,
                    ghost_weight=ghost_weight,
                    ghost_reps=ghost_reps,
                    logged=done,
                )
            )
        blocks.append(
            ScaffoldBlock(
                exercise=entry.exercise,
                target_sets=entry.target_sets,
                target_reps_low=entry.target_reps_low,
                target_reps_high=entry.target_reps_high,
                target_rpe=entry.target_rpe,
                rest_seconds=entry.rest_seconds,
                superset_group=entry.superset_group,
                superset_rest_seconds=entry.superset_rest_seconds,
                last_set_amrap=entry.last_set_amrap,
                planned_sets=planned,
            )
        )
    return blocks
