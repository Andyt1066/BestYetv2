import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch, reverse

User = get_user_model()


def test_secure_cookie_settings():
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.CSRF_COOKIE_HTTPONLY is True
    assert settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_axes_installed_and_wired():
    assert "axes" in settings.INSTALLED_APPS
    assert settings.AUTHENTICATION_BACKENDS[0] == "axes.backends.AxesStandaloneBackend"
    assert "axes.middleware.AxesMiddleware" in settings.MIDDLEWARE


def test_admin_mounted_on_ini_path(client):
    response = client.get("/hidden-admin/", secure=True)
    assert response.status_code == 302  # redirect to admin login
    assert client.get("/admin/", secure=True).status_code == 404


@pytest.mark.django_db
def test_login_view_renders(client):
    response = client.get(reverse("login"), secure=True)
    assert response.status_code == 200


def test_no_signup_route_exists(client):
    with pytest.raises(NoReverseMatch):
        reverse("signup")
    assert client.get("/accounts/signup/", secure=True).status_code == 404


@pytest.mark.django_db
def test_repeated_login_failures_lock_out(client):
    User.objects.create_user(username="andy", password="correct-horse-1")
    for _ in range(settings.AXES_FAILURE_LIMIT):
        client.post(
            reverse("login"),
            {"username": "andy", "password": "wrong"},
            secure=True,
        )
    # Even the correct password is now rejected with the lockout status.
    response = client.post(
        reverse("login"),
        {"username": "andy", "password": "correct-horse-1"},
        secure=True,
    )
    assert response.status_code == 429
