from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.exercises.models import Exercise, MuscleGroup


@login_required
def picker(request):
    exercises = Exercise.objects.filter(active=True).order_by("name")
    query = request.GET.get("q", "").strip()
    muscle = request.GET.get("muscle", "")
    equipment = request.GET.get("equipment", "")
    if query:
        exercises = exercises.filter(name__icontains=query)
    if muscle:
        exercises = exercises.filter(
            exercisemuscle__muscle_group_id=muscle, exercisemuscle__role="primary"
        )
    if equipment:
        exercises = exercises.filter(equipment=equipment)

    context = {
        "exercises": exercises[:50],
        "query": query,
        "muscle": muscle,
        "equipment": equipment,
    }
    if request.GET.get("results"):
        return render(request, "exercises/partials/_picker_results.html", context)
    context["muscle_groups"] = MuscleGroup.objects.order_by("name")
    context["equipment_choices"] = (
        Exercise.objects.filter(active=True)
        .exclude(equipment="")
        .values_list("equipment", flat=True)
        .distinct()
        .order_by("equipment")
    )
    return render(request, "exercises/partials/_picker.html", context)
