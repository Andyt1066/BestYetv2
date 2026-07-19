import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.exercises.models import Exercise
from apps.routines.models import Routine, RoutineExercise, RoutineRotation

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


def formset_payload(rows, initial=0):
    """Management form + row data for the exercise formset."""
    payload = {
        "exercises-TOTAL_FORMS": str(len(rows)),
        "exercises-INITIAL_FORMS": str(initial),
        "exercises-MIN_NUM_FORMS": "0",
        "exercises-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        defaults = {"progression_style": "double", "progression_increment_kg": "2.5"}
        defaults.update(row)
        for key, value in defaults.items():
            payload[f"exercises-{i}-{key}"] = str(value)
    return payload


def test_anonymous_is_redirected_to_login(client):
    for name in ["routines:list", "routines:library", "routines:rotation", "routines:create"]:
        response = client.get(reverse(name), secure=True)
        assert response.status_code == 302
        assert reverse("login") in response["Location"]


def test_list_shows_only_own_living_routines(as_andy, andy, robyn):
    mine = Routine.objects.create(owner=andy, name="My push day")
    theirs = Routine.objects.create(owner=robyn, name="Robyn secret plan")
    dead = Routine.objects.create(owner=andy, name="Deleted plan")
    dead.delete()
    response = as_andy.get(reverse("routines:list"), secure=True)
    content = response.content.decode()
    assert mine.name in content
    assert theirs.name not in content
    assert dead.name not in content


def test_create_routine_owned_and_private(as_andy, andy):
    response = as_andy.post(
        reverse("routines:create"), {"name": "New block", "description": ""}, secure=True
    )
    routine = Routine.objects.get(owner=andy, name="New block")
    assert routine.visibility == "private"
    assert response.status_code == 302


def test_edit_updates_routine_and_exercises(as_andy, andy, squat):
    routine = Routine.objects.create(owner=andy, name="Leg day")
    payload = {
        "name": "Leg day A",
        "description": "",
        "visibility": "private",
        **formset_payload(
            [
                {
                    "exercise": squat.pk,
                    "position": 0,
                    "target_sets": 5,
                    "target_reps_low": 5,
                    "rest_seconds": 180,
                }
            ]
        ),
    }
    response = as_andy.post(reverse("routines:edit", args=[routine.pk]), payload, secure=True)
    assert response.status_code == 302
    routine.refresh_from_db()
    assert routine.name == "Leg day A"
    entry = routine.exercises.get()
    assert entry.exercise == squat
    assert entry.target_sets == 5


def test_cannot_open_or_edit_someone_elses_routine(as_andy, robyn):
    theirs = Routine.objects.create(owner=robyn, name="Robyn plan")
    assert as_andy.get(reverse("routines:edit", args=[theirs.pk]), secure=True).status_code == 404
    response = as_andy.post(
        reverse("routines:edit", args=[theirs.pk]), {"name": "hijack"}, secure=True
    )
    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.name == "Robyn plan"


def test_curated_routines_are_read_only(as_andy):
    curated = Routine.objects.create(name="Beginner full-body 5x5", visibility="curated")
    assert as_andy.get(reverse("routines:edit", args=[curated.pk]), secure=True).status_code == 404


def test_visibility_cannot_be_set_to_curated(as_andy, andy):
    routine = Routine.objects.create(owner=andy, name="Mine")
    payload = {"name": "Mine", "description": "", "visibility": "curated", **formset_payload([])}
    response = as_andy.post(reverse("routines:edit", args=[routine.pk]), payload, secure=True)
    assert response.status_code == 200  # form redisplayed with errors
    routine.refresh_from_db()
    assert routine.visibility == "private"


def test_library_lists_curated_and_others_shared(as_andy, robyn):
    curated = Routine.objects.create(name="Beginner full-body 5x5", visibility="curated")
    shared = Routine.objects.create(owner=robyn, name="Robyn shared split", visibility="shared")
    private = Routine.objects.create(owner=robyn, name="Robyn private plan")
    content = as_andy.get(reverse("routines:library"), secure=True).content.decode()
    assert curated.name in content
    assert shared.name in content
    assert private.name not in content


def test_clone_curated_creates_owned_private_copy(as_andy, andy, squat):
    curated = Routine.objects.create(name="Beginner full-body 5x5", visibility="curated")
    RoutineExercise.objects.create(
        routine=curated, exercise=squat, position=0, target_sets=5, target_reps_low=5
    )
    response = as_andy.post(reverse("routines:clone", args=[curated.pk]), secure=True)
    assert response.status_code == 302
    clone = Routine.objects.get(owner=andy)
    assert clone.cloned_from == curated
    assert clone.visibility == "private"
    assert clone.exercises.count() == 1


def test_cannot_clone_someone_elses_private_routine(as_andy, robyn):
    private = Routine.objects.create(owner=robyn, name="Robyn private plan")
    response = as_andy.post(reverse("routines:clone", args=[private.pk]), secure=True)
    assert response.status_code == 404


def test_delete_is_soft(as_andy, andy):
    routine = Routine.objects.create(owner=andy, name="Old plan")
    as_andy.post(reverse("routines:delete", args=[routine.pk]), secure=True)
    assert not Routine.objects.filter(pk=routine.pk).exists()
    assert Routine.all_objects.get(pk=routine.pk).deleted_at is not None


def test_archive_toggle(as_andy, andy):
    routine = Routine.objects.create(owner=andy, name="Winter block")
    as_andy.post(reverse("routines:archive", args=[routine.pk]), secure=True)
    routine.refresh_from_db()
    assert routine.archived is True
    as_andy.post(reverse("routines:archive", args=[routine.pk]), secure=True)
    routine.refresh_from_db()
    assert routine.archived is False


def test_rotation_add_reorder_remove(as_andy, andy):
    push = Routine.objects.create(owner=andy, name="Push")
    pull = Routine.objects.create(owner=andy, name="Pull")
    as_andy.post(reverse("routines:rotation_add"), {"routine": push.pk}, secure=True)
    as_andy.post(reverse("routines:rotation_add"), {"routine": pull.pk}, secure=True)
    assert [r.routine for r in RoutineRotation.objects.filter(user=andy)] == [push, pull]

    as_andy.post(
        reverse("routines:rotation_reorder"), {"order": [str(pull.pk), str(push.pk)]}, secure=True
    )
    assert [r.routine for r in RoutineRotation.objects.filter(user=andy)] == [pull, push]

    as_andy.post(reverse("routines:rotation_remove"), {"routine": push.pk}, secure=True)
    assert [r.routine for r in RoutineRotation.objects.filter(user=andy)] == [pull]


def test_archived_routine_rejected_from_rotation(as_andy, andy):
    old = Routine.objects.create(owner=andy, name="Old plan", archived=True)
    response = as_andy.post(reverse("routines:rotation_add"), {"routine": old.pk}, secure=True)
    assert response.status_code == 400
    assert RoutineRotation.objects.filter(user=andy).count() == 0


def test_cannot_add_others_routine_to_rotation(as_andy, robyn):
    theirs = Routine.objects.create(owner=robyn, name="Robyn plan")
    response = as_andy.post(reverse("routines:rotation_add"), {"routine": theirs.pk}, secure=True)
    assert response.status_code == 404


def test_exercise_picker_returns_active_matches_only(as_andy, squat):
    Exercise.objects.create(name="Barbell Hack Squat", slug="barbell-hack-squat", active=False)
    response = as_andy.get(reverse("exercises:picker"), {"q": "squat"}, secure=True)
    content = response.content.decode()
    assert "Barbell Squat" in content
    assert "Barbell Hack Squat" not in content


def test_builder_enforces_per_metric_targets(as_andy, andy):
    plank = Exercise.objects.create(name="Plank", slug="plank", active=True, metric="weight_time")
    routine = Routine.objects.create(owner=andy, name="Core day")
    payload = {
        "name": "Core day",
        "description": "",
        "visibility": "private",
        **formset_payload(
            [{"exercise": plank.pk, "position": 0, "target_sets": 3}]  # duration missing
        ),
    }
    response = as_andy.post(reverse("routines:edit", args=[routine.pk]), payload, secure=True)
    assert response.status_code == 200
    assert "duration" in response.content.decode().lower()
    assert routine.exercises.count() == 0
