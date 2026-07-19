from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.exercises.models import Exercise
from apps.routines.models import Routine, RoutineExercise, RoutineRotation

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


@pytest.fixture
def squat():
    return Exercise.objects.create(name="Barbell Squat", slug="barbell-squat", active=True)


def make_routine(owner, **overrides):
    fields = {"name": "Leg day", "owner": owner}
    fields.update(overrides)
    return Routine.objects.create(**fields)


def test_routine_defaults(andy):
    routine = make_routine(andy)
    assert routine.visibility == "private"
    assert routine.archived is False
    assert routine.cloned_from is None
    assert routine.deleted_at is None
    assert routine.id is not None


def test_soft_delete_hides_from_default_manager(andy):
    routine = make_routine(andy)
    routine.delete()
    routine.refresh_from_db()
    assert routine.deleted_at is not None
    assert not Routine.objects.filter(pk=routine.pk).exists()
    assert Routine.all_objects.filter(pk=routine.pk).exists()


def test_restore_clears_deleted_at(andy):
    routine = make_routine(andy)
    routine.delete()
    routine.restore()
    assert Routine.objects.filter(pk=routine.pk).exists()


def test_curated_routine_must_have_no_owner(andy):
    with pytest.raises(IntegrityError):
        make_routine(andy, visibility="curated")


def test_ownerless_routine_must_be_curated():
    with pytest.raises(IntegrityError):
        make_routine(None, visibility="private")


def test_routine_exercise_defaults(andy, squat):
    routine = make_routine(andy)
    entry = RoutineExercise.objects.create(
        routine=routine, exercise=squat, position=0, target_sets=5, target_reps_low=5
    )
    assert entry.progression_style == "double"
    assert entry.progression_increment_kg == Decimal("2.5")
    assert entry.last_set_amrap is False
    assert entry.superset_group is None
    assert entry.target_reps_high is None


def test_clone_for_copies_structure_and_marks_provenance(andy, squat):
    curated = Routine.objects.create(name="Beginner full-body 5x5", visibility="curated")
    RoutineExercise.objects.create(
        routine=curated,
        exercise=squat,
        position=0,
        target_sets=5,
        target_reps_low=5,
        rest_seconds=180,
        progression_style="linear",
    )

    clone = curated.clone_for(andy)

    assert clone.pk != curated.pk
    assert clone.owner == andy
    assert clone.visibility == "private"
    assert clone.cloned_from == curated
    assert clone.name == curated.name
    entries = list(clone.exercises.all())
    assert len(entries) == 1
    assert entries[0].exercise == squat
    assert entries[0].rest_seconds == 180
    assert entries[0].progression_style == "linear"
    # The source is untouched and independent.
    assert curated.exercises.count() == 1
    assert entries[0].pk != curated.exercises.get().pk


def test_rotation_orders_by_position(andy, squat):
    push = make_routine(andy, name="Push")
    pull = make_routine(andy, name="Pull")
    RoutineRotation.objects.create(user=andy, routine=pull, position=1)
    RoutineRotation.objects.create(user=andy, routine=push, position=0)
    names = [r.routine.name for r in RoutineRotation.objects.filter(user=andy)]
    assert names == ["Push", "Pull"]


def test_routine_appears_once_in_rotation(andy):
    push = make_routine(andy, name="Push")
    RoutineRotation.objects.create(user=andy, routine=push, position=0)
    with pytest.raises(IntegrityError):
        RoutineRotation.objects.create(user=andy, routine=push, position=1)


def test_archived_routine_cannot_join_rotation(andy):
    old = make_routine(andy, name="Old plan", archived=True)
    entry = RoutineRotation(user=andy, routine=old, position=0)
    with pytest.raises(ValidationError):
        entry.full_clean()
