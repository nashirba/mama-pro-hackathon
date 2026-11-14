from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("specialist/<slug:slug>/", views.specialist_detail, name="specialist"),
    path("nanny/<slug:slug>/", views.nanny_detail, name="nanny"),
]
