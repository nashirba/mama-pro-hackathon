from django.urls import path

from . import views

app_name = "onboarding"

urlpatterns = [
    path("cabinet/application/", views.edit, name="edit"),
    path("cabinet/application/submit/", views.submit, name="submit"),
    path("cabinet/application/documents/add/", views.document_add, name="document_add"),
    path("cabinet/application/documents/<int:pk>/", views.document_file, name="document_file"),
    path("cabinet/application/documents/<int:pk>/delete/", views.document_delete, name="document_delete"),
    path("cabinet/application/courses/add/", views.course_add, name="course_add"),
    path("cabinet/application/courses/<int:pk>/delete/", views.course_delete, name="course_delete"),
]
