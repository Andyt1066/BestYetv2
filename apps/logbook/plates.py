"""Plate calculator and loadable-weight rounding (spec §5.3).

Pure display logic: per-side, greedy largest-first from the profile's plate
inventory. Nothing here writes a target or a log. The active-workout popover
mirrors `plate_breakdown` client-side; this module is the tested source of
truth and is reused by the warm-up generator's rounding.
"""

from decimal import Decimal

TWO = Decimal(2)


def plate_breakdown(weight, bar, inventory):
    """Per-side plate list for `weight` on `bar`, greedy from `inventory`.

    Returns a dict: achievable (bool), per_side (list of plates when exact),
    and nearest_below / nearest_above achievable total weights otherwise.
    """
    plates = sorted((Decimal(p) for p in inventory), reverse=True)
    if weight < bar:
        return {"achievable": False, "per_side": [], "nearest_below": None, "nearest_above": None}

    per_side_target = (Decimal(weight) - Decimal(bar)) / TWO
    remaining = per_side_target
    used = []
    for plate in plates:
        while remaining >= plate:
            used.append(plate)
            remaining -= plate

    if remaining == 0:
        return {"achievable": True, "per_side": used, "nearest_below": None, "nearest_above": None}

    loaded_per_side = per_side_target - remaining
    nearest_below = Decimal(bar) + TWO * loaded_per_side
    smallest = plates[-1]
    nearest_above = nearest_below + TWO * smallest
    return {
        "achievable": False,
        "per_side": [],
        "nearest_below": nearest_below,
        "nearest_above": nearest_above,
    }


def nearest_loadable(weight, bar, inventory, increment=Decimal("2.5")):
    """Round `weight` to a weight the equipment can actually make.

    With a bar, snap to the nearest plate-achievable weight; without one
    (dumbbells/other), snap to the nearest `increment` step.
    """
    weight = Decimal(weight)
    if bar is None:
        increment = Decimal(increment)
        steps = (weight / increment).quantize(Decimal(1))
        return steps * increment

    result = plate_breakdown(weight, bar, inventory)
    if result["achievable"]:
        return weight
    below, above = result["nearest_below"], result["nearest_above"]
    if below is None:
        return above
    return below if (weight - below) <= (above - weight) else above
