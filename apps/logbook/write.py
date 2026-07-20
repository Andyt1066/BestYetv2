"""Idempotent JSON write endpoints for the sync-ready logging models.

Every write is an upsert keyed on the client-supplied UUID (invariant 2):
replaying the same request produces exactly one row. All rows are scoped to
request.user; a UUID already owned by another user is never hijacked.
"""

import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from apps.exercises.models import Exercise
from apps.logbook.models import CardioLog, SetLog, WorkoutSession
from apps.logbook.prs import pr_check
from apps.routines.models import Routine


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _owned_by_other(model, pk, user):
    """True if `pk` exists but belongs to a different user (block hijack)."""
    row = model.all_objects.filter(pk=pk).first()
    if row is None:
        return False
    owner_id = row.user_id if hasattr(row, "user_id") else row.session.user_id
    return owner_id != user.id


def _dec(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError("Not a number") from exc


@login_required
@require_POST
def session_start(request):
    data = _payload(request)
    if data is None or "id" not in data:
        return HttpResponseBadRequest("Malformed payload")
    session_id = data["id"]
    if _owned_by_other(WorkoutSession, session_id, request.user):
        return JsonResponse({"error": "id belongs to another user"}, status=409)
    started_at = parse_datetime(data.get("started_at", "")) or timezone.now()
    routine = None
    if data.get("routine"):
        routine = get_object_or_404(
            Routine, Q(owner=request.user) | Q(visibility="curated"), pk=data["routine"]
        )
    session, _created = WorkoutSession.all_objects.get_or_create(
        pk=session_id,
        defaults={"user": request.user, "started_at": started_at, "routine": routine},
    )
    return JsonResponse({"id": str(session.pk)})


@login_required
@require_POST
def session_finish(request, pk):
    session = get_object_or_404(WorkoutSession, pk=pk, user=request.user)
    data = _payload(request) or {}
    already_finished = session.is_finished
    if not already_finished:
        session.ended_at = timezone.now()
    if "session_rpe" in data:
        try:
            session.session_rpe = _dec(data["session_rpe"])
        except ValidationError:
            return JsonResponse({"errors": {"session_rpe": ["Not a number"]}}, status=400)
    if "notes" in data:
        session.notes = data["notes"]
    session.save()
    if already_finished:
        session.mark_edited()
    return JsonResponse({"id": str(session.pk), "ended_at": session.ended_at.isoformat()})


@login_required
@require_POST
def set_upsert(request):
    data = _payload(request)
    if data is None or "id" not in data or "session" not in data:
        return HttpResponseBadRequest("Malformed payload")
    if _owned_by_other(SetLog, data["id"], request.user):
        return JsonResponse({"error": "id belongs to another user"}, status=409)
    session = get_object_or_404(WorkoutSession, pk=data["session"], user=request.user)
    exercise = get_object_or_404(Exercise, pk=data.get("exercise"))

    entry = SetLog.all_objects.filter(pk=data["id"]).first() or SetLog(pk=data["id"])
    entry.session = session
    entry.exercise = exercise
    entry.position = data.get("position", entry.position or 0)
    entry.set_type = data.get("set_type", entry.set_type or "normal")
    entry.superset_group = data.get("superset_group")
    try:
        entry.weight_kg = _dec(data.get("weight_kg"))
        entry.distance_m = _dec(data.get("distance_m"))
        entry.rpe = _dec(data.get("rpe"))
    except ValidationError:
        return JsonResponse({"errors": {"weight_kg": ["Not a number"]}}, status=400)
    entry.reps = data.get("reps")
    entry.duration_seconds = data.get("duration_seconds")
    entry.side = data.get("side", "") or ""
    entry.notes = data.get("notes", "")
    if data.get("completed_at"):
        entry.completed_at = parse_datetime(data["completed_at"]) or timezone.now()
    entry.deleted_at = None  # a re-completed set is live again

    try:
        entry.full_clean(exclude=["_load_type"])
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)
    entry.save()

    if session.is_finished:
        session.mark_edited()
    return JsonResponse({"id": str(entry.pk), "pr": pr_check(entry)})


@login_required
@require_POST
def set_delete(request, pk):
    # Scoped to the owner: another user's set (or a missing one) is a 404, and
    # a replayed delete of an already-deleted set is a no-op (idempotent).
    entry = get_object_or_404(SetLog.all_objects, pk=pk, session__user=request.user)
    if entry.deleted_at is None:
        entry.delete()
        if entry.session.is_finished:
            entry.session.mark_edited()
    return JsonResponse({"id": str(pk)})


@login_required
@require_POST
def set_restore(request, pk):
    entry = get_object_or_404(SetLog.all_objects, pk=pk, session__user=request.user)
    if entry.deleted_at is not None:
        entry.restore()
        if entry.session.is_finished:
            entry.session.mark_edited()
    return JsonResponse({"id": str(pk)})


@login_required
@require_POST
def cardio_upsert(request):
    data = _payload(request)
    if data is None or "id" not in data:
        return HttpResponseBadRequest("Malformed payload")
    if _owned_by_other(CardioLog, data["id"], request.user):
        return JsonResponse({"error": "id belongs to another user"}, status=409)
    session = None
    if data.get("session"):
        session = get_object_or_404(WorkoutSession, pk=data["session"], user=request.user)

    entry = CardioLog.all_objects.filter(pk=data["id"]).first() or CardioLog(pk=data["id"])
    entry.user = request.user
    entry.session = session
    entry.activity = data.get("activity", entry.activity or "other")
    entry.duration_seconds = data.get("duration_seconds")
    try:
        entry.distance_m = _dec(data.get("distance_m"))
    except ValidationError:
        return JsonResponse({"errors": {"distance_m": ["Not a number"]}}, status=400)
    if data.get("performed_at"):
        entry.performed_at = parse_datetime(data["performed_at"]) or timezone.now()
    elif entry.performed_at is None:
        entry.performed_at = timezone.now()
    entry.notes = data.get("notes", "")
    entry.deleted_at = None

    try:
        entry.full_clean()
    except ValidationError as exc:
        return JsonResponse({"errors": exc.message_dict}, status=400)
    entry.save()
    return JsonResponse({"id": str(entry.pk)})
