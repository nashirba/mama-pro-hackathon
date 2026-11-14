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


def test_params_section_is_not_a_query_parameter():
    p = SearchParams.from_querydict(QueryDict("section=nannies&pay_units=night&pay_units=hour&price_hour_min=2000&price_hour_max=x"))
    assert (p.section, p.pay_units, p.price_hour_min, p.price_hour_max) == ("specialists", ["night", "hour"], 2000, None)
    nannies = SearchParams.from_querydict(QueryDict("pay_units=month"), section="nannies")
    assert nannies.section == "nannies" and "section" not in nannies.to_querydict()
    assert SearchParams.from_querydict(nannies.to_querydict(), section="nannies") == nannies


def test_params_unknown_section_falls_back_to_specialists():
    assert SearchParams.from_querydict(QueryDict(""), section="bogus").section == "specialists"
