from apps.catalog.models import DevelopmentalCondition, SpecialistType
from apps.geo.models import KatoNode
from apps.search.query import SearchParams, search
from apps.search.suggest import suggest
from tests.factories import TrainingFactory

VISIBLE = {"aigul-nanny", "marina-nanny"}


def _slugs(response) -> set[str]:
    return {card.specialist.slug for card in response.context["result"].cards}


def test_nannies_section_shows_only_eligible_nannies(client, nannies):
    r = client.get("/ru/nannies/")
    assert r.status_code == 200 and _slugs(r) == VISIBLE
    html = r.content.decode()
    assert "Обученные няни" in html and 'data-nanny="aigul-nanny"' in html and "/ru/nanny/aigul-nanny/" in html


def test_specialists_catalog_has_no_nannies(client, nannies):
    slugs = _slugs(client.get("/ru/specialists/"))
    assert slugs and not slugs & set(nannies)
    assert not {c.specialist.slug for c in search(SearchParams(q="няня")).cards} & set(nannies)


def test_specialists_map_has_no_nannies(client, nannies):
    features = client.get("/ru/specialists/map.geojson").json()["features"]
    assert features and not {f["properties"]["specialist_slug"] for f in features} & set(nannies)


def test_nannies_section_has_no_map_and_nanny_filters(client, nannies):
    html = client.get("/ru/nannies/").content.decode()
    assert 'id="map"' not in html and "map-config" not in html and "Карта" not in html
    assert 'name="pay_units"' in html and 'name="price_hour_min"' in html and 'name="price_month_min"' in html
    assert 'name="condition_ids"' in html and 'name="language_codes"' in html and 'name="experience_min"' in html
    for absent in ('name="specialist_type_ids"', 'name="method_ids"', 'name="formats"', "data-geolocate", 'name="price_min"',
                   'name="free_only"', 'name="verification_levels"'):
        assert absent not in html, absent
    assert 'action="/ru/nannies/"' in html and 'hx-get="/ru/nannies/"' in html


def test_nannies_section_intro_lists_the_rule(client, nannies):
    html = client.get("/ru/nannies/").content.decode()
    assert "Курс первой помощи детям" in html and "Справка о несудимости" in html
    assert "не проводит коррекционных занятий" in html


def test_nanny_card_shows_prices_training_and_marks(client, nannies):
    html = client.get("/ru/nannies/").content.decode()
    assert "3\xa0000 ₸ в час" in html and "15\xa0000 ₸ за ночь" in html and "200\xa0000 ₸ в месяц" in html
    assert "112 часов" in html and "3 курса" in html
    card = html.split('data-nanny="aigul-nanny"')[1].split("</article>")[0]
    # Only fully checked nannies are listed, so a card carries one mark, not the list of checks.
    assert "Проверено Мама Про" in card and "Справка о несудимости" not in card
    assert "Алмалинский район" in html


def test_nanny_card_shows_at_most_three_conditions(client, nannies):
    card = client.get("/ru/nannies/").content.decode().split('data-nanny="aigul-nanny"')[1].split("</article>")[0]
    assert "+1" in card


def test_pay_units_filter(client, nannies):
    assert _slugs(client.get("/ru/nannies/?pay_units=night")) == {"aigul-nanny"}
    assert _slugs(client.get("/ru/nannies/?pay_units=month")) == {"marina-nanny"}
    assert _slugs(client.get("/ru/nannies/?pay_units=night&pay_units=month")) == VISIBLE
    assert _slugs(client.get("/ru/nannies/?pay_units=hour")) == VISIBLE


def test_price_hour_filter_and_sort(client, nannies):
    assert _slugs(client.get("/ru/nannies/?price_hour_max=2800")) == {"marina-nanny"}
    r = client.get("/ru/nannies/?sort=price")
    assert [c.specialist.slug for c in r.context["result"].cards] == ["marina-nanny", "aigul-nanny"]
    r = client.get("/ru/nannies/?sort=experience")
    assert [c.specialist.slug for c in r.context["result"].cards] == ["aigul-nanny", "marina-nanny"]


def test_nannies_city_and_condition_filters(client, nannies):
    assert _slugs(client.get(f"/ru/nannies/?kato_id={KatoNode.objects.get(slug='almaty').pk}")) == {"aigul-nanny"}
    down = DevelopmentalCondition.objects.get(slug="down-syndrome").pk
    assert _slugs(client.get(f"/ru/nannies/?condition_ids={down}")) == VISIBLE
    assert _slugs(client.get("/ru/nannies/?q=Айгуль")) == {"aigul-nanny"}


