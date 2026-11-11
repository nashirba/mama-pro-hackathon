from django.http import QueryDict

from apps.search.query import SearchParams


def test_params_defaults_are_valid_dataclass():
    p = SearchParams(kato_id=5)
    assert p.q == "" and p.formats == [] and p.sort == "relevance" and p.page == 1 and p.near is None


def test_params_from_querydict():
    p = SearchParams.from_querydict(QueryDict("kato_id=5&formats=online&formats=in_person&near=76.9,43.25&sort=bogus&price_max=abc&page=0"))
    assert (p.kato_id, p.formats, p.near, p.sort, p.price_max, p.page) == (5, ["online", "in_person"], (76.9, 43.25), "relevance", None, 1)


def test_params_distance_sort_requires_valid_near():
    assert SearchParams.from_querydict(QueryDict("sort=distance&near=76.9,43.25")).sort == "distance"
    assert SearchParams.from_querydict(QueryDict("sort=distance")).sort == "relevance"
    p = SearchParams.from_querydict(QueryDict("sort=distance&near=abc"))
    assert p.sort == "relevance" and p.near is None


def test_params_roundtrip_querydict():
    p = SearchParams(kato_id=5, formats=["online", "in_person"], near=(76.9, 43.25), sort="distance", child_age_min=3, child_age_max=7)
    assert SearchParams.from_querydict(p.to_querydict()) == p
