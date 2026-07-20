import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.exercises.models import Exercise
from apps.logbook.models import SetLog, WorkoutSession

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


def test_plate_endpoint_returns_per_side(as_andy, squat):
    resp = as_andy.get(
        reverse("logbook:plates"), {"exercise": squat.pk, "weight": "100"}, secure=True
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["achievable"] is True
    assert data["per_side"] == ["25", "15"]


def test_plate_endpoint_uses_profile_inventory(as_andy, andy, squat):
    andy.profile.plate_inventory = [20, 10, 5]
    andy.profile.save()
    resp = as_andy.get(
        reverse("logbook:plates"), {"exercise": squat.pk, "weight": "60"}, secure=True
    )
    data = resp.json()
    assert data["per_side"] == ["20"]


def test_plate_endpoint_rejects_non_barbell(as_andy):
    db = Exercise.objects.create(name="DB Curl", slug="db-curl", active=True)
    resp = as_andy.get(reverse("logbook:plates"), {"exercise": db.pk, "weight": "20"}, secure=True)
    assert resp.status_code == 400


def test_warmup_endpoint_returns_scaffold_specs(as_andy, squat):
    resp = as_andy.get(
        reverse("logbook:warmups"), {"exercise": squat.pk, "weight": "100"}, secure=True
    )
    assert resp.status_code == 200
    sets = resp.json()["sets"]
    assert sets[0]["weight"] == "20"
    assert all(s["set_type"] == "warmup" for s in sets)
    # Generating warm-ups writes nothing (invariant 16).
    assert SetLog.objects.count() == 0


def test_warmup_endpoint_persists_nothing(as_andy, squat):
    as_andy.get(reverse("logbook:warmups"), {"exercise": squat.pk, "weight": "100"}, secure=True)
    assert SetLog.objects.count() == 0
    assert WorkoutSession.objects.count() == 0


def test_helper_endpoints_require_login(client, squat):
    assert client.get(
        reverse("logbook:plates"), {"exercise": squat.pk, "weight": "100"}
    ).status_code in (302, 403)


# --- backdated entry ---------------------------------------------------------


def test_backdated_flow_renders_datetime_picker_and_disables_timer(as_andy):
    resp = as_andy.get(reverse("logbook:new_backdated"), secure=True)
    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'type="datetime-local"' in content
    assert "data-backdated" in content


def test_backdated_session_start_accepts_past_datetime(as_andy, andy):
    session_id = str(uuid.uuid4())
    resp = as_andy.post(
        reverse("logbook:session_start"),
        data=json.dumps({"id": session_id, "started_at": "2026-07-01T10:00:00Z"}),
        content_type="application/json",
        secure=True,
    )
    assert resp.status_code == 200
    session = WorkoutSession.objects.get(pk=session_id)
    assert session.started_at.isoformat().startswith("2026-07-01")


def test_finish_accepts_backdated_ended_at(as_andy, andy):
    session_id = str(uuid.uuid4())
    as_andy.post(
        reverse("logbook:session_start"),
        data=json.dumps({"id": session_id, "started_at": "2026-07-01T10:00:00Z"}),
        content_type="application/json",
        secure=True,
    )
    resp = as_andy.post(
        reverse("logbook:session_finish", args=[session_id]),
        data=json.dumps({"ended_at": "2026-07-01T11:00:00Z"}),
        content_type="application/json",
        secure=True,
    )
    assert resp.status_code == 200
    session = WorkoutSession.objects.get(pk=session_id)
    assert session.ended_at.isoformat().startswith("2026-07-01T11")


def test_future_started_at_is_rejected(as_andy, andy):
    session_id = str(uuid.uuid4())
    resp = as_andy.post(
        reverse("logbook:session_start"),
        data=json.dumps({"id": session_id, "started_at": "2099-01-01T10:00:00Z"}),
        content_type="application/json",
        secure=True,
    )
    assert resp.status_code == 400
    assert not WorkoutSession.objects.filter(pk=session_id).exists()
