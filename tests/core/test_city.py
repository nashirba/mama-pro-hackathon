import re

import pytest


def _choose(client, kato_id, next_url="/ru/"):
    return client.post("/ru/city/", {"kato_id": kato_id, "next": next_url})


def _button_text(client) -> str:
    html = client.get("/ru/").content.decode()
    match = re.search(r"<button[^>]*data-city-button[^>]*>(.*?)</button>", html, re.DOTALL)
    return re.sub(r"<svg.*?</svg>|<[^>]+>", "", match.group(1), flags=re.DOTALL).strip()


def test_choose_city_sets_cookie_and_returns(client, kato_demo):
    r = _choose(client, kato_demo["almaty"].id, "/ru/nannies/")
    assert r.headers["Location"] == "/ru/nannies/" and r.cookies["city"].value == str(
        kato_demo["almaty"].id
    )


def test_any_city_deletes_cookie(client, kato_demo):
    _choose(client, kato_demo["almaty"].id)
    r = _choose(client, "")
    assert r.cookies["city"].value == "" and r.cookies["city"]["max-age"] == 0


def test_external_next_is_ignored(client, kato_demo):
    assert (
        _choose(client, kato_demo["almaty"].id, "https://evil.example/").headers[
            "Location"
        ]
        == "/ru/"
    )


def test_get_not_allowed(client, db):
    assert client.get("/ru/city/").status_code == 405


def test_header_shows_selected_city(client, kato_demo):
    assert _button_text(client) == "Город"
    _choose(client, kato_demo["almaty"].id)
    assert _button_text(client) == "Алматы"


@pytest.mark.parametrize("path", ["/ru/specialists/", "/ru/nannies/"])
def test_catalog_without_params_redirects_to_city(client, kato_demo, path):
    _choose(client, kato_demo["almaty"].id)
    assert (
        client.get(path).headers["Location"]
        == f"{path}?kato_id={kato_demo['almaty'].id}"
    )


def test_focus_param_kept_on_redirect(client, kato_demo):
    _choose(client, kato_demo["almaty"].id)
    assert (
        client.get("/ru/specialists/?focus=q").headers["Location"]
        == f"/ru/specialists/?kato_id={kato_demo['almaty'].id}&focus=q"
    )


def test_explicit_params_win(client, kato_demo):
    _choose(client, kato_demo["almaty"].id)
    assert (
        client.get(f"/ru/specialists/?kato_id={kato_demo['astana'].id}").status_code
        == 200
    )
    assert client.get("/ru/specialists/?q=логопед").status_code == 200


def test_htmx_request_not_redirected(client, kato_demo):
    _choose(client, kato_demo["almaty"].id)
    assert client.get("/ru/specialists/", HTTP_HX_REQUEST="true").status_code == 200


@pytest.mark.parametrize("value", ["garbage", "999999"])
def test_bad_cookie_is_ignored(client, kato_demo, value):
    client.cookies["city"] = value
    assert client.get("/ru/specialists/").status_code == 200


def test_non_city_node_cookie_is_ignored(client, kato_demo):
    client.cookies["city"] = str(kato_demo["almalinskiy"].id)  # a district
    assert client.get("/ru/specialists/").status_code == 200


def test_no_cookie_no_redirect(client, kato_demo):
    assert client.get("/ru/specialists/").status_code == 200


def test_home_city_select_preselected(client, kato_demo):
    _choose(client, kato_demo["almaty"].id)
    assert (
        f'<option value="{kato_demo["almaty"].id}" selected>'
        in client.get("/ru/").content.decode()
    )


def test_search_input_autofocus(client, kato_demo):
    html = client.get("/ru/specialists/?focus=q").content.decode()
    assert re.search(r'id="f-q"[^>]*autofocus', html)
