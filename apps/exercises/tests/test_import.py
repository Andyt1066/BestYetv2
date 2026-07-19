import json
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command

from apps.exercises.models import Exercise, MuscleGroup

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def run_import(data_path=None, images_dir=None):
    call_command(
        "import_exercises",
        str(data_path or FIXTURES / "exercises.json"),
        images_dir=str(images_dir or FIXTURES / "images"),
    )


def test_import_creates_seed_exercises(media_root):
    run_import()
    assert Exercise.objects.count() == 2
    squat = Exercise.objects.get(slug="barbell-squat")
    assert squat.name == "Barbell Squat"
    assert squat.source == "seed"
    assert squat.active is False
    assert squat.force == "push"
    assert squat.mechanic == "compound"
    assert squat.equipment == "barbell"
    assert "sitting back with the hips" in squat.instructions


def test_import_maps_muscles_to_canonical_groups(media_root):
    run_import()
    squat = Exercise.objects.get(slug="barbell-squat")
    primary = set(
        squat.muscles.filter(exercisemuscle__role="primary").values_list("name", flat=True)
    )
    secondary = set(
        squat.muscles.filter(exercisemuscle__role="secondary").values_list("name", flat=True)
    )
    assert primary == {"quads"}
    # "lower back" maps into the canonical back group
    assert secondary == {"glutes", "hamstrings", "back"}


def test_muscle_in_both_lists_counts_as_primary_only(media_root):
    run_import()
    plank = Exercise.objects.get(slug="plank")
    roles = list(plank.exercisemuscle_set.values_list("muscle_group__name", "role"))
    assert roles == [("core", "primary")]


def test_import_copies_images_and_records_paths(media_root):
    run_import()
    squat = Exercise.objects.get(slug="barbell-squat")
    assert squat.image_paths == ["exercises/Barbell_Squat/0.jpg", "exercises/Barbell_Squat/1.jpg"]
    for rel in squat.image_paths:
        assert (media_root / rel).exists()
    plank = Exercise.objects.get(slug="plank")
    assert plank.image_paths == []


def test_reimport_is_idempotent_and_preserves_curation(media_root):
    run_import()
    squat = Exercise.objects.get(slug="barbell-squat")
    squat.active = True
    squat.bar_weight_kg = 20
    squat.dots_eligible = True
    squat.save()

    run_import()

    assert Exercise.objects.count() == 2
    squat.refresh_from_db()
    assert squat.active is True
    assert squat.bar_weight_kg == 20
    assert squat.dots_eligible is True
    assert MuscleGroup.objects.filter(name="quads").count() == 1


def test_reimport_refreshes_source_fields(media_root, tmp_path):
    run_import()
    data = json.loads((FIXTURES / "exercises.json").read_text())
    data[0]["instructions"] = ["Updated upstream instructions."]
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(data))

    run_import(data_path=edited)

    squat = Exercise.objects.get(slug="barbell-squat")
    assert squat.instructions == "Updated upstream instructions."


def test_unknown_muscle_fails_loudly(media_root, tmp_path):
    data = json.loads((FIXTURES / "exercises.json").read_text())
    data[0]["primaryMuscles"] = ["mystery muscle"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(CommandError, match="mystery muscle"):
        run_import(data_path=bad)
