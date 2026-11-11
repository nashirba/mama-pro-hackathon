import json
import re

from apps.search.geojson import feature_collection

GEOJSON_QUERY_BUDGET = 2  # the offers query (+ one spare); must not grow with the number of features


def features(client, qs=""):
    return client.get("/ru/specialists/map.geojson" + qs).json()["features"]


def json_script(html, element_id):
    return json.loads(re.search(rf'<script id="{element_id}" type="application/json">(.*?)</script>', html, re.DOTALL).group(1))


def test_geojson_lon_lat_order_and_count(client, catalog_fixture):
    fs = features(client)
    assert len(fs) == 5  # almaly, medeu, esil, karaganda, saryarka
    for f in fs:
        lon, lat = f["geometry"]["coordinates"]
        assert 46 < lon < 88 and 40 < lat < 56


def test_geojson_properties(client, catalog_fixture):
    f = next(f for f in features(client) if f["properties"]["specialist_slug"] == "ivanova-logoped")
    assert f["geometry"]["coordinates"] == [76.91, 43.251]
    assert f["properties"]["name"] == "Иванова Анна" and f["properties"]["price_from"] == 8000
    assert f["properties"]["url"].endswith("/ru/specialist/ivanova-logoped/")
    assert f["properties"]["two_gis_url"].startswith("https://2gis.kz/almaty/geo/")
    free = next(f for f in features(client) if f["properties"]["specialist_slug"] == "sergeev-free")
    assert free["properties"]["is_free"] is True


def test_geojson_respects_filters(client, catalog_fixture):
    astana = catalog_fixture.kato["astana"].id
    assert {f["properties"]["specialist_slug"] for f in features(client, f"?kato_id={astana}")} == {"kim-neuro", "sergeev-free"}


def test_geojson_district_overrides_city(client, catalog_fixture):
    almaty, esil = catalog_fixture.kato["almaty"].id, catalog_fixture.kato["esilskiy"].id
    qs = f"?kato_id={almaty}&district_id={esil}"
    assert {f["properties"]["specialist_slug"] for f in features(client, qs)} == {"kim-neuro"}


def test_geojson_ignores_empty_params(client, catalog_fixture):
    assert len(features(client, "?q=&kato_id=&price_min=&sort=relevance")) == 5


def test_geojson_excludes_online_only_and_home_visit(client, catalog_fixture):
    slugs = {f["properties"]["specialist_slug"] for f in features(client)}
    assert "nurlan-online" not in slugs and "omarova-home" not in slugs and "hidden-logoped" not in slugs


def test_geojson_limit(client, catalog_fixture, settings):
    settings.GEOJSON_MAX_FEATURES = 2
    assert len(features(client)) == 2


def test_geojson_query_count_is_constant(client, catalog_fixture, django_assert_max_num_queries):
    with django_assert_max_num_queries(GEOJSON_QUERY_BUDGET):
        assert len(features(client)) == 5


def test_feature_collection_one_marker_per_specialist_and_address(catalog_fixture):
    from apps.search.geojson import map_offers
    from apps.search.models import SearchOffer

    offers = list(map_offers(SearchOffer.objects.all()))
    collection = feature_collection(offers + offers, limit=100)  # duplicated offers collapse into the same markers
    assert len(collection["features"]) == 5


def test_results_page_has_map_container_and_maplibre(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    assert 'id="map"' in html and "maplibre-gl@4.7.1" in html and "mapgl.2gis.com" not in html


def test_map_config_defaults_to_kazakhstan(client, catalog_fixture):
    cfg = json_script(client.get("/ru/specialists/").content.decode(), "map-config")
    assert cfg["center"] == [66.9, 48.0] and cfg["zoom"] == 4 and cfg["geojsonUrl"] == "/ru/specialists/map.geojson"


def test_map_config_centers_on_selected_city_and_carries_filters(client, catalog_fixture):
    astana = catalog_fixture.kato["astana"]
    cfg = json_script(client.get(f"/ru/specialists/?kato_id={astana.id}&price_min=").content.decode(), "map-config")
    assert cfg["center"] == [71.4491, 51.1694] and cfg["zoom"] == 11
    assert cfg["geojsonUrl"] == f"/ru/specialists/map.geojson?kato_id={astana.id}"


def test_map_config_district_wins_over_city(client, catalog_fixture):
    almaty, esil = catalog_fixture.kato["almaty"].id, catalog_fixture.kato["esilskiy"].id
    cfg = json_script(client.get(f"/ru/specialists/?kato_id={almaty}&district_id={esil}").content.decode(), "map-config")
    assert cfg["center"] == [71.43, 51.13] and cfg["zoom"] == 12


def test_map_config_on_landing_page(client, catalog_fixture):
    cfg = json_script(client.get("/ru/almaty/logoped/").content.decode(), "map-config")
    assert cfg["center"] == [76.9286, 43.2567] and "specialist_type_ids=" in cfg["geojsonUrl"]


def test_map_config_numbers_are_not_localized_in_kk(client, catalog_fixture):
    astana = catalog_fixture.kato["astana"]
    html = client.get(f"/kk/specialists/?kato_id={astana.id}").content.decode()
    assert '"center": [71.4491, 51.1694]' in html and '"zoom": 11' in html
    assert json_script(html, "map-config")["geojsonUrl"].startswith("/kk/specialists/map.geojson")


def test_htmx_swap_carries_map_config(client, catalog_fixture):
    astana = catalog_fixture.kato["astana"]
    html = client.get(f"/ru/specialists/?kato_id={astana.id}", headers={"HX-Request": "true"}).content.decode()
    assert json_script(html, "map-config")["center"] == [71.4491, 51.1694] and 'id="map"' not in html


def test_map_popup_labels_are_translated(client, catalog_fixture):
    labels = json_script(client.get("/kk/specialists/").content.decode(), "map-labels")
    assert labels["from"].count("__PRICE__") == 1 and all(labels.values())
    assert labels["details"] != json_script(client.get("/ru/specialists/").content.decode(), "map-labels")["details"]


def test_results_page_has_no_inline_map_init_only_static_script(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    inline = [body for body in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S) if body.strip()]
    assert not [body for body in inline if "kamqorMap" in body or "maplibregl" in body]
    assert html.count("js/map/results.js") == 1 and html.count('id="map-config"') == 1


def test_popup_label_for_price_on_request(client, catalog_fixture):
    labels = json_script(client.get("/ru/specialists/").content.decode(), "map-labels")
    assert labels["onRequest"] == "цена по запросу"
    assert json_script(client.get("/kk/specialists/").content.decode(), "map-labels")["onRequest"] != "цена по запросу"
