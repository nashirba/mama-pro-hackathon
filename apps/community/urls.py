from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("community/", views.feed_view, name="feed"),
    path("community/nickname/", views.nickname, name="nickname"),
    path("community/rules/", views.rules, name="rules"),
    path("community/<int:pk>/", views.post_detail, name="post"),
    path("community/<int:pk>/image/", views.image, name="image"),
]
