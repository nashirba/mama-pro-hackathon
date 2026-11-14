from django.urls import path

from . import views

app_name = "cabinet"

urlpatterns = [
    path("cabinet/", views.home, name="home"),
    path("cabinet/edit/", views.profile_edit, name="profile_edit"),
]
