from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("healthz", core_views.healthz, name="healthz"),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("i18n/setlang/", core_views.set_language, name="set_language"),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.questionnaire.urls")),
    path("", include("apps.community.urls")),
    path("", include("apps.cabinet.urls")),
    path("", include("apps.onboarding.urls")),
    path("", include("apps.favorites.urls")),
    path("", include("apps.search.urls")),  # last: its landing pattern matches any two-segment path
    prefix_default_language=True,
)