def test_nannies_chips(client, nannies):
    r = client.get("/ru/nannies/?pay_units=night&price_hour_min=2000")
    labels = [chip["label"] for chip in r.context["active_chips"]]
    assert "Ночью" in labels and "Цена за час: от 2\xa0000 ₸" in labels
    assert r.context["active_filter_count"] == 2
    night = next(chip for chip in r.context["active_chips"] if chip["label"] == "Ночью")
    assert night["url"] == "/ru/nannies/?price_hour_min=2000"


def test_nannies_htmx_partial_keeps_section_heading(client, nannies):
    html = client.get("/ru/nannies/?pay_units=night", HTTP_HX_REQUEST="true").content.decode()
    assert 'data-nanny="aigul-nanny"' in html and "Обученные няни" in html and "Каталог специалистов" not in html


def test_nannies_city_landing(client, nannies):
    r = client.get("/ru/almaty/nannies/")
    assert r.status_code == 200 and _slugs(r) == {"aigul-nanny"}
    assert "Обученные няни в Алматы" in r.content.decode()


def test_nannies_city_landing_kk(client, nannies):
    r = client.get("/kk/almaty/nannies/")
    assert r.status_code == 200 and "Алматыдағы оқытылған бала күтушілер" in r.content.decode()


def test_nannies_kk_page(client, nannies):
    r = client.get("/kk/nannies/")
    html = r.content.decode()
    assert r.status_code == 200 and _slugs(r) == VISIBLE
    assert "Оқытылған бала күтушілер" in html and "Обученные няни" not in html and "/kk/nanny/aigul-nanny/" in html


def test_suggest_nanny_goes_first_and_opens_the_section(db, reference):
    items = suggest("няня", "ru")
    assert items[0].kind == "nannies" and items[0].label == "Обученные няни" and items[0].url == "/ru/nannies/"
    assert suggest("бала күтуші", "kk")[0].url == "/kk/nannies/"
    assert suggest("нян", "ru", kato_id=7)[0].url == "/ru/nannies/?kato_id=7"
    assert all(s.kind != "nannies" for s in suggest("логопед", "ru"))


def test_suggest_endpoint_renders_nannies_kind(client, reference):
    html = client.get("/ru/suggest/?q=няня").content.decode()
    assert 'data-kind="nannies"' in html and 'href="/ru/nannies/"' in html


def test_adding_training_shows_nanny_in_section(client, nannies, django_capture_on_commit_callbacks):
    assert "no-first-aid-nanny" not in _slugs(client.get("/ru/nannies/"))
    with django_capture_on_commit_callbacks(execute=True):
        TrainingFactory(profile=nannies["no-first-aid-nanny"], hours=16, is_first_aid=True)
    assert "no-first-aid-nanny" in _slugs(client.get("/ru/nannies/"))


def test_deleting_first_aid_training_removes_nanny_from_section(client, nannies, django_capture_on_commit_callbacks):
    assert "aigul-nanny" in _slugs(client.get("/ru/nannies/"))
    with django_capture_on_commit_callbacks(execute=True):
        nannies["aigul-nanny"].trainings.get(is_first_aid=True).delete()
    assert "aigul-nanny" not in _slugs(client.get("/ru/nannies/"))


def test_clearing_criminal_record_removes_nanny_from_section(client, nannies, django_capture_on_commit_callbacks):
    assert "aigul-nanny" in _slugs(client.get("/ru/nannies/"))
    nanny = nannies["aigul-nanny"]
    with django_capture_on_commit_callbacks(execute=True):
        nanny.criminal_record_issued_on = None
        nanny.save()
    assert "aigul-nanny" not in _slugs(client.get("/ru/nannies/"))


def test_specialist_only_filters_are_ignored_in_nannies_section(client, nannies):
    for query in ("formats=online", "price_max=1", "free_only=1", "verification_levels=education", "near=76.9,43.25&sort=distance"):
        assert _slugs(client.get(f"/ru/nannies/?{query}")) == VISIBLE, query
    ids = [str(i) for i in SpecialistType.objects.values_list("pk", flat=True)] or ["1"]
    assert _slugs(client.get(f"/ru/nannies/?specialist_type_ids={ids[0]}&method_ids=1")) == VISIBLE
