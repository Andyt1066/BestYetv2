"""Ingest the free-exercise-db dataset (JSON + images) as seed exercises.

Usage:
    manage.py import_exercises path/to/exercises.json --images-dir path/to/images

Re-running is safe: source-derived fields refresh, curation fields (active,
load_type, metric, bar_weight_kg, unilateral, is_mobility, dots_eligible) are
never touched on existing rows.
"""

import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.exercises.models import Exercise, ExerciseMuscle, MuscleGroup, MuscleRole, Source

# free-exercise-db muscle vocabulary -> canonical MuscleGroup names (spec §4).
MUSCLE_MAP = {
    "abdominals": "core",
    "abductors": "glutes",
    "adductors": "quads",
    "biceps": "biceps",
    "calves": "calves",
    "chest": "chest",
    "forearms": "forearms",
    "glutes": "glutes",
    "hamstrings": "hamstrings",
    "lats": "back",
    "lower back": "back",
    "middle back": "back",
    "neck": "back",
    "quadriceps": "quads",
    "shoulders": "shoulders",
    "traps": "back",
    "triceps": "triceps",
}

# Fields owned by the dataset; refreshed on every import run.
SOURCE_FIELDS = ("name", "force", "mechanic", "equipment", "instructions", "image_paths")


class Command(BaseCommand):
    help = "Import exercises from a free-exercise-db JSON dump"

    def add_arguments(self, parser):
        parser.add_argument("data_path", help="Path to exercises.json")
        parser.add_argument(
            "--images-dir",
            required=True,
            help="Directory containing per-exercise image folders",
        )

    def handle(self, *args, **options):
        data_path = Path(options["data_path"])
        images_dir = Path(options["images_dir"])
        try:
            records = json.loads(data_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot read {data_path}: {exc}") from exc

        created = updated = 0
        image_bytes = 0
        for record in records:
            muscles = self._mapped_muscles(record)
            image_paths, copied_bytes = self._copy_images(record, images_dir)
            image_bytes += copied_bytes
            exercise, was_created = self._upsert(record, image_paths)
            self._sync_muscles(exercise, muscles)
            created += was_created
            updated += not was_created

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created} new, refreshed {updated} existing exercises; "
                f"copied {image_bytes / 1024 / 1024:.1f} MiB of images."
            )
        )

    def _mapped_muscles(self, record):
        raw_primary = record.get("primaryMuscles", [])
        raw_secondary = record.get("secondaryMuscles", [])
        unknown = [m for m in raw_primary + raw_secondary if m not in MUSCLE_MAP]
        if unknown:
            raise CommandError(
                f"Unmapped muscle names for '{record['name']}': {', '.join(sorted(set(unknown)))}"
            )
        primary = {MUSCLE_MAP[m] for m in raw_primary}
        secondary = {MUSCLE_MAP[m] for m in raw_secondary} - primary
        return {MuscleRole.PRIMARY: primary, MuscleRole.SECONDARY: secondary}

    def _copy_images(self, record, images_dir):
        image_paths = []
        copied_bytes = 0
        for rel in record.get("images", []):
            src = images_dir / rel
            if not src.is_file():
                raise CommandError(f"Missing image for '{record['name']}': {src}")
            dest = Path(settings.MEDIA_ROOT) / "exercises" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            copied_bytes += dest.stat().st_size
            image_paths.append(f"exercises/{rel}")
        return image_paths, copied_bytes

    def _upsert(self, record, image_paths):
        values = {
            "name": record["name"],
            "force": record.get("force") or "",
            "mechanic": record.get("mechanic") or "",
            "equipment": record.get("equipment") or "",
            "instructions": "\n".join(record.get("instructions", [])),
            "image_paths": image_paths,
        }
        slug = slugify(record["name"])
        try:
            exercise = Exercise.objects.get(slug=slug)
        except Exercise.DoesNotExist:
            exercise = Exercise.objects.create(slug=slug, source=Source.SEED, **values)
            return exercise, True
        for field, value in values.items():
            setattr(exercise, field, value)
        exercise.save(update_fields=[*SOURCE_FIELDS, "updated_at"])
        return exercise, False

    def _sync_muscles(self, exercise, muscles):
        exercise.exercisemuscle_set.all().delete()
        for role, names in muscles.items():
            for name in sorted(names):
                group, _ = MuscleGroup.objects.get_or_create(name=name)
                ExerciseMuscle.objects.create(exercise=exercise, muscle_group=group, role=role)
