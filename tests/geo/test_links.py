from apps.geo.links import two_gis_route_url, two_gis_url


def test_geo_link_lon_first(address_almaty):
    assert two_gis_url(address_almaty) == "https://2gis.kz/almaty/geo/76.945465%2C43.238293"


def test_firm_link_wins(address_almaty):
    address_almaty.two_gis_firm_url = "https://2gis.kz/almaty/firm/70000001012345678"
    assert two_gis_url(address_almaty) == "https://2gis.kz/almaty/firm/70000001012345678"


def test_route_link(address_almaty):
    assert two_gis_route_url(address_almaty) == "https://2gis.kz/almaty/directions/points/%7C76.945465%2C43.238293"


def test_district_uses_city_slug(address_in_almaly_district):
    assert address_in_almaly_district.city_slug() == "almaty"
    assert two_gis_url(address_in_almaly_district) == "https://2gis.kz/almaty/geo/76.914%2C43.253"


def test_rural_without_city_uses_city_less_links(address_rural):
    assert address_rural.city_slug() == ""
    assert two_gis_url(address_rural) == "https://2gis.kz/geo/70%2C49"
    assert two_gis_route_url(address_rural) == "https://2gis.kz/directions/points/%7C70%2C49"
