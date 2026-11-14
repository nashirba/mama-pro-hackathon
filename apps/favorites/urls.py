from django.urls import path

from . import views

app_name = "favorites"

urlpatterns = [
    path("favorites/<slug:slug>/toggle/", views.toggle, name="toggle"),
]
