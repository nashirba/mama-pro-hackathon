import json
import re


def geojson_of(html):
    return json.loads(re.search(r'<script id="specialist-geojson" type="application/json">(.*?)</script>', html, re.DOTALL).group(1))


def test_specialist_page_has_minimap_with_own_points(client, catalog_fixture):
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert 'id="specialist-map"' in html and "maplibre-gl@4.7.1" in html
    assert [f["geometry"]["coordinates"] for f in geojson_of(html)["features"]] == [[76.91, 43.251]]


def test_minimap_only_addresses_not_online(client, catalog_fixture):
    html = client.get("/ru/specialist/serikov-aba/").content.decode()
    assert len(geojson_of(html)["features"]) == 1  # medeu; online rows have no point


def test_no_minimap_without_address(client, catalog_fixture):
    html = client.get("/ru/specialist/nurlan-online/").content.decode()
    assert 'id="specialist-map"' not in html and "maplibre-gl" not in html


def test_no_minimap_for_home_visit_only(client, catalog_fixture):
    assert 'id="specialist-map"' not in client.get("/ru/specialist/omarova-home/").content.decode()


def test_minimap_coordinates_are_not_localized_in_kk(client, catalog_fixture):
    html = client.get("/kk/specialist/ivanova-logoped/").content.decode()
    assert "[76.91, 43.251]" in html
