import json
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.exercises.models import Exercise
from apps.routines.models import Routine, RoutineExercise

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parent.parent / "fixtures" / "curated_routines.json"


def referenced_exercise_slugs():
    entries = json.loads(FIXTURE.read_text())
    return {
        entry["fields"]["exercise"][0]
        for entry in entries
        if entry["model"] == "routines.routineexercise"
    }


@pytest.fixture
def seed_exercises():
    for slug in referenced_exercise_slugs():
        Exercise.objects.create(
            name=slug.replace("-", " ").title(), slug=slug, source="seed", active=True
        )


def test_exercise_natural_key_round_trip(seed_exercises):
    slug = next(iter(referenced_exercise_slugs()))
    exercise = Exercise.objects.get_by_natural_key(slug)
    assert exercise.natural_key() == (slug,)


def test_fixture_loads_curated_starters(seed_exercises):
    call_command("loaddata", "curated_routines")
    routines = Routine.objects.filter(visibility="curated")
    assert routines.count() == 6
    assert all(r.owner is None for r in routines)
    names = set(routines.values_list("name", flat=True))
    assert "Beginner full-body 5x5" in names
    fullbody = routines.get(name="Beginner full-body 5x5")
    assert fullbody.exercises.count() == 5
    deadlift = fullbody.exercises.get(exercise__slug="barbell-deadlift")
    assert deadlift.target_sets == 1
    assert deadlift.progression_style == "linear"


def test_fixture_reload_is_idempotent(seed_exercises):
    call_command("loaddata", "curated_routines")
    routine_count = Routine.objects.count()
    entry_count = RoutineExercise.objects.count()
    call_command("loaddata", "curated_routines")
    assert Routine.objects.count() == routine_count
    assert RoutineExercise.objects.count() == entry_count
