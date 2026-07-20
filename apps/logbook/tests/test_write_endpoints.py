import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.exercises.models import Exercise
from apps.logbook.models import CardioLog, SetLog, WorkoutSession

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
    return Exercise.objects.create(name="Barbell Squat", slug="barbell-squat", active=True)


def post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json", secure=True)


def start_session(client, session_id=None):
    session_id = session_id or str(uuid.uuid4())
    resp = post_json(
        client,
        reverse("logbook:session_start"),
        {"id": session_id, "started_at": timezone.now().isoformat()},
    )
    return session_id, resp


def set_payload(session_id, exercise, **overrides):
    payload = {
        "id": str(uuid.uuid4()),
        "session": session_id,
        "exercise": str(exercise.pk),
        "position": 0,
        "weight_kg": "100.00",
        "reps": 5,
    }
    payload.update(overrides)
    return payload


# --- session lifecycle -------------------------------------------------------


def test_start_session_creates_row(as_andy, andy):
    session_id, resp = start_session(as_andy)
    assert resp.status_code == 200
    assert WorkoutSession.objects.filter(pk=session_id, user=andy).exists()


def test_start_session_is_idempotent(as_andy, andy):
    session_id, _ = start_session(as_andy)
    _, resp = start_session(as_andy, session_id=session_id)
    assert resp.status_code == 200
    assert WorkoutSession.objects.filter(user=andy).count() == 1


def test_start_session_with_empty_routine_is_freeform(as_andy, andy):
    session_id = str(uuid.uuid4())
    resp = post_json(
        as_andy,
        reverse("logbook:session_start"),
        {"id": session_id, "routine": "", "started_at": timezone.now().isoformat()},
    )
    assert resp.status_code == 200
    assert WorkoutSession.objects.get(pk=session_id).routine_id is None


def test_start_session_records_routine(as_andy, andy):
    from apps.routines.models import Routine

    routine = Routine.objects.create(owner=andy, name="Leg day")
    session_id = str(uuid.uuid4())
    post_json(
        as_andy,
        reverse("logbook:session_start"),
        {"id": session_id, "routine": str(routine.pk)},
    )
    assert WorkoutSession.objects.get(pk=session_id).routine_id == routine.pk


def test_finish_session_sets_ended_at(as_andy, andy):
    session_id, _ = start_session(as_andy)
    resp = post_json(
        as_andy,
        reverse("logbook:session_finish", args=[session_id]),
        {"session_rpe": "8.5", "notes": "solid"},
    )
    assert resp.status_code == 200
    session = WorkoutSession.objects.get(pk=session_id)
    assert session.ended_at is not None
    assert str(session.session_rpe) == "8.5"


def test_finish_is_idempotent(as_andy, andy):
    session_id, _ = start_session(as_andy)
    post_json(as_andy, reverse("logbook:session_finish", args=[session_id]), {})
    first_end = WorkoutSession.objects.get(pk=session_id).ended_at
    post_json(as_andy, reverse("logbook:session_finish", args=[session_id]), {})
    assert WorkoutSession.objects.get(pk=session_id).ended_at == first_end


# --- set upsert --------------------------------------------------------------


def test_complete_set_creates_row(as_andy, squat):
    session_id, _ = start_session(as_andy)
    payload = set_payload(session_id, squat)
    resp = post_json(as_andy, reverse("logbook:set_upsert"), payload)
    assert resp.status_code == 200
    assert SetLog.objects.filter(pk=payload["id"]).exists()


def test_replaying_set_write_does_not_duplicate(as_andy, squat):
    session_id, _ = start_session(as_andy)
    payload = set_payload(session_id, squat)
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    assert SetLog.objects.filter(session_id=session_id).count() == 1


def test_upsert_updates_existing_set(as_andy, squat):
    session_id, _ = start_session(as_andy)
    payload = set_payload(session_id, squat)
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    payload["weight_kg"] = "105.00"
    payload["reps"] = 3
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    entry = SetLog.objects.get(pk=payload["id"])
    assert str(entry.weight_kg) == "105.00"
    assert entry.reps == 3


def test_set_write_response_includes_pr_flash(as_andy, squat):
    session_id, _ = start_session(as_andy)
    resp = post_json(as_andy, reverse("logbook:set_upsert"), set_payload(session_id, squat))
    data = resp.json()
    assert data["pr"]["max_weight"] is True
    assert data["pr"]["best_e1rm"] is True


def test_set_validation_rejected(as_andy, squat):
    session_id, _ = start_session(as_andy)
    payload = set_payload(session_id, squat, reps=None)
    resp = post_json(as_andy, reverse("logbook:set_upsert"), payload)
    assert resp.status_code == 400
    assert "reps" in resp.json()["errors"]


