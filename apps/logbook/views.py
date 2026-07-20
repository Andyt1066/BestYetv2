import uuid

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.exercises.models import Exercise
from apps.logbook.models import SetLog, SetType, WorkoutSession
from apps.logbook.prs import epley_e1rm
from apps.logbook.scaffold import build_scaffold
from apps.routines.models import DeloadPeriod, Routine


@login_required
def start(request):
    routines = Routine.objects.filter(owner=request.user, archived=False).order_by("name")
    unfinished = WorkoutSession.objects.filter(user=request.user, ended_at__isnull=True).order_by(
        "-started_at"
    )
    deload = DeloadPeriod.objects.active_for(request.user, today=timezone.localdate())
    return render(
        request,
        "logbook/start.html",
        {"routines": routines, "unfinished": unfinished, "deload": deload},
    )


def _visible_routine(request, pk):
    return get_object_or_404(Routine, Q(owner=request.user) | Q(visibility="curated"), pk=pk)


@login_required
def new_from_routine(request, pk):
    routine = _visible_routine(request, pk)
    blocks = build_scaffold(request.user, routine)
    return render(
        request,
        "logbook/active.html",
        {
            "session_id": uuid.uuid4(),
            "routine": routine,
            "blocks": blocks,
            "logged_sets": [],
            "new_session": True,
        },
    )


@login_required
def new_freeform(request):
    return render(
        request,
        "logbook/active.html",
        {
            "session_id": uuid.uuid4(),
            "routine": None,
            "blocks": [],
            "logged_sets": [],
            "new_session": True,
        },
    )


@login_required
def new_backdated(request):
    # "Log past session": the active screen with a date/time picker and the
    # rest timer disabled (invariant 16). Validation lives in the model.
    return render(
        request,
        "logbook/active.html",
        {
            "session_id": uuid.uuid4(),
            "routine": None,
            "blocks": [],
            "logged_sets": [],
            "new_session": True,
            "backdated": True,
        },
    )


@login_required
def active(request, pk):
    session = get_object_or_404(WorkoutSession, pk=pk, user=request.user)
    blocks = build_scaffold(request.user, session.routine, session=session)
    scaffold_ids = {block.exercise.pk for block in blocks}
    # Sets whose exercise isn't in the routine scaffold (freeform, swaps, extras)
    # are rendered as their own logged blocks.
    logged_blocks = _group_logged_sets(session, exclude=scaffold_ids)
    return render(
        request,
        "logbook/active.html",
        {
            "session_id": session.pk,
            "session": session,
            "routine": session.routine,
            "blocks": blocks,
            "logged_blocks": logged_blocks,
            "new_session": False,
        },
    )


def _group_logged_sets(session, exclude):
    grouped = {}
    for entry in session.sets.select_related("exercise").order_by("position", "completed_at"):
        if entry.exercise.pk in exclude:
            continue
        grouped.setdefault(entry.exercise, []).append(entry)
    return [{"exercise": exercise, "sets": sets} for exercise, sets in grouped.items()]


@login_required
def exercise_history(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    sets = (
        SetLog.objects.filter(session__user=request.user, exercise=exercise)
        .exclude(set_type=SetType.WARMUP)
        .select_related("session")
        .order_by("-completed_at")[:20]
    )
    rows = [
        {
            "date": s.session.started_at,
            "weight_kg": s.weight_kg,
            "reps": s.reps,
            "e1rm": epley_e1rm(s.weight_kg, s.reps),
        }
        for s in sets
    ]
    return render(
        request,
        "logbook/partials/_history_sheet.html",
        {"exercise": exercise, "rows": rows},
    )
