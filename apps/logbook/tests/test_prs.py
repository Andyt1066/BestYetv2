from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.exercises.models import Exercise
from apps.logbook.models import SetLog, WorkoutSession
from apps.logbook.prs import epley_e1rm, pr_check

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


@pytest.fixture
def squat():
    return Exercise.objects.create(name="Barbell Squat", slug="barbell-squat", active=True)


def add_set(user, exercise, weight, reps, set_type="normal", **kw):
    session = WorkoutSession.objects.create(user=user, started_at=timezone.now())
    return SetLog.objects.create(
        session=session,
        exercise=exercise,
        position=0,
        weight_kg=weight,
        reps=reps,
        set_type=set_type,
        completed_at=timezone.now(),
        **kw,
    )


def test_epley_formula():
    assert epley_e1rm(Decimal("100"), 5) == Decimal("116.67")
    assert epley_e1rm(Decimal("100"), 1) == Decimal("103.33")


def test_epley_excludes_high_reps():
    # Over 12 reps: estimate degrades, excluded entirely.
    assert epley_e1rm(Decimal("60"), 13) is None


def test_first_ever_set_is_a_pr(andy, squat):
    entry = add_set(andy, squat, 100, 5)
    result = pr_check(entry)
    assert result["max_weight"] is True
    assert result["best_e1rm"] is True


def test_heavier_weight_flags_max_weight_pr(andy, squat):
    add_set(andy, squat, 100, 5)
    entry = add_set(andy, squat, 105, 3)
    result = pr_check(entry)
    assert result["max_weight"] is True


def test_lighter_weight_is_not_max_weight_pr(andy, squat):
    add_set(andy, squat, 120, 3)
    entry = add_set(andy, squat, 100, 5)
    result = pr_check(entry)
    assert result["max_weight"] is False


def test_better_e1rm_at_lighter_weight(andy, squat):
    add_set(andy, squat, 120, 1)  # e1RM 124
    entry = add_set(andy, squat, 110, 5)  # e1RM 128.33
    result = pr_check(entry)
    assert result["max_weight"] is False
    assert result["best_e1rm"] is True


def test_warmup_sets_excluded_from_history(andy, squat):
    add_set(andy, squat, 200, 5, set_type="warmup")  # ignored
    entry = add_set(andy, squat, 100, 5)
    result = pr_check(entry)
    assert result["max_weight"] is True


def test_warmup_set_itself_is_never_a_pr(andy, squat):
    entry = add_set(andy, squat, 100, 5, set_type="warmup")
    result = pr_check(entry)
    assert result["any"] is False


def test_high_rep_set_gets_no_e1rm_pr_but_can_hold_weight_pr(andy, squat):
    entry = add_set(andy, squat, 60, 15)
    result = pr_check(entry)
    assert result["best_e1rm"] is False
    assert result["max_weight"] is True


def test_pr_check_is_scoped_per_user(andy, squat):
    other = User.objects.create_user(username="robyn", password="pass-2")
    add_set(other, squat, 300, 3)  # Robyn's monster lift
    entry = add_set(andy, squat, 100, 5)
    result = pr_check(entry)
    assert result["max_weight"] is True  # Andy's own first set
