from django.urls import path

from . import views

app_name = "questionnaire"

urlpatterns = [
    path("questionnaire/", views.questionnaire, name="questionnaire"),
    path("questionnaire/result/", views.result, name="result"),
]
