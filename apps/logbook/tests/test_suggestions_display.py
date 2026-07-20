from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.exercises.models import Exercise
from apps.logbook.models import SetLog, WorkoutSession
from apps.routines.deload import start_deload_week
from apps.routines.models import Routine, RoutineExercise

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


@pytest.fixture
def as_andy(client, andy):
    client.force_login(andy)
    return client


@pytest.fixture
def squat():
    return Exercise.objects.create(
        name="Barbell Squat", slug="barbell-squat", active=True, bar_weight_kg=20
    )


@pytest.fixture
def routine(andy, squat):
    r = Routine.objects.create(owner=andy, name="Leg day")
    RoutineExercise.objects.create(
        routine=r, exercise=squat, position=0, target_sets=3, target_reps_low=5, target_reps_high=8
    )
    return r


def log_finished(andy, squat, days_ago, weight, reps):
    when = timezone.now() - timedelta(days=days_ago)
    session = WorkoutSession.objects.create(user=andy, started_at=when, ended_at=when)
    for i in range(3):
        SetLog.objects.create(
            session=session,
            exercise=squat,
            position=i,
            weight_kg=Decimal(weight),
            reps=reps,
            completed_at=when,
        )


def test_scaffold_shows_progression_suggestion(as_andy, andy, squat, routine):
    log_finished(andy, squat, days_ago=3, weight="100", reps=8)  # hit top -> progress
    resp = as_andy.get(reverse("logbook:new", args=[routine.pk]), secure=True)
    content = resp.content.decode()
    assert "102.5" in content  # 100 + 2.5 progression suggestion
    assert "suggestion" in content.lower()


def test_scaffold_shows_deload_week_banner_and_scaled_suggestion(as_andy, andy, squat, routine):
    log_finished(andy, squat, days_ago=10, weight="100", reps=8)
    start_deload_week(andy, today=timezone.localdate())
    resp = as_andy.get(reverse("logbook:new", args=[routine.pk]), secure=True)
    content = resp.content.decode()
    assert "Deload week" in content
    assert "50" in content  # 100 * 50%


def test_dashboard_shows_deload_banner_when_active(as_andy, andy):
    start_deload_week(andy, today=timezone.localdate())
    resp = as_andy.get(reverse("logbook:start"), secure=True)
    assert "Deload week" in resp.content.decode()


def test_start_deload_button_shown_when_inactive(as_andy, andy):
    resp = as_andy.get(reverse("logbook:start"), secure=True)
    assert "Start deload week" in resp.content.decode()
