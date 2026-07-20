from decimal import Decimal

from apps.logbook.plates import nearest_loadable, plate_breakdown

INV = [Decimal(x) for x in ("25", "20", "15", "10", "5", "2.5", "1.25")]


def D(x):
    return Decimal(str(x))


def test_exact_breakdown_per_side():
    # 100 kg on a 20 kg bar = 40 kg per side = 25 + 15
    result = plate_breakdown(D(100), D(20), INV)
    assert result["achievable"] is True
    assert result["per_side"] == [D(25), D(15)]


def test_greedy_largest_first():
    # 60 kg, 20 bar => 20 per side => 20
    assert plate_breakdown(D(60), D(20), INV)["per_side"] == [D(20)]
    # 62.5 => 21.25 per side => 20 + 1.25
    assert plate_breakdown(D("62.5"), D(20), INV)["per_side"] == [D(20), D("1.25")]


def test_bar_only():
    result = plate_breakdown(D(20), D(20), INV)
    assert result["achievable"] is True
    assert result["per_side"] == []


def test_weight_below_bar_is_not_achievable():
    result = plate_breakdown(D(15), D(20), INV)
    assert result["achievable"] is False


def test_unachievable_weight_reports_nearest_either_side():
    # 61 kg => 20.5 per side; inventory can't hit 0.5 alone at this point.
    result = plate_breakdown(D(61), D(20), INV)
    assert result["achievable"] is False
    assert result["nearest_below"] == D(60)
    assert result["nearest_above"] == D("62.5")


def test_nearest_loadable_rounds_to_inventory():
    assert nearest_loadable(D(61), D(20), INV) == D(60)
    assert nearest_loadable(D(62), D(20), INV) == D("62.5")


def test_nearest_loadable_without_bar_uses_increment():
    # No bar (dumbbell/other): round to the increment step.
    assert nearest_loadable(D(37), None, INV, increment=D("2.5")) == D("37.5")
    assert nearest_loadable(D(36), None, INV, increment=D("2.5")) == D(35)
