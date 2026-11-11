def test_test_settings_selected(settings):
    assert settings.DEPLOY_PROFILE == "test"
    assert settings.DATABASES["default"]["ENGINE"] == "django.contrib.gis.db.backends.postgis"
