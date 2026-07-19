import pytest
from django.contrib.auth import get_user_model

from apps.exercises.models import Exercise

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client_(client):
    user = get_user_model().objects.create_superuser(username="root", password="admin-pass-1")
    client.force_login(user)
    return client


def test_exercise_changelist_supports_curation(admin_client_):
    Exercise.objects.create(name="Barbell Squat", slug="barbell-squat", source="seed")
    response = admin_client_.get("/hidden-admin/exercises/exercise/", secure=True)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Barbell Squat" in content
    # Curation happens in the list view: inline-editable active flag plus filters.
    assert 'name="_save"' in content
    assert "By active" in content
    assert "By source" in content


def test_musclegroup_registered(admin_client_):
    response = admin_client_.get("/hidden-admin/exercises/musclegroup/", secure=True)
    assert response.status_code == 200
