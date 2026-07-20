from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.routines.models import DeloadPeriod

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


@pytest.fixture
def as_andy(client, andy):
    client.force_login(andy)
    return client


def test_start_deload_week_creates_period(as_andy, andy):
    resp = as_andy.post(reverse("routines:deload_start"), secure=True)
    assert resp.status_code == 302
    assert DeloadPeriod.objects.filter(user=andy).count() == 1


def test_start_deload_week_is_idempotent_while_active(as_andy, andy):
    as_andy.post(reverse("routines:deload_start"), secure=True)
    as_andy.post(reverse("routines:deload_start"), secure=True)
    # Starting again while one is active must not stack windows.
    today = timezone.localdate()
    assert DeloadPeriod.objects.filter(user=andy, end_date__gte=today).count() == 1


def test_cancel_deload_week_truncates(as_andy, andy):
    as_andy.post(reverse("routines:deload_start"), secure=True)
    resp = as_andy.post(reverse("routines:deload_cancel"), secure=True)
    assert resp.status_code == 302
    today = timezone.localdate()
    period = DeloadPeriod.objects.get(user=andy)
    # Truncated to today: today is the last deload day, tomorrow is clear.
    assert period.end_date == today
    assert DeloadPeriod.objects.active_for(andy, today=today + timedelta(days=1)) is None


def test_deload_actions_require_login(client):
    assert client.post(reverse("routines:deload_start"), secure=True).status_code == 302


def test_cannot_cancel_when_none_active(as_andy, andy):
    resp = as_andy.post(reverse("routines:deload_cancel"), secure=True)
    assert resp.status_code == 302  # no-op, no error
    assert DeloadPeriod.objects.filter(user=andy).count() == 0
