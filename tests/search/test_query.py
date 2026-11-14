from django.utils import translation

from apps.catalog.models import DevelopmentalCondition, Method, SpecialistType
from apps.search.query import SearchParams, search


def slugs(result):
    return [c.specialist.slug for c in result.cards]


def test_filter_city_includes_districts(catalog_fixture):
    k = catalog_fixture.kato
    assert slugs(search(SearchParams(kato_id=k["almaty"].id))) == ["ivanova-logoped", "serikov-aba", "omarova-home"]
    assert slugs(search(SearchParams(kato_id=k["almalinskiy"].id))) == ["ivanova-logoped"]   # the home-visit area almaty does not reach the district


def test_city_filter_excludes_online_unless_online_format(catalog_fixture):
    k = catalog_fixture.kato["almaty"].id
    r = search(SearchParams(kato_id=k))
    assert "nurlan-online" not in slugs(r)
    serikov = next(c for c in r.cards if c.specialist.slug == "serikov-aba")
    assert len(serikov.matching_offers) == 1 and not serikov.has_online            # only the in-person medeu row
    assert slugs(search(SearchParams(kato_id=k, formats=["online"]))) == ["serikov-aba", "nurlan-online"]


def test_filter_child_age_in_range(catalog_fixture):
    r = lambda lo, hi: slugs(search(SearchParams(child_age_min=lo, child_age_max=hi)))
    assert r(5, 5) == ["ivanova-logoped", "serikov-aba", "kim-neuro", "nurlan-online", "bekova-karaganda", "omarova-home"]
    assert r(0, 3) == ["ivanova-logoped", "serikov-aba", "bekova-karaganda", "omarova-home"]       # overlap at the boundary 3
    assert r(12, 18) == ["ivanova-logoped", "kim-neuro", "nurlan-online", "omarova-home", "sergeev-free"]


def test_age_lone_bound_open_ended(catalog_fixture):
    assert slugs(search(SearchParams(child_age_min=12))) == ["ivanova-logoped", "kim-neuro", "nurlan-online", "omarova-home", "sergeev-free"]
    assert slugs(search(SearchParams(child_age_max=3))) == ["ivanova-logoped", "serikov-aba", "bekova-karaganda", "omarova-home"]
    # a lone bound is not turned into a single age: min=5 keeps sergeev (6-18), max=11 keeps serikov and bekova (up to 10)
    assert len(slugs(search(SearchParams(child_age_min=5)))) == 7 and "sergeev-free" in slugs(search(SearchParams(child_age_min=5)))
    assert len(slugs(search(SearchParams(child_age_max=11)))) == 7


def test_filter_condition_includes_children(catalog_fixture, reference):
    cid = lambda s: DevelopmentalCondition.objects.get(slug=s).id
    assert slugs(search(SearchParams(condition_ids=[cid("emotional-volitional")]))) == ["serikov-aba", "kim-neuro"]
    assert slugs(search(SearchParams(condition_ids=[cid("ras")]))) == ["serikov-aba"]
    assert slugs(search(SearchParams(condition_ids=[cid("speech-impairment")]))) == ["ivanova-logoped", "nurlan-online", "bekova-karaganda", "sergeev-free"]


def test_filter_type_and_method(catalog_fixture, reference):
    t = SpecialistType.objects.get(slug="logoped").id
    assert slugs(search(SearchParams(specialist_type_ids=[t]))) == ["ivanova-logoped", "nurlan-online"]
    m = Method.objects.filter(slug__in=["aba", "esdm"]).values_list("id", flat=True)
    assert slugs(search(SearchParams(method_ids=list(m)))) == ["serikov-aba"]


def test_filter_price_and_free(catalog_fixture):
    assert slugs(search(SearchParams(price_min=7000, price_max=9000))) == ["ivanova-logoped", "kim-neuro", "bekova-karaganda"]
    assert slugs(search(SearchParams(free_only=True))) == ["sergeev-free"]
    assert search(SearchParams(price_max=100)).total == 0                   # a free service is not stored as 0


def test_filter_price_month(catalog_fixture):
    assert slugs(search(SearchParams(price_month_min=50000))) == ["ivanova-logoped"]
    assert slugs(search(SearchParams(price_month_max=70000))) == ["ivanova-logoped"]
    assert search(SearchParams(price_month_min=100000)).total == 0


