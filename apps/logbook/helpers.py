"""Read-only helper endpoints: plate breakdown and warm-up ramp.

Both are display aids that write nothing (invariants 11 and 16). The warm-up
response is a set of scaffold specs the client renders as (unpersisted) rows.
"""

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404

from apps.exercises.models import Exercise
from apps.logbook.plates import plate_breakdown
from apps.logbook.warmups import generate_warmups


def _weight(request):
    try:
        return Decimal(request.GET.get("weight", ""))
    except InvalidOperation:
        return None


@login_required
def plates(request):
    exercise = get_object_or_404(Exercise, pk=request.GET.get("exercise"))
    weight = _weight(request)
    if exercise.bar_weight_kg is None or weight is None:
        return HttpResponseBadRequest("Plate calculator needs a barbell exercise and a weight")
    inventory = request.user.profile.plate_inventory
    result = plate_breakdown(weight, exercise.bar_weight_kg, inventory)
    return JsonResponse(
        {
            "achievable": result["achievable"],
            "per_side": [_num(p) for p in result["per_side"]],
            "nearest_below": _opt_str(result["nearest_below"]),
            "nearest_above": _opt_str(result["nearest_above"]),
        }
    )


@login_required
def warmups(request):
    exercise = get_object_or_404(Exercise, pk=request.GET.get("exercise"))
    weight = _weight(request)
    if weight is None:
        return HttpResponseBadRequest("A working weight is required")
    inventory = request.user.profile.plate_inventory
    sets = generate_warmups(weight, exercise.bar_weight_kg, inventory)
    return JsonResponse(
        {
            "sets": [
                {"weight": _num(s["weight"]), "reps": s["reps"], "set_type": "warmup"} for s in sets
            ]
        }
    )


def _num(value):
    """Decimal to a trimmed string: 20.00 -> "20", 1.25 -> "1.25"."""
    normalized = Decimal(value).normalize()
    # normalize() gives 2E+1 for 20; expand it back to plain notation.
    return f"{normalized:f}"


def _opt_str(value):
    return _num(value) if value is not None else None
