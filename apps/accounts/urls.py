from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("login/code/", views.verify_view, name="verify"),
    path("logout/", views.logout_view, name="logout"),
    path("logout/all/", views.logout_all_view, name="logout_all"),
]
