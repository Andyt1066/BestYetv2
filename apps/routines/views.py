from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.routines.forms import RoutineCreateForm, RoutineExerciseFormSet, RoutineForm
from apps.routines.models import Routine, RoutineRotation, Visibility


def owned(request, pk):
    return get_object_or_404(Routine, pk=pk, owner=request.user)


@login_required
def routine_list(request):
    routines = Routine.objects.filter(owner=request.user).order_by("archived", "name")
    return render(request, "routines/list.html", {"routines": routines})


@login_required
def routine_create(request):
    form = RoutineCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        routine = form.save(commit=False)
        routine.owner = request.user
        routine.save()
        return redirect("routines:edit", pk=routine.pk)
    return render(request, "routines/create.html", {"form": form})


@login_required
def routine_edit(request, pk):
    routine = owned(request, pk)
    form = RoutineForm(request.POST or None, instance=routine)
    formset = RoutineExerciseFormSet(request.POST or None, instance=routine, prefix="exercises")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        form.save()
        entries = formset.save(commit=False)
        for entry in formset.deleted_objects:
            entry.delete()  # soft delete
        for entry in entries:
            entry.save()
        messages.success(request, "Routine saved.")
        return redirect("routines:list")
    return render(
        request, "routines/edit.html", {"routine": routine, "form": form, "formset": formset}
    )


@login_required
@require_POST
def routine_delete(request, pk):
    routine = owned(request, pk)
    routine.delete()
    messages.success(request, f"Deleted {routine.name}.")
    return redirect("routines:list")


@login_required
@require_POST
def routine_archive(request, pk):
    routine = owned(request, pk)
    routine.archived = not routine.archived
    routine.save(update_fields=["archived", "updated_at"])
    if routine.archived:
        RoutineRotation.objects.filter(user=request.user, routine=routine).delete()
    return redirect("routines:list")


@login_required
def library(request):
    curated = Routine.objects.filter(visibility=Visibility.CURATED).order_by("name")
    shared = (
        Routine.objects.filter(visibility=Visibility.SHARED)
        .exclude(owner=request.user)
        .order_by("name")
    )
    return render(request, "routines/library.html", {"curated": curated, "shared": shared})


@login_required
@require_POST
def routine_clone(request, pk):
    source = get_object_or_404(
        Routine, pk=pk, visibility__in=[Visibility.CURATED, Visibility.SHARED]
    )
    clone = source.clone_for(request.user)
    messages.success(request, f"Added {clone.name} to your routines.")
    return redirect("routines:edit", pk=clone.pk)


@login_required
def rotation(request):
    entries = RoutineRotation.objects.filter(user=request.user).select_related("routine")
    in_rotation = [entry.routine_id for entry in entries]
    available = Routine.objects.filter(owner=request.user, archived=False).exclude(
        pk__in=in_rotation
    )
    return render(request, "routines/rotation.html", {"entries": entries, "available": available})


@login_required
@require_POST
def rotation_add(request):
    routine = get_object_or_404(Routine, pk=request.POST.get("routine"), owner=request.user)
    if routine.archived:
        return HttpResponseBadRequest("Archived routines cannot be added to the rotation.")
    next_position = RoutineRotation.objects.filter(user=request.user).aggregate(m=Max("position"))[
        "m"
    ]
    RoutineRotation.objects.get_or_create(
        user=request.user,
        routine=routine,
        defaults={"position": 0 if next_position is None else next_position + 1},
    )
    return redirect("routines:rotation")


@login_required
@require_POST
def rotation_remove(request):
    RoutineRotation.objects.filter(
        user=request.user, routine_id=request.POST.get("routine")
    ).delete()
    return redirect("routines:rotation")


@login_required
@require_POST
def rotation_reorder(request):
    order = request.POST.getlist("order")
    entries = {str(e.routine_id): e for e in RoutineRotation.objects.filter(user=request.user)}
    for position, routine_id in enumerate(order):
        entry = entries.get(routine_id)
        if entry and entry.position != position:
            entry.position = position
            entry.save(update_fields=["position", "updated_at"])
    return redirect("routines:rotation")
