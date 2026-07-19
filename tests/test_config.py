import pytest
from django.core.exceptions import ImproperlyConfigured

from config.ini import load_config


def write_ini(tmp_path, body):
    path = tmp_path / "bestyet.ini"
    path.write_text(body)
    return path


MINIMAL = """
[django]
secret_key = abc123

[paths]
db = /data/bestyet.sqlite3
media = /data/media
"""


def test_missing_file_raises(tmp_path):
    with pytest.raises(ImproperlyConfigured):
        load_config(tmp_path / "does-not-exist.ini")


def test_missing_secret_key_raises(tmp_path):
    path = write_ini(tmp_path, "[django]\n\n[paths]\ndb = /d/db\nmedia = /d/m\n")
    with pytest.raises(ImproperlyConfigured):
        load_config(path)


def test_missing_paths_raise(tmp_path):
    path = write_ini(tmp_path, "[django]\nsecret_key = abc\n")
    with pytest.raises(ImproperlyConfigured):
        load_config(path)


def test_minimal_config_defaults(tmp_path):
    cfg = load_config(write_ini(tmp_path, MINIMAL))
    assert cfg.secret_key == "abc123"
    assert cfg.debug is False
    assert cfg.allowed_hosts == []
    assert cfg.csrf_trusted_origins == []
    assert cfg.admin_path == "admin"
    assert str(cfg.db_path) == "/data/bestyet.sqlite3"
    assert str(cfg.media_root) == "/data/media"


def test_full_config_parsed(tmp_path):
    body = """
[django]
secret_key = abc123
debug = true
allowed_hosts = bestyet.example.com, www.bestyet.example.com
csrf_trusted_origins = https://bestyet.example.com
admin_path = secret-admin

[paths]
db = /data/bestyet.sqlite3
media = /data/media
"""
    cfg = load_config(write_ini(tmp_path, body))
    assert cfg.debug is True
    assert cfg.allowed_hosts == ["bestyet.example.com", "www.bestyet.example.com"]
    assert cfg.csrf_trusted_origins == ["https://bestyet.example.com"]
    assert cfg.admin_path == "secret-admin"


def test_relative_paths_resolved_against_base_dir(tmp_path):
    body = """
[django]
secret_key = abc123

[paths]
db = var/test.sqlite3
media = var/media
"""
    cfg = load_config(write_ini(tmp_path, body))
    assert cfg.db_path.is_absolute()
    assert cfg.media_root.is_absolute()
