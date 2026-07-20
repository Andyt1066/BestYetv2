"""Warm-up ramp generator (spec §5.3).

Builds scaffold-only warm-up sets from the first working weight: empty bar x10
(barbell only), then ~40% x8, 60% x5, 80% x3, each rounded to a loadable
weight, skipping steps at or below the bar or duplicating a prior step.
Percentages and reps are v1 conventions. Output is scaffold, never persisted
until ticked (invariant 16).
"""

from decimal import Decimal

from apps.logbook.plates import nearest_loadable

# (fraction of working weight, reps). Conventions, stated not universal.
RAMP = [(Decimal("0.40"), 8), (Decimal("0.60"), 5), (Decimal("0.80"), 3)]
EMPTY_BAR_REPS = 10


def generate_warmups(working_weight, bar, inventory, increment=Decimal("2.5")):
    working_weight = Decimal(working_weight)
    sets = []
    seen = set()

    if bar is not None:
        sets.append({"weight": Decimal(bar), "reps": EMPTY_BAR_REPS, "set_type": "warmup"})
        seen.add(Decimal(bar))

    floor = Decimal(bar) if bar is not None else Decimal(0)
    for fraction, reps in RAMP:
        weight = nearest_loadable(working_weight * fraction, bar, inventory, increment)
        if weight is None or weight <= floor or weight >= working_weight or weight in seen:
            continue
        seen.add(weight)
        sets.append({"weight": weight, "reps": reps, "set_type": "warmup"})

    return sets
