from django.urls import path

from . import views

app_name = "cabinet"

urlpatterns = [
    path("cabinet/", views.home, name="home"),
    path("cabinet/edit/", views.profile_edit, name="profile_edit"),
    path("cabinet/phone/", views.phone_change, name="phone_change"),
    path("cabinet/phone/code/", views.phone_change_verify, name="phone_change_verify"),
    path("cabinet/children/add/", views.child_add, name="child_add"),
    path("cabinet/children/<int:pk>/edit/", views.child_edit, name="child_edit"),
    path(
        "cabinet/children/<int:pk>/delete/", views.child_delete, name="child_delete"
    ),
]
