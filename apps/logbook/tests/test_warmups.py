from decimal import Decimal

from apps.logbook.warmups import generate_warmups

INV = [Decimal(x) for x in ("25", "20", "15", "10", "5", "2.5", "1.25")]


def D(x):
    return Decimal(str(x))


def test_barbell_warmups_start_with_empty_bar():
    sets = generate_warmups(working_weight=D(100), bar=D(20), inventory=INV)
    assert sets[0]["weight"] == D(20)
    assert sets[0]["reps"] == 10


def test_percentage_ramp_rounded_to_loadable():
    sets = generate_warmups(working_weight=D(100), bar=D(20), inventory=INV)
    weights = [s["weight"] for s in sets]
    # empty bar, then ~40/60/80% of 100 rounded to loadable plates
    assert D(20) in weights
    assert D(40) in weights  # 40%
    assert D(60) in weights  # 60%
    assert D(80) in weights  # 80%
    # reps taper down the ramp
    assert [s["reps"] for s in sets] == [10, 8, 5, 3]


def test_steps_at_or_below_bar_are_skipped():
    # Light working weight: 40% of 30 = 12 < 20 bar, so that step drops out.
    sets = generate_warmups(working_weight=D(30), bar=D(20), inventory=INV)
    assert all(s["weight"] >= D(20) for s in sets)
    # No duplicate weights either.
    weights = [s["weight"] for s in sets]
    assert len(weights) == len(set(weights))


def test_non_barbell_has_no_empty_bar_step_and_uses_increment():
    sets = generate_warmups(working_weight=D(40), bar=None, inventory=INV, increment=D("2.5"))
    # No empty-bar row; weights rounded to the increment.
    assert all(s["weight"] % D("2.5") == 0 for s in sets)
    assert sets[0]["reps"] >= sets[-1]["reps"]


def test_all_generated_sets_are_warmup_type():
    sets = generate_warmups(working_weight=D(100), bar=D(20), inventory=INV)
    assert all(s["set_type"] == "warmup" for s in sets)
