import pytest


@pytest.fixture
def page(client, db):
    return client.get("/ru/mamapro/").content.decode()


def test_mamapro_page_lists_the_sections_in_order(page):
    titles = ["Анонс ближайших курсов", "Курсы фонда", "Купить онлайн курсы", "Филиалы в Казахстане", "Поддержка фонда"]
    positions = [page.index(t) for t in titles]
    assert positions == sorted(positions)


def test_mamapro_links_point_to_the_foundation_pages(page):
    assert 'href="https://project2418305.tilda.ws/page40285738.html#!/tab/651857742-2"' in page
    assert 'href="https://mamapro.kz/#rec199050404"' in page
    assert 'href="https://kaspi.kz/pay/mamapro"' in page


def test_mamapro_lists_foundation_courses(page):
    for course in ("Основы предпринимательства", "Сиблинги", "Психологическая поддержка"):
        assert course in page


def test_mamapro_lists_branches_with_instagram(page):
    for city in ("Астана", "Алматы", "Усть-Каменогорск", "Шымкент", "Костанай"):
        assert city in page
    assert 'href="https://instagram.com/mamapro_kst"' in page


def test_mamapro_online_courses_are_coming_soon(page):
    assert "Скоро" in page


def test_external_links_open_in_new_tab(page):
    assert page.count('target="_blank" rel="noopener"') >= 3


def test_header_has_mamapro_link_after_community(client, db):
    html = client.get("/ru/").content.decode()
    assert 'href="/ru/mamapro/"' in html
    assert html.index(">Сообщество<") < html.index(">Мама Про<")


def test_header_mamapro_link_current_on_its_page(client, db):
    assert 'href="/ru/mamapro/" aria-current="page"' in client.get("/ru/mamapro/").content.decode()


def test_mamapro_page_in_kazakh(client, db):
    html = client.get("/kk/mamapro/").content.decode()
    assert "Қорды қолдау" in html and "Поддержка фонда" not in html


def test_brand_uses_cyrillic_name(client, db, settings):
    assert settings.BRAND_NAME == "Особенный путь с Мама Про"
    assert "Mama Pro" not in client.get("/ru/").content.decode()
