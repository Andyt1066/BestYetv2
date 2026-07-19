from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Profile

User = get_user_model()

pytestmark = pytest.mark.django_db


def make_user(username="andy"):
    return User.objects.create_user(username=username, password="irrelevant-pass-1")


def test_profile_created_automatically_with_new_user():
    user = make_user()
    assert Profile.objects.filter(user=user).exists()


def test_profile_defaults_match_spec():
    profile = make_user().profile
    assert profile.preferred_units == "kg"
    assert profile.bodyweight_unit == "kg"
    assert profile.bodyweight_goal_kg is None
    assert profile.share_history is False
    assert profile.plate_inventory == [25, 20, 15, 10, 5, 2.5, 1.25]
    assert profile.deload_after_failures == 3
    assert profile.deload_percent == Decimal("10")
    assert profile.deload_week_percent == Decimal("50")
    assert profile.sex == ""  # unset; excludes the user from DOTS boards


def test_display_name_defaults_to_username():
    profile = make_user(username="robyn").profile
    assert profile.display_name == "robyn"


def test_pseudonym_generated_and_unique():
    a = make_user("andy").profile
    b = make_user("robyn").profile
    assert a.pseudonym
    assert b.pseudonym
    assert a.pseudonym != b.pseudonym


def test_pseudonym_is_stable_across_saves():
    profile = make_user().profile
    original = profile.pseudonym
    profile.save()
    profile.refresh_from_db()
    assert profile.pseudonym == original


def test_regenerate_pseudonym_changes_and_persists():
    profile = make_user().profile
    original = profile.pseudonym
    profile.regenerate_pseudonym()
    profile.refresh_from_db()
    assert profile.pseudonym != original
    assert profile.pseudonym


def test_timestamps_maintained_automatically():
    profile = make_user().profile
    assert profile.created_at is not None
    first_updated = profile.updated_at
    profile.display_name = "Andy T"
    profile.save()
    profile.refresh_from_db()
    assert profile.updated_at > first_updated


def test_saving_second_user_cannot_collide_on_pseudonym(monkeypatch):
    # Force the generator to emit a duplicate first, proving the retry loop.
    from apps.accounts import pseudonyms

    a = make_user("andy").profile
    candidates = iter([a.pseudonym, "unique-handle-99"])
    monkeypatch.setattr(pseudonyms, "generate_candidate", lambda: next(candidates))
    b = make_user("robyn").profile
    assert b.pseudonym == "unique-handle-99"
