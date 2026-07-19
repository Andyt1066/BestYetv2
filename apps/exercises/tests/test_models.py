import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.exercises.models import Exercise, ExerciseMuscle, MuscleGroup

pytestmark = pytest.mark.django_db


def make_exercise(**overrides):
    fields = {"name": "Barbell Squat", "slug": "barbell-squat"}
    fields.update(overrides)
    return Exercise.objects.create(**fields)


def test_exercise_defaults():
    exercise = make_exercise()
    assert exercise.metric == "weight_reps"
    assert exercise.load_type == "external"
    assert exercise.unilateral is False
    assert exercise.is_mobility is False
    assert exercise.dots_eligible is False
    assert exercise.active is False
    assert exercise.source == "custom"
    assert exercise.bar_weight_kg is None
    assert exercise.created_by is None
    assert exercise.id is not None  # UUID assigned


def test_slug_must_be_unique():
    make_exercise()
    with pytest.raises(IntegrityError):
        make_exercise(name="Other", slug="barbell-squat")


def test_bar_weight_rejected_on_bodyweight_plus_at_validation():
    exercise = Exercise(
        name="Weighted Pull-up",
        slug="weighted-pull-up",
        load_type="bodyweight_plus",
        bar_weight_kg=20,
    )
    with pytest.raises(ValidationError) as excinfo:
        exercise.full_clean()
    assert "bar_weight_kg" in excinfo.value.message_dict


def test_bar_weight_rejected_on_bodyweight_plus_at_db_level():
    with pytest.raises(IntegrityError):
        make_exercise(
            name="Weighted Dip",
            slug="weighted-dip",
            load_type="bodyweight_plus",
            bar_weight_kg=20,
        )


def test_bar_weight_allowed_on_external():
    exercise = make_exercise(bar_weight_kg=20)
    exercise.full_clean()
    assert exercise.bar_weight_kg == 20


def test_exercise_muscles_link_with_roles():
    exercise = make_exercise()
    quads = MuscleGroup.objects.create(name="quads")
    glutes = MuscleGroup.objects.create(name="glutes")
    ExerciseMuscle.objects.create(exercise=exercise, muscle_group=quads, role="primary")
    ExerciseMuscle.objects.create(exercise=exercise, muscle_group=glutes, role="secondary")
    assert list(
        exercise.muscles.filter(exercisemuscle__role="primary").values_list("name", flat=True)
    ) == ["quads"]


def test_same_muscle_cannot_be_linked_twice():
    exercise = make_exercise()
    quads = MuscleGroup.objects.create(name="quads")
    ExerciseMuscle.objects.create(exercise=exercise, muscle_group=quads, role="primary")
    with pytest.raises(IntegrityError):
        ExerciseMuscle.objects.create(exercise=exercise, muscle_group=quads, role="secondary")


def test_muscle_group_name_unique():
    MuscleGroup.objects.create(name="chest")
    with pytest.raises(IntegrityError):
        MuscleGroup.objects.create(name="chest")
