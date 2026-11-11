from .models import Address


def _coord(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _lon_lat(address: Address) -> str:
    return f"{_coord(address.point.x)}%2C{_coord(address.point.y)}"


def _base(address: Address) -> str:
    city_slug = address.city_slug()
    return f"https://2gis.kz/{city_slug}" if city_slug else "https://2gis.kz"


def two_gis_url(address: Address) -> str:
    if address.two_gis_firm_url:
        return address.two_gis_firm_url
    return f"{_base(address)}/geo/{_lon_lat(address)}"


def two_gis_route_url(address: Address) -> str:
    return f"{_base(address)}/directions/points/%7C{_lon_lat(address)}"
