def test_home_has_search_and_popular_types(client, catalog_fixture):
    r = client.get("/ru/")
    html = r.content.decode()
    assert 'name="q"' in html and 'action="/ru/specialists/"' in html and 'hx-get="/ru/suggest/"' in html
    assert 'hx-trigger="input changed delay:250ms"' in html
    popular = r.context["popular_types"]
    assert len(popular) == 8 and popular[0].slug == "logoped" and popular[0].specialists_count == 2   # hidden-logoped не считается


def test_home_suggest_dropdown_closes_and_keeps_city(client, catalog_fixture):
    html = client.get("/ru/").content.decode()
    assert 'x-data="{ open: false,' in html and 'role="combobox"' in html and '@click.outside="open = false"' in html and '@keydown.escape="$refs.input.focus(); open = false"' in html
    assert '@input="open = true"' in html and '@focus="open = true"' in html and 'x-show="open"' in html
    assert 'hx-include="#home-city"' in html and 'id="home-city"' in html


def test_home_popular_types_match_results_and_skip_zero(client, catalog_fixture):
    popular = client.get("/ru/").context["popular_types"]
    assert all(t.specialists_count > 0 for t in popular)
    by_slug = {t.slug: t.specialists_count for t in popular}
    r = client.get(f"/ru/specialists/?specialist_type_ids={popular[0].id}")
    assert len(r.context["result"].cards) == by_slug["logoped"] == 2


def test_home_popular_types_order_is_count_then_slug(client, catalog_fixture):
    popular = client.get("/ru/").context["popular_types"]
    keys = [(-t.specialists_count, t.slug) for t in popular]
    assert keys == sorted(keys)


def test_home_popular_type_links_to_results(client, catalog_fixture):
    r = client.get("/ru/")
    assert f"/ru/specialists/?specialist_type_ids={r.context['popular_types'][0].id}" in r.content.decode()


def test_home_has_trust_block_and_register_entry(client, catalog_fixture):
    html = client.get("/ru/").content.decode()
    assert "Что значит проверенный специалист" in html and 'href="/ru/login/?next=' in html


def test_home_city_links(client, catalog_fixture):
    html = client.get("/ru/").content.decode()
    assert f"kato_id={catalog_fixture.kato['almaty'].id}" in html


def test_home_kk_renders_with_unlocalized_ids(client, catalog_fixture):
    r = client.get("/kk/")
    html = r.content.decode()
    assert r.status_code == 200 and 'hx-get="/kk/suggest/"' in html and 'action="/kk/specialists/"' in html
    assert f"kato_id={catalog_fixture.kato['almaty'].id}" in html
    assert "Что значит проверенный специалист" not in html


def test_robots_disallows_all(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r.content.decode().splitlines() == ["User-agent: *", "Disallow: /"]
    assert r["Content-Type"].startswith("text/plain")


def test_home_has_nannies_block_with_count_of_shown_nannies(client, nannies):
    r = client.get("/ru/")
    html = r.content.decode()
    assert r.context["nannies_count"] == 2  # three nannies are hidden by the rule
    assert "Обученные няни" in html and 'href="/ru/nannies/"' in html and "2 няни в разделе" in html


def test_home_popular_types_ignore_nannies(client, nannies):
    popular = client.get("/ru/").context["popular_types"]
    assert popular[0].slug == "logoped" and popular[0].specialists_count == 2


def test_header_links_to_nannies(client, catalog_fixture):
    for url, link in (("/ru/", 'href="/ru/nannies/"'), ("/ru/specialists/", 'href="/ru/nannies/"'), ("/kk/", 'href="/kk/nannies/"')):
        header = client.get(url).content.decode().split("<header")[1].split("</header>")[0]
        assert link in header, url
    assert ">Няни<" in client.get("/ru/").content.decode().split("</header>")[0]
