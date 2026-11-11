from apps.catalog.models import SpecialistType
from apps.search.suggest import suggest


def test_suggest_synonym_returns_condition(client, catalog_fixture):
    html = client.get("/ru/suggest/?q=аутизм").content.decode()
    assert 'data-kind="condition"' in html and "РАС" in html


def test_suggest_kk_page_returns_type_in_kk_label(client, catalog_fixture):
    html = client.get("/kk/suggest/?q=логопед").content.decode()
    t = SpecialistType.objects.get(slug="logoped")
    assert 'data-kind="type"' in html and f"specialist_type_ids={t.id}" in html and "Логопед" in html


def test_suggest_finds_method(client, catalog_fixture):
    assert 'data-kind="method"' in client.get("/ru/suggest/?q=томатис").content.decode()


def test_suggest_kk_letters_normalized(client, catalog_fixture):
    assert 'data-kind="condition"' in client.get("/kk/suggest/?q=аутистикалык").content.decode()   # без специальных букв


def test_suggest_short_query_is_empty(client, catalog_fixture):
    r = client.get("/ru/suggest/?q=а")
    assert r.status_code == 200 and "<li" not in r.content.decode()


def test_suggest_latin_method_synonym(client, catalog_fixture):
    assert 'data-kind="method"' in client.get("/ru/suggest/?q=ABA").content.decode()


def test_suggest_urls_and_prefix_follow_language(catalog_fixture):
    t = SpecialistType.objects.get(slug="logoped")
    items = suggest("логопед", "kk")
    assert [i.kind for i in items][0] == "type"
    assert next(i.url for i in items if i.slug == "logoped") == f"/kk/specialists/?specialist_type_ids={t.id}"


def test_suggest_respects_limit(catalog_fixture):
    assert len(suggest("те", "ru", limit=100)) > 2   # the query matches more rows than the limit below
    assert len(suggest("те", "ru", limit=2)) == 2


def test_suggest_keeps_chosen_city(client, catalog_fixture):
    almaty = catalog_fixture.kato["almaty"].id
    t = SpecialistType.objects.get(slug="logoped")
    html = client.get(f"/ru/suggest/?q=логопед&kato_id={almaty}").content.decode()
    assert f"specialist_type_ids={t.id}&amp;kato_id={almaty}" in html
    assert "kato_id" not in client.get("/ru/suggest/?q=логопед").content.decode()
    assert "kato_id" not in client.get("/ru/suggest/?q=логопед&kato_id=abc").content.decode()


def test_suggest_escapes_query_and_wildcards(client, catalog_fixture):
    r = client.get("/ru/suggest/?q=<script>alert(1)</script>")
    assert r.status_code == 200 and "<script>" not in r.content.decode()
    assert "<li" not in client.get("/ru/suggest/?q=%25%25").content.decode()   # % is not a LIKE wildcard


def test_suggest_without_hx_header_returns_fragment(client, catalog_fixture):
    html = client.get("/ru/suggest/?q=логопед").content.decode()
    assert html.lstrip().startswith("<ul") and "<html" not in html
