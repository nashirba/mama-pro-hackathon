import pytest
from django.urls import resolve
from django.utils import translation


@pytest.mark.parametrize(
    "path,name",
    [
        ("/ru/login/code/", "accounts:verify"),
        ("/ru/logout/all/", "accounts:logout_all"),
        ("/ru/specialist/ivanova-logoped/", "catalog:specialist"),
        ("/ru/specialists/map.geojson", "search:map_geojson"),
        ("/ru/almaty/logoped/", "search:landing"),
        ("/ru/almaty/ras/", "search:landing"),
    ],
)
def test_landing_pattern_does_not_shadow_other_routes(path, name):
    with translation.override("ru"):
        assert resolve(path).view_name == name


def test_specialist_and_verify_pages_not_404(client, catalog_fixture):
    assert client.get("/ru/specialist/ivanova-logoped/").status_code == 200
    assert client.get("/ru/login/code/").status_code in (200, 302)
