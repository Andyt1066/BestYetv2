from django.contrib import admin

from apps.exercises.models import Exercise, ExerciseMuscle, MuscleGroup


class ExerciseMuscleInline(admin.TabularInline):
    model = ExerciseMuscle
    extra = 0


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "active",
        "load_type",
        "metric",
        "bar_weight_kg",
        "unilateral",
        "is_mobility",
        "dots_eligible",
        "equipment",
        "source",
    )
    list_editable = ("active", "dots_eligible")
    list_filter = ("active", "source", "load_type", "metric", "equipment", "is_mobility")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("source", "created_at", "updated_at")
    inlines = (ExerciseMuscleInline,)


@admin.register(MuscleGroup)
class MuscleGroupAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
