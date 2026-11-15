def test_header_specialists_link_before_nannies(client, db):
    html = client.get("/ru/").content.decode()
    assert 'href="/ru/specialists/"' in html
    assert html.index(">Специалисты<") < html.index(">Няни<")


def test_header_specialists_link_current_on_search(client, db):
    html = client.get("/ru/specialists/").content.decode()
    assert 'href="/ru/specialists/" aria-current="page"' in html


def test_header_specialists_link_in_kazakh(client, db):
    assert ">Мамандар<" in client.get("/kk/").content.decode()


def test_header_specialists_link_visible_on_phone(client, db):
    html = client.get("/ru/").content.decode()
    start = html.index('href="/ru/specialists/"')
    tag = html[start : html.index(">", start)]
    assert 'class="inline-flex ' in tag
    assert "hidden" not in tag
