import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.exercises.models import Exercise
from apps.logbook.models import CardioLog, SetLog, WorkoutSession

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


@pytest.fixture
def squat():
    return Exercise.objects.create(name="Barbell Squat", slug="barbell-squat", active=True)


@pytest.fixture
def pullup():
    return Exercise.objects.create(
        name="Weighted Pull-up",
        slug="weighted-pull-up",
        load_type="bodyweight_plus",
        active=True,
    )


@pytest.fixture
def plank():
    return Exercise.objects.create(name="Plank", slug="plank", metric="weight_time", active=True)


@pytest.fixture
def carry():
    return Exercise.objects.create(
        name="Farmer Walk", slug="farmer-walk", metric="weight_distance_time", active=True
    )


@pytest.fixture
def unilateral_curl():
    return Exercise.objects.create(
        name="One-Arm Curl", slug="one-arm-curl", unilateral=True, active=True
    )


def make_session(user, **overrides):
    fields = {"user": user, "started_at": timezone.now()}
    fields.update(overrides)
    return WorkoutSession.objects.create(**fields)


def make_set(session, exercise, **overrides):
    fields = {
        "session": session,
        "exercise": exercise,
        "position": 0,
        "weight_kg": 100,
        "reps": 5,
        "completed_at": timezone.now(),
    }
    fields.update(overrides)
    return SetLog.objects.create(**fields)


def test_session_accepts_client_uuid(andy):
    client_id = uuid.uuid4()
    session = make_session(andy, id=client_id)
    assert session.pk == client_id


def test_session_and_set_soft_delete(andy, squat):
    session = make_session(andy)
    entry = make_set(session, squat)
    entry.delete()
    assert not SetLog.objects.filter(pk=entry.pk).exists()
    assert SetLog.all_objects.filter(pk=entry.pk).exists()


def test_weight_reps_requires_reps(andy, squat):
    session = make_session(andy)
    entry = SetLog(session=session, exercise=squat, position=0, weight_kg=100, reps=None)
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "reps" in exc.value.message_dict


def test_weight_time_requires_duration(andy, plank):
    session = make_session(andy)
    entry = SetLog(session=session, exercise=plank, position=0, weight_kg=0, duration_seconds=None)
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "duration_seconds" in exc.value.message_dict


def test_weight_distance_time_requires_distance(andy, carry):
    session = make_session(andy)
    entry = SetLog(session=session, exercise=carry, position=0, weight_kg=40, distance_m=None)
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "distance_m" in exc.value.message_dict


def test_unilateral_requires_side(andy, unilateral_curl):
    session = make_session(andy)
    entry = SetLog(
        session=session, exercise=unilateral_curl, position=0, weight_kg=10, reps=8, side=None
    )
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "side" in exc.value.message_dict


def test_side_rejected_when_not_unilateral(andy, squat):
    session = make_session(andy)
    entry = SetLog(session=session, exercise=squat, position=0, weight_kg=100, reps=5, side="left")
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "side" in exc.value.message_dict


def test_negative_weight_rejected_for_external(andy, squat):
    session = make_session(andy)
    entry = SetLog(session=session, exercise=squat, position=0, weight_kg=-5, reps=5)
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "weight_kg" in exc.value.message_dict


def test_negative_weight_allowed_for_bodyweight_plus(andy, pullup):
    session = make_session(andy)
    entry = SetLog(session=session, exercise=pullup, position=0, weight_kg=-10, reps=5)
    entry.full_clean()  # band-assisted: no error
    entry.save()
    assert entry.weight_kg == -10


def test_negative_weight_rejected_at_db_level_for_external(andy, squat):
    session = make_session(andy)
    with pytest.raises(IntegrityError):
        make_set(session, squat, weight_kg=-5)


def test_started_at_cannot_be_in_future(andy):
    session = WorkoutSession(user=andy, started_at=timezone.now() + timedelta(days=1))
    with pytest.raises(ValidationError) as exc:
        session.full_clean()
    assert "started_at" in exc.value.message_dict


def test_ended_at_must_not_precede_started_at(andy):
    now = timezone.now()
    session = WorkoutSession(user=andy, started_at=now, ended_at=now - timedelta(minutes=5))
    with pytest.raises(ValidationError) as exc:
        session.full_clean()
    assert "ended_at" in exc.value.message_dict


def test_mark_edited_sets_edited_at(andy):
    session = make_session(andy, ended_at=timezone.now())
    assert session.edited_at is None
    session.mark_edited()
    session.refresh_from_db()
    assert session.edited_at is not None


def test_cardio_accepts_client_uuid_and_standalone(andy):
    client_id = uuid.uuid4()
    log = CardioLog.objects.create(
        id=client_id,
        user=andy,
        activity="outdoor_run",
        duration_seconds=1800,
        distance_m=5000,
        performed_at=timezone.now(),
    )
    assert log.pk == client_id
    assert log.session is None


def test_session_updated_at_maintained(andy):
    session = make_session(andy)
    first = session.updated_at
    session.notes = "felt strong"
    session.save()
    session.refresh_from_db()
    assert session.updated_at > first
