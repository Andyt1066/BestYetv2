from copy import deepcopy

import pytest
from django.conf import settings
from django.db import connections


def test_settings_come_from_ini():
    assert settings.SECRET_KEY == "test-only-insecure-key"
    assert settings.DEBUG is False
    assert "testserver" in settings.ALLOWED_HOSTS
    assert settings.CSRF_TRUSTED_ORIGINS == ["https://testserver"]
    assert settings.ADMIN_PATH == "hidden-admin"
    assert str(settings.MEDIA_ROOT).endswith("var/test-media")


def test_database_options_configured():
    options = settings.DATABASES["default"]["OPTIONS"]
    assert options["transaction_mode"] == "IMMEDIATE"
    init_command = options["init_command"]
    assert "journal_mode=WAL" in init_command
    assert "busy_timeout=5000" in init_command
    assert "synchronous=NORMAL" in init_command
    assert "foreign_keys=ON" in init_command


@pytest.mark.django_db
def test_sqlite_connection_applies_pragmas(tmp_path):
    db_settings = deepcopy(connections.databases["default"])
    db_settings["NAME"] = str(tmp_path / "pragmas.sqlite3")
    conn = connections["default"].__class__(db_settings, alias="pragma-probe")
    try:
        with conn.cursor() as cursor:
            cursor.execute("PRAGMA journal_mode")
            assert cursor.fetchone()[0] == "wal"
            cursor.execute("PRAGMA busy_timeout")
            assert cursor.fetchone()[0] == 5000
            cursor.execute("PRAGMA synchronous")
            assert cursor.fetchone()[0] == 1  # NORMAL
            cursor.execute("PRAGMA foreign_keys")
            assert cursor.fetchone()[0] == 1
    finally:
        conn.close()
