import re

import pytest

from tests.factories import UserFactory


def _nav(html):
    return html.split("data-bottom-nav")[1].split("</nav>")[0]


def test_nav_has_five_items_in_order(client, db):
    nav = _nav(client.get("/ru/").content.decode())
    labels = ["Главная", "Сообщество", "Избранное", "Поиск", "Кабинет"]
    assert [nav.index(label) for label in labels] == sorted(
        nav.index(label) for label in labels
    )


def test_nav_hidden_on_desktop_and_fixed(client, db):
    html = client.get("/ru/").content.decode()
    assert re.search(
        r'data-bottom-nav[^>]*class="[^"]*fixed[^"]*lg:hidden', html
    ) or re.search(r'class="[^"]*fixed[^"]*lg:hidden[^"]*"[^>]*data-bottom-nav', html)


def test_body_has_bottom_padding_on_mobile(client, db):
    html = client.get("/ru/").content.decode()
    tokens = re.search(r'<body class="([^"]*)"', html).group(1).split()
    assert "pb-[calc(4rem+env(safe-area-inset-bottom))]" in tokens
    assert "lg:pb-0" in tokens and "bg-white" in tokens


@pytest.mark.parametrize(
    "path, label",
    [
        ("/ru/", "Главная"),
        ("/ru/community/", "Сообщество"),
        ("/ru/specialists/", "Поиск"),
        ("/ru/almaty/logoped/", "Поиск"),
    ],
)
def test_active_item(client, catalog_fixture, path, label):
    nav = _nav(client.get(path).content.decode())
    current = nav.split('aria-current="page"')[1].split("</a>")[0]
    assert label in current and nav.count('aria-current="page"') == 1


@pytest.mark.parametrize("path", ["/ru/nannies/", "/ru/mamapro/"])
def test_no_active_item_on_other_pages(client, db, path):
    assert 'aria-current="page"' not in _nav(client.get(path).content.decode())


def test_search_link_focuses_input(client, db):
    assert 'href="/ru/specialists/?focus=q"' in _nav(
        client.get("/ru/").content.decode()
    )


def test_cabinet_link_for_anonymous_goes_to_login(client, db):
    assert 'href="/ru/login/?next=/ru/cabinet/"' in _nav(
        client.get("/ru/").content.decode()
    )


def test_cabinet_and_favorites_active_for_user(client, db):
    client.force_login(UserFactory())
    for path, label in (("/ru/cabinet/", "Кабинет"), ("/ru/favorites/", "Избранное")):
        nav = _nav(client.get(path).content.decode())
        assert label in nav.split('aria-current="page"')[1].split("</a>")[0]
