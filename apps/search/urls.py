from django.urls import path

from . import views

app_name = "search"

# `landing` must stay the last pattern: it matches any two-segment path and 404s on unknown ones.
urlpatterns = [
    path("specialists/", views.results, name="results"),
    path("specialists/map.geojson", views.map_geojson, name="map_geojson"),
    path("nannies/", views.nannies, name="nannies"),
    path("suggest/", views.suggest, name="suggest"),
    path("<slug:city_slug>/<slug:slug>/", views.landing, name="landing"),
]
