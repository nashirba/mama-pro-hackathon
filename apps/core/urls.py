from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("city/", views.set_city, name="set_city"),
    path("mamapro/", views.mamapro, name="mamapro"),
]
