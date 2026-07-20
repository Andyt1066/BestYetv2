from django.urls import path

from apps.logbook import views, write

app_name = "logbook"

urlpatterns = [
    path("", views.start, name="start"),
    path("new/freeform/", views.new_freeform, name="new_freeform"),
    path("new/<uuid:pk>/", views.new_from_routine, name="new"),
    path("session/<uuid:pk>/", views.active, name="active"),
    path("exercise/<uuid:pk>/history/", views.exercise_history, name="exercise_history"),
    path("api/session/start/", write.session_start, name="session_start"),
    path("api/session/<uuid:pk>/finish/", write.session_finish, name="session_finish"),
    path("api/set/", write.set_upsert, name="set_upsert"),
    path("api/set/<uuid:pk>/delete/", write.set_delete, name="set_delete"),
    path("api/set/<uuid:pk>/restore/", write.set_restore, name="set_restore"),
    path("api/cardio/", write.cardio_upsert, name="cardio_upsert"),
]
