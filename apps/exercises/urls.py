from django.urls import path

from apps.exercises import views

app_name = "exercises"

urlpatterns = [
    path("picker/", views.picker, name="picker"),
]
