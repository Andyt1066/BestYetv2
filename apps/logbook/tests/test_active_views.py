import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.exercises.models import Exercise
from apps.logbook.models import SetLog, WorkoutSession
from apps.routines.models import Routine, RoutineExercise

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


@pytest.fixture
def robyn():
    return User.objects.create_user(username="robyn", password="pass-2")


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
        routine=r,
        exercise=squat,
        position=0,
        target_sets=3,
        target_reps_low=5,
        target_reps_high=8,
        rest_seconds=180,
    )
    return r


def test_start_screen_lists_routines_and_freeform(as_andy, routine):
    resp = as_andy.get(reverse("logbook:start"), secure=True)
    assert resp.status_code == 200
    content = resp.content.decode()
    assert routine.name in content
    assert "Freeform" in content


def test_new_from_routine_renders_scaffold(as_andy, routine, squat):
    resp = as_andy.get(reverse("logbook:new", args=[routine.pk]), secure=True)
    assert resp.status_code == 200
    content = resp.content.decode()
    assert squat.name in content
    # Scaffold shows the plan but persists nothing (invariant 9).
    assert "3" in content  # target sets
    assert WorkoutSession.objects.count() == 0
    assert SetLog.objects.count() == 0


def test_new_from_routine_includes_crypto_uuid_and_session_seed(as_andy, routine):
    resp = as_andy.get(reverse("logbook:new", args=[routine.pk]), secure=True)
    content = resp.content.decode()
    assert "randomUUID" in content or "data-session-id" in content


def test_cannot_start_from_another_users_routine(as_andy, robyn):
    theirs = Routine.objects.create(owner=robyn, name="Robyn plan")
    resp = as_andy.get(reverse("logbook:new", args=[theirs.pk]), secure=True)
    assert resp.status_code == 404


def test_can_start_from_curated_routine(as_andy, squat):
    curated = Routine.objects.create(name="Starter", visibility="curated")
    RoutineExercise.objects.create(
        routine=curated, exercise=squat, position=0, target_sets=5, target_reps_low=5
    )
    resp = as_andy.get(reverse("logbook:new", args=[curated.pk]), secure=True)
    assert resp.status_code == 200


def test_freeform_new_renders_empty_scaffold(as_andy):
    resp = as_andy.get(reverse("logbook:new_freeform"), secure=True)
    assert resp.status_code == 200
    assert "Add exercise" in resp.content.decode()


def test_active_session_shows_logged_sets(as_andy, andy, squat):
    session = WorkoutSession.objects.create(user=andy, started_at=timezone.now())
    SetLog.objects.create(session=session, exercise=squat, position=0, weight_kg=100, reps=5)
    resp = as_andy.get(reverse("logbook:active", args=[session.pk]), secure=True)
    content = resp.content.decode()
    assert "100" in content
    assert squat.name in content


def test_resuming_routine_session_shows_completed_scaffold_sets(as_andy, andy, routine, squat):
    # A set completed for a routine exercise must render as complete on resume,
    # not as a blank scaffold row (the logged value must survive).
    session = WorkoutSession.objects.create(user=andy, routine=routine, started_at=timezone.now())
    SetLog.objects.create(session=session, exercise=squat, position=0, weight_kg=142.5, reps=5)
    resp = as_andy.get(reverse("logbook:active", args=[session.pk]), secure=True)
    content = resp.content.decode()
    assert "142.5" in content
    assert "is-complete" in content


def test_cannot_view_another_users_active_session(as_andy, robyn):
    theirs = WorkoutSession.objects.create(user=robyn, started_at=timezone.now())
    resp = as_andy.get(reverse("logbook:active", args=[theirs.pk]), secure=True)
    assert resp.status_code == 404


def test_history_sheet_shows_previous_performance(as_andy, andy, squat):
    old = WorkoutSession.objects.create(user=andy, started_at=timezone.now())
    SetLog.objects.create(session=old, exercise=squat, position=0, weight_kg=95, reps=6)
    resp = as_andy.get(reverse("logbook:exercise_history", args=[squat.pk]), secure=True)
    content = resp.content.decode()
    assert "95" in content


def test_history_sheet_is_user_scoped(as_andy, robyn, squat):
    theirs = WorkoutSession.objects.create(user=robyn, started_at=timezone.now())
    SetLog.objects.create(session=theirs, exercise=squat, position=0, weight_kg=200, reps=3)
    resp = as_andy.get(reverse("logbook:exercise_history", args=[squat.pk]), secure=True)
    assert "200" not in resp.content.decode()


def test_dashboard_banner_for_unfinished_session(as_andy, andy):
    WorkoutSession.objects.create(user=andy, started_at=timezone.now())
    resp = as_andy.get(reverse("logbook:start"), secure=True)
    assert "in progress" in resp.content.decode().lower()


def test_start_requires_login(client):
    resp = client.get(reverse("logbook:start"), secure=True)
    assert resp.status_code == 302