def test_filter_format_language_experience(catalog_fixture):
    assert slugs(search(SearchParams(formats=["home_visit"]))) == ["omarova-home"]
    assert slugs(search(SearchParams(formats=["online"]))) == ["serikov-aba", "nurlan-online"]
    assert slugs(search(SearchParams(language_codes=["kk"]))) == ["serikov-aba", "nurlan-online", "bekova-karaganda"]
    assert slugs(search(SearchParams(experience_min=10))) == ["ivanova-logoped", "nurlan-online"]


def test_text_search_kk_without_special_letters(catalog_fixture):
    assert slugs(search(SearchParams(q="караганды")))[0] == "bekova-karaganda"


def test_text_search_typo(catalog_fixture):
    # word_similarity("лагопед", search_norm) >= SEARCH_TRIGRAM_MIN (0.3); лагопед/логопед = 0.5
    s = slugs(search(SearchParams(q="лагопед")))
    assert {"ivanova-logoped", "nurlan-online"} <= set(s) and "hidden-logoped" not in s


def test_text_search_synonym(catalog_fixture):
    s = slugs(search(SearchParams(q="аутизм")))
    assert s[0] == "serikov-aba" and "sergeev-free" not in s


def test_card_groups_offers_and_price_from(catalog_fixture):
    r = search(SearchParams(child_age_min=5, child_age_max=5))
    serikov = next(c for c in r.cards if c.specialist.slug == "serikov-aba")
    assert len(serikov.matching_offers) == 3 and serikov.price_from == 6000 and serikov.has_online


def test_card_nearest_district_name_per_language(catalog_fixture):
    with translation.override("ru"):
        c = next(c for c in search(SearchParams(kato_id=catalog_fixture.kato["almalinskiy"].id)).cards)
        assert c.nearest_district_name == "Алмалинский район"
    with translation.override("kk"):
        c = next(c for c in search(SearchParams(kato_id=catalog_fixture.kato["almalinskiy"].id)).cards)
        assert c.nearest_district_name == "Алмалы ауданы"
    online = next(c for c in search(SearchParams(formats=["online"])).cards if c.specialist.slug == "nurlan-online")
    assert online.nearest_district_name is None


def test_sort_price_nulls_last_free_first(catalog_fixture):
    assert slugs(search(SearchParams(sort="price"))) == ["sergeev-free", "serikov-aba", "bekova-karaganda", "ivanova-logoped", "kim-neuro", "omarova-home", "nurlan-online"]


def test_sort_experience(catalog_fixture):
    assert slugs(search(SearchParams(sort="experience"))) == ["nurlan-online", "ivanova-logoped", "omarova-home", "bekova-karaganda", "serikov-aba", "kim-neuro", "sergeev-free"]


def test_sort_distance_online_and_home_last(catalog_fixture):
    s = slugs(search(SearchParams(sort="distance", near=(76.9, 43.25))))
    assert s[:2] == ["ivanova-logoped", "serikov-aba"] and set(s[-2:]) == {"nurlan-online", "omarova-home"}
    d = {c.specialist.slug: c.distance_m for c in search(SearchParams(sort="distance", near=(76.9, 43.25))).cards}
    assert d["ivanova-logoped"] < d["serikov-aba"] and d["nurlan-online"] is None


def test_paid_tariff_does_not_change_order(catalog_fixture):
    # there is no tariff field yet: relevance order is deterministic (rank desc, specialist_id asc)
    assert slugs(search(SearchParams())) == ["ivanova-logoped", "serikov-aba", "kim-neuro", "nurlan-online", "bekova-karaganda", "omarova-home", "sergeev-free"]


def test_pagination(catalog_fixture, settings):
    settings.SEARCH_PAGE_SIZE = 3
    r = search(SearchParams(page=3))
    assert (r.total, r.pages, r.page, len(r.cards)) == (7, 3, 3, 1)


def test_empty_city_has_no_cards(catalog_fixture):
    r = search(SearchParams(kato_id=catalog_fixture.kato["shymkent"].id))
    assert r.total == 0 and r.cards == []


def test_distance_sort_without_near_equals_relevance(catalog_fixture):
    assert slugs(search(SearchParams(sort="distance"))) == slugs(search(SearchParams()))
    assert slugs(search(SearchParams(sort="distance", q="логопед"))) == slugs(search(SearchParams(q="логопед")))


def test_empty_normalized_query_applies_no_text_filter(catalog_fixture):
    r = search(SearchParams(q="!!!"))
    assert r.total == 7 and slugs(r) == slugs(search(SearchParams()))
