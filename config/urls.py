from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path(f"{settings.ADMIN_PATH}/", admin.site.urls),
    # Home becomes the dashboard in build-order step 4; routines until then.
    path("", RedirectView.as_view(pattern_name="routines:list"), name="home"),
    path("routines/", include("apps.routines.urls")),
    path("exercises/", include("apps.exercises.urls")),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "accounts/password-change/",
        auth_views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "accounts/password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
]
