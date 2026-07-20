"""Progression engine (spec §5.3). Suggestions are display-only and computed
from history at read time — nothing here writes a target or a log.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.exercises.models import Exercise
from apps.logbook.models import SetLog, WorkoutSession
from apps.routines.deload import start_deload_week
from apps.routines.models import Routine, RoutineExercise
from apps.routines.progression import suggest

User = get_user_model()

pytestmark = pytest.mark.django_db


def D(x):
    return Decimal(str(x))


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


@pytest.fixture
def squat():
    return Exercise.objects.create(
        name="Barbell Squat", slug="barbell-squat", active=True, bar_weight_kg=20
    )


@pytest.fixture
def routine(andy, squat):
    return Routine.objects.create(owner=andy, name="Leg day")


def make_rx(routine, exercise, style="double", low=5, high=8, rpe=None, increment="2.5"):
    return RoutineExercise.objects.create(
        routine=routine,
        exercise=exercise,
        position=0,
        target_sets=3,
        target_reps_low=low,
        target_reps_high=high,
        target_rpe=rpe,
        progression_style=style,
        progression_increment_kg=Decimal(increment),
    )


def log_session(user, exercise, on_date, sets, routine=None):
    """sets: list of (weight, reps, set_type, rpe)."""
    started = timezone.make_aware(
        timezone.datetime(on_date.year, on_date.month, on_date.day, 12, 0)
    )
    session = WorkoutSession.objects.create(
        user=user, routine=routine, started_at=started, ended_at=started
    )
    for i, (weight, reps, set_type, rpe) in enumerate(sets):
        SetLog.objects.create(
            session=session,
            exercise=exercise,
            position=i,
            weight_kg=D(weight),
            reps=reps,
            set_type=set_type,
            rpe=D(rpe) if rpe is not None else None,
            completed_at=started,
        )
    return session


NORMAL = "normal"
WARMUP = "warmup"
DROPSET = "dropset"

TODAY = date(2026, 7, 20)


# --- double progression ------------------------------------------------------


def test_double_progresses_when_all_sets_hit_high(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8, increment="2.5")
    log_session(andy, squat, TODAY - timedelta(days=3), [(100, 8, NORMAL, None)] * 3)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "progress"
    assert s.weight_kg == D("102.5")
    assert s.reps_low == 5  # aim back at the bottom of the range


def test_double_holds_when_a_set_misses(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8)
    log_session(
        andy,
        squat,
        TODAY - timedelta(days=3),
        [(100, 8, NORMAL, None), (100, 6, NORMAL, None), (100, 8, NORMAL, None)],
    )
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "hold"
    assert s.weight_kg == D("100")


def test_double_rpe_gate_blocks_progression(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8, rpe="8.0")
    # Hit the reps but too hard (RPE above the gate): hold, don't progress.
    log_session(andy, squat, TODAY - timedelta(days=3), [(100, 8, NORMAL, "9.5")] * 3)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "hold"


def test_double_rpe_gate_allows_progression_when_within(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8, rpe="8.0")
    log_session(andy, squat, TODAY - timedelta(days=3), [(100, 8, NORMAL, "7.5")] * 3)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "progress"


def test_warmup_and_dropset_sets_excluded_from_evaluation(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8)
    # A low-rep warm-up and a low-rep drop set must not block progression.
    log_session(
        andy,
        squat,
        TODAY - timedelta(days=3),
        [
            (40, 5, WARMUP, None),
            (100, 8, NORMAL, None),
            (100, 8, NORMAL, None),
            (100, 8, NORMAL, None),
            (60, 15, DROPSET, None),
        ],
    )
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "progress"


def test_amrap_last_set_counts_toward_condition(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8)
    rx.last_set_amrap = True
    rx.save()
    # AMRAP final set beat target_reps_high; all sets hit -> progress.
    log_session(
        andy,
        squat,
        TODAY - timedelta(days=3),
        [(100, 8, NORMAL, None), (100, 8, NORMAL, None), (100, 12, NORMAL, None)],
    )
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "progress"


# --- linear progression ------------------------------------------------------


def test_linear_progresses_when_target_met(andy, squat, routine):
    rx = make_rx(routine, squat, style="linear", low=5, high=None, increment="5")
    log_session(andy, squat, TODAY - timedelta(days=3), [(100, 5, NORMAL, None)] * 3)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "progress"
    assert s.weight_kg == D("105")


def test_linear_holds_when_target_missed(andy, squat, routine):
    rx = make_rx(routine, squat, style="linear", low=5, high=None, increment="5")
    log_session(
        andy,
        squat,
        TODAY - timedelta(days=3),
        [(100, 5, NORMAL, None), (100, 4, NORMAL, None), (100, 5, NORMAL, None)],
    )
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "hold"


# --- stall deload ------------------------------------------------------------


def test_stall_deload_after_threshold_failures(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8, increment="2.5")
    # deload_after_failures defaults to 3. Three straight misses at 100 kg.
    for d in (12, 9, 6):
        log_session(andy, squat, TODAY - timedelta(days=d), [(100, 6, NORMAL, None)] * 3)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "deload"
    assert s.stall_count == 3
    # 100 * (1 - 10/100) = 90, rounded to the 2.5 increment.
    assert s.weight_kg == D("90")


def test_two_failures_below_threshold_still_holds(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8)
    for d in (9, 6):
        log_session(andy, squat, TODAY - timedelta(days=d), [(100, 6, NORMAL, None)] * 3)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "hold"


def test_failures_at_different_weight_do_not_accumulate(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8)
    # Two misses at 100, but the most recent is at a new weight 95: streak resets.
    log_session(andy, squat, TODAY - timedelta(days=12), [(100, 6, NORMAL, None)] * 3)
    log_session(andy, squat, TODAY - timedelta(days=9), [(100, 6, NORMAL, None)] * 3)
    log_session(andy, squat, TODAY - timedelta(days=6), [(95, 6, NORMAL, None)] * 3)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "hold"
    assert s.weight_kg == D("95")


def test_deload_week_session_never_counts_as_a_failure(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8)
    # Two real misses, plus a miss during a deload week that must NOT count.
    log_session(andy, squat, date(2026, 7, 8), [(100, 6, NORMAL, None)] * 3)
    log_session(andy, squat, date(2026, 7, 11), [(100, 6, NORMAL, None)] * 3)
    # This "miss" falls inside a deload window and is excluded (invariant 19).
    from apps.routines.models import DeloadPeriod

    DeloadPeriod.objects.create(user=andy, start_date=date(2026, 7, 13), end_date=date(2026, 7, 20))
    log_session(andy, squat, date(2026, 7, 14), [(100, 4, NORMAL, None)] * 3)
    s = suggest(rx, andy, today=date(2026, 7, 21))
    # Only two counted failures -> below the threshold of 3 -> hold, not deload.
    assert s.kind == "hold"


# --- deload week mode --------------------------------------------------------


def test_deload_week_mode_scales_suggestion(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8)
    log_session(andy, squat, date(2026, 7, 1), [(100, 8, NORMAL, None)] * 3)
    start_deload_week(andy, today=TODAY)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "deload_week"
    # 100 * 50/100 = 50, rounded to a loadable weight (20 kg bar + plates).
    assert s.weight_kg == D("50")


# --- prefill-only cases ------------------------------------------------------


def test_none_style_is_prefill_only(andy, squat, routine):
    rx = make_rx(routine, squat, style="none", low=5, high=8)
    log_session(andy, squat, TODAY - timedelta(days=3), [(100, 8, NORMAL, None)] * 3)
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "prefill"
    assert s.weight_kg == D("100")


def test_non_rep_metric_is_prefill_only(andy, routine):
    plank = Exercise.objects.create(name="Plank", slug="plank", metric="weight_time", active=True)
    rx = RoutineExercise.objects.create(
        routine=routine, exercise=plank, position=0, target_sets=3, progression_style="double"
    )
    started = timezone.make_aware(timezone.datetime(2026, 7, 17, 12, 0))
    session = WorkoutSession.objects.create(user=andy, started_at=started, ended_at=started)
    SetLog.objects.create(
        session=session,
        exercise=plank,
        position=0,
        weight_kg=0,
        duration_seconds=60,
        completed_at=started,
    )
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "prefill"


def test_no_history_yields_fresh_suggestion(andy, squat, routine):
    rx = make_rx(routine, squat, style="double")
    s = suggest(rx, andy, today=TODAY)
    assert s.kind == "fresh"
    assert s.weight_kg is None


def test_suggestion_writes_nothing(andy, squat, routine):
    rx = make_rx(routine, squat, style="double", low=5, high=8)
    log_session(andy, squat, TODAY - timedelta(days=3), [(100, 8, NORMAL, None)] * 3)
    before_sets = SetLog.objects.count()
    suggest(rx, andy, today=TODAY)
    assert SetLog.objects.count() == before_sets
    rx.refresh_from_db()
    assert rx.progression_increment_kg == D("2.5")  # untouched
