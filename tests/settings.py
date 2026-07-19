"""Test settings: pin BESTYET_CONFIG to the test INI, then reuse real settings."""

import os
from pathlib import Path

os.environ.setdefault("BESTYET_CONFIG", str(Path(__file__).parent / "bestyet.test.ini"))

from config.settings import *  # noqa: E402, F403

# No collectstatic manifest exists in test runs; use the plain storage and
# serve straight from the finders instead of scanning STATIC_ROOT.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_AUTOREFRESH = True
