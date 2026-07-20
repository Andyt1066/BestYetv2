"""The active-workout JS posts JSON with an X-CSRFToken header. Because the CSRF
cookie is HttpOnly (unreadable by JS), the token must be rendered into the DOM
for the script to read, and the endpoints must actually enforce CSRF.
"""

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.logbook.models import WorkoutSession

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def andy():
    return User.objects.create_user(username="andy", password="pass-1")


def test_active_page_renders_csrf_token_for_js(client, andy):
    client.force_login(andy)
    resp = client.get(reverse("logbook:new_freeform"), secure=True)
    assert 'name="csrf-token"' in resp.content.decode()


def test_write_endpoint_rejects_post_without_csrf_token(andy):
    # A CSRF-enforcing client (like a real browser) must be blocked without a token.
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(andy)
    resp = csrf_client.post(
        reverse("logbook:session_start"),
        data=json.dumps({"id": str(uuid.uuid4()), "started_at": timezone.now().isoformat()}),
        content_type="application/json",
        secure=True,
    )
    assert resp.status_code == 403
    assert WorkoutSession.objects.count() == 0


def test_write_endpoint_accepts_post_with_csrf_header(andy):
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(andy)
    # Prime the CSRF cookie, then send the token in the header as the JS does.
    csrf_client.get(reverse("logbook:new_freeform"), secure=True)
    token = csrf_client.cookies["csrftoken"].value
    session_id = str(uuid.uuid4())
    resp = csrf_client.post(
        reverse("logbook:session_start"),
        data=json.dumps({"id": session_id, "started_at": timezone.now().isoformat()}),
        content_type="application/json",
        secure=True,
        HTTP_X_CSRFTOKEN=token,
        # HTTPS CSRF also checks Referer against CSRF_TRUSTED_ORIGINS; a browser
        # sends this automatically, so the host's INI must pin the real origin.
        HTTP_REFERER="https://testserver/logbook/new/freeform/",
    )
    assert resp.status_code == 200
    assert WorkoutSession.objects.filter(pk=session_id).exists()
