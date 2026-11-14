from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("community/", views.feed_view, name="feed"),
    path("community/new/", views.new, name="new"),
    path("community/specialists/", views.specialist_options, name="specialist_options"),
    path("community/nickname/", views.nickname, name="nickname"),
    path("community/rules/", views.rules, name="rules"),
    path("community/<int:pk>/", views.post_detail, name="post"),
    path("community/<int:pk>/edit/", views.edit, name="edit"),
    path("community/<int:pk>/delete/", views.delete, name="delete"),
    path("community/<int:pk>/image/", views.image, name="image"),
    path("community/<int:pk>/comment/", views.comment, name="comment"),
    path("community/comment/<int:pk>/edit/", views.comment_edit, name="comment_edit"),
    path("community/comment/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
    path("community/like/<str:target>/<int:pk>/", views.like, name="like"),
    path("community/complain/<str:target>/<int:pk>/", views.complain, name="complain"),
]