def test_delete_set_is_soft_and_idempotent(as_andy, squat):
    session_id, _ = start_session(as_andy)
    payload = set_payload(session_id, squat)
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    url = reverse("logbook:set_delete", args=[payload["id"]])
    post_json(as_andy, url, {})
    post_json(as_andy, url, {})  # replay
    assert not SetLog.objects.filter(pk=payload["id"]).exists()
    assert SetLog.all_objects.get(pk=payload["id"]).deleted_at is not None


def test_undo_delete_restores_set(as_andy, squat):
    session_id, _ = start_session(as_andy)
    payload = set_payload(session_id, squat)
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    post_json(as_andy, reverse("logbook:set_delete", args=[payload["id"]]), {})
    resp = post_json(as_andy, reverse("logbook:set_restore", args=[payload["id"]]), {})
    assert resp.status_code == 200
    assert SetLog.objects.filter(pk=payload["id"]).exists()


def test_restore_is_idempotent(as_andy, squat):
    session_id, _ = start_session(as_andy)
    payload = set_payload(session_id, squat)
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    url = reverse("logbook:set_restore", args=[payload["id"]])
    post_json(as_andy, url, {})
    post_json(as_andy, url, {})
    assert SetLog.objects.filter(pk=payload["id"]).count() == 1


# --- post-finish editing -----------------------------------------------------


def test_editing_finished_session_set_marks_edited(as_andy, squat):
    session_id, _ = start_session(as_andy)
    payload = set_payload(session_id, squat)
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    post_json(as_andy, reverse("logbook:session_finish", args=[session_id]), {})
    payload["weight_kg"] = "110.00"
    post_json(as_andy, reverse("logbook:set_upsert"), payload)
    assert WorkoutSession.objects.get(pk=session_id).edited_at is not None


# --- cardio ------------------------------------------------------------------


def test_cardio_upsert_idempotent(as_andy, andy):
    cardio_id = str(uuid.uuid4())
    payload = {
        "id": cardio_id,
        "activity": "outdoor_run",
        "duration_seconds": 1800,
        "distance_m": "5000.0",
        "performed_at": timezone.now().isoformat(),
    }
    post_json(as_andy, reverse("logbook:cardio_upsert"), payload)
    post_json(as_andy, reverse("logbook:cardio_upsert"), payload)
    assert CardioLog.objects.filter(user=andy).count() == 1


# --- cross-user isolation (mandatory) ----------------------------------------


def test_cannot_write_set_into_another_users_session(as_andy, robyn, squat):
    others = WorkoutSession.objects.create(user=robyn, started_at=timezone.now())
    payload = set_payload(str(others.pk), squat)
    resp = post_json(as_andy, reverse("logbook:set_upsert"), payload)
    assert resp.status_code == 404
    assert SetLog.objects.filter(session=others).count() == 0


def test_cannot_finish_another_users_session(as_andy, robyn):
    others = WorkoutSession.objects.create(user=robyn, started_at=timezone.now())
    resp = post_json(as_andy, reverse("logbook:session_finish", args=[others.pk]), {})
    assert resp.status_code == 404
    others.refresh_from_db()
    assert others.ended_at is None


def test_cannot_delete_another_users_set(as_andy, robyn, squat):
    others = WorkoutSession.objects.create(user=robyn, started_at=timezone.now())
    entry = SetLog.objects.create(session=others, exercise=squat, position=0, weight_kg=100, reps=5)
    resp = post_json(as_andy, reverse("logbook:set_delete", args=[entry.pk]), {})
    assert resp.status_code == 404
    assert SetLog.objects.filter(pk=entry.pk).exists()


def test_uuid_collision_across_users_is_rejected(as_andy, robyn, squat):
    """A client UUID already owned by another user must not be hijacked."""
    others = WorkoutSession.objects.create(user=robyn, started_at=timezone.now())
    shared_id = SetLog.objects.create(
        session=others, exercise=squat, position=0, weight_kg=100, reps=5
    ).pk
    my_session, _ = start_session(as_andy)
    payload = set_payload(my_session, squat, id=str(shared_id))
    resp = post_json(as_andy, reverse("logbook:set_upsert"), payload)
    assert resp.status_code in (403, 404, 409)
    # Robyn's row is untouched.
    assert SetLog.objects.get(pk=shared_id).session_id == others.pk


def test_login_required(client, squat):
    resp = post_json(client, reverse("logbook:set_upsert"), {"id": str(uuid.uuid4())})
    assert resp.status_code in (302, 403)
