from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from apps.routines.deload import date_in_deload_period, start_deload_week
from apps.routines.models import DeloadPeriod

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


def test_start_deload_week_creates_seven_day_period(andy):
    today = date(2026, 7, 20)
    period = start_deload_week(andy, today=today)
    assert period.start_date == today
    assert period.end_date == today + timedelta(days=7)


def test_active_when_today_within_period(andy):
    today = date(2026, 7, 20)
    start_deload_week(andy, today=today)
    assert DeloadPeriod.objects.active_for(andy, today=today) is not None
    assert DeloadPeriod.objects.active_for(andy, today=today + timedelta(days=8)) is None


def test_cancel_truncates_end_date_to_today(andy):
    start = date(2026, 7, 20)
    period = start_deload_week(andy, today=start)
    cancel_day = start + timedelta(days=2)
    period.cancel(today=cancel_day)
    period.refresh_from_db()
    assert period.end_date == cancel_day
    assert DeloadPeriod.objects.active_for(andy, today=cancel_day + timedelta(days=1)) is None


def test_date_in_period_covers_past_and_backdated_windows(andy):
    # A historical window still counts (invariant 19).
    DeloadPeriod.objects.create(user=andy, start_date=date(2026, 1, 1), end_date=date(2026, 1, 8))
    assert date_in_deload_period(andy, date(2026, 1, 4)) is True
    assert date_in_deload_period(andy, date(2026, 1, 8)) is True  # end inclusive
    assert date_in_deload_period(andy, date(2026, 2, 1)) is False


def test_date_in_period_is_user_scoped(andy):
    robyn = User.objects.create_user(username="robyn", password="pass-2")
    DeloadPeriod.objects.create(user=robyn, start_date=date(2026, 1, 1), end_date=date(2026, 1, 8))
    assert date_in_deload_period(andy, date(2026, 1, 4)) is False
