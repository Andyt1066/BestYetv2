from django.urls import path

from apps.routines import views

app_name = "routines"

urlpatterns = [
    path("", views.routine_list, name="list"),
    path("new/", views.routine_create, name="create"),
    path("library/", views.library, name="library"),
    path("rotation/", views.rotation, name="rotation"),
    path("rotation/add/", views.rotation_add, name="rotation_add"),
    path("rotation/remove/", views.rotation_remove, name="rotation_remove"),
    path("rotation/reorder/", views.rotation_reorder, name="rotation_reorder"),
    path("deload/start/", views.deload_start, name="deload_start"),
    path("deload/cancel/", views.deload_cancel, name="deload_cancel"),
    path("<uuid:pk>/edit/", views.routine_edit, name="edit"),
    path("<uuid:pk>/delete/", views.routine_delete, name="delete"),
    path("<uuid:pk>/archive/", views.routine_archive, name="archive"),
    path("<uuid:pk>/clone/", views.routine_clone, name="clone"),
]
