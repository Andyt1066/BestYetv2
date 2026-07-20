"""Deload-week helpers: create/query the DeloadPeriod windows (spec §5.3).

Deload week mode changes suggestions only; it never writes targets or logs
(invariant 19).
"""

from datetime import timedelta

from apps.routines.models import DeloadPeriod

DELOAD_WEEK_DAYS = 7


def start_deload_week(user, today):
    return DeloadPeriod.objects.create(
        user=user, start_date=today, end_date=today + timedelta(days=DELOAD_WEEK_DAYS)
    )


def date_in_deload_period(user, on_date):
    """True if `on_date` falls within any of the user's deload windows (past,
    present, live or backdated). End date is inclusive."""
    return DeloadPeriod.objects.filter(
        user=user, start_date__lte=on_date, end_date__gte=on_date
    ).exists()
