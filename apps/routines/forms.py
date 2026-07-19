from django import forms

from apps.exercises.models import Exercise, Metric
from apps.routines.models import Routine, RoutineExercise, Visibility

INPUT_CSS = (
    "min-h-11 w-full rounded-lg border border-zinc-300 px-3 py-2 "
    "dark:border-zinc-700 dark:bg-zinc-900"
)
NUMBER_CSS = INPUT_CSS + " text-center"


class RoutineCreateForm(forms.ModelForm):
    class Meta:
        model = Routine
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CSS, "autofocus": True}),
            "description": forms.Textarea(attrs={"class": INPUT_CSS, "rows": 2}),
        }


class RoutineForm(forms.ModelForm):
    # Users may make a routine private or shared; curated is system-only
    # (invariant 12), so it is not offered.
    visibility = forms.ChoiceField(
        choices=[
            (Visibility.PRIVATE, "Private"),
            (Visibility.SHARED, "Shared with other users"),
        ],
        widget=forms.Select(attrs={"class": INPUT_CSS}),
    )

    class Meta:
        model = Routine
        fields = ["name", "description", "visibility"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CSS}),
            "description": forms.Textarea(attrs={"class": INPUT_CSS, "rows": 2}),
        }


class RoutineExerciseForm(forms.ModelForm):
    class Meta:
        model = RoutineExercise
        fields = [
            "exercise",
            "position",
            "superset_group",
            "target_sets",
            "target_reps_low",
            "target_reps_high",
            "target_rpe",
            "rest_seconds",
            "superset_rest_seconds",
            "last_set_amrap",
            "target_duration_seconds",
            "target_distance_m",
            "progression_style",
            "progression_increment_kg",
            "notes",
        ]
        widgets = {
            "position": forms.HiddenInput(),
            "exercise": forms.Select(attrs={"class": INPUT_CSS}),
            "superset_group": forms.NumberInput(
                attrs={"class": NUMBER_CSS, "inputmode": "numeric"}
            ),
            "target_sets": forms.NumberInput(attrs={"class": NUMBER_CSS, "inputmode": "numeric"}),
            "target_reps_low": forms.NumberInput(
                attrs={"class": NUMBER_CSS, "inputmode": "numeric"}
            ),
            "target_reps_high": forms.NumberInput(
                attrs={"class": NUMBER_CSS, "inputmode": "numeric"}
            ),
            "target_rpe": forms.NumberInput(
                attrs={"class": NUMBER_CSS, "inputmode": "decimal", "step": "0.5"}
            ),
            "rest_seconds": forms.NumberInput(attrs={"class": NUMBER_CSS, "inputmode": "numeric"}),
            "superset_rest_seconds": forms.NumberInput(
                attrs={"class": NUMBER_CSS, "inputmode": "numeric"}
            ),
            "target_duration_seconds": forms.NumberInput(
                attrs={"class": NUMBER_CSS, "inputmode": "numeric"}
            ),
            "target_distance_m": forms.NumberInput(
                attrs={"class": NUMBER_CSS, "inputmode": "decimal"}
            ),
            "progression_style": forms.Select(attrs={"class": INPUT_CSS}),
            "progression_increment_kg": forms.NumberInput(
                attrs={"class": NUMBER_CSS, "inputmode": "decimal", "step": "0.25"}
            ),
            "notes": forms.TextInput(attrs={"class": INPUT_CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exercise"].queryset = Exercise.objects.filter(active=True).order_by("name")

    def clean(self):
        cleaned = super().clean()
        exercise = cleaned.get("exercise")
        if not exercise:
            return cleaned
        if exercise.metric == Metric.WEIGHT_REPS and not cleaned.get("target_reps_low"):
            self.add_error("target_reps_low", "Rep target is required for this exercise.")
        if exercise.metric == Metric.WEIGHT_TIME and not cleaned.get("target_duration_seconds"):
            self.add_error(
                "target_duration_seconds", "A duration target is required for this exercise."
            )
        if exercise.metric == Metric.WEIGHT_DISTANCE_TIME and not cleaned.get("target_distance_m"):
            self.add_error("target_distance_m", "A distance target is required for this exercise.")
        return cleaned


RoutineExerciseFormSet = forms.inlineformset_factory(
    Routine,
    RoutineExercise,
    form=RoutineExerciseForm,
    extra=0,
    can_delete=True,
)
