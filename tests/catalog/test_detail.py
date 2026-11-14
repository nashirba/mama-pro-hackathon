import re

import pytest


def test_detail_has_2gis_and_route_links(client, catalog_fixture):
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert "https://2gis.kz/almaty/geo/76.91%2C43.251" in html
    assert "https://2gis.kz/almaty/directions/points/%7C76.91%2C43.251" in html


def test_detail_has_whatsapp_button(client, catalog_fixture):
    assert "https://wa.me/77011234567?text=" in client.get("/ru/specialist/ivanova-logoped/").content.decode()


def test_detail_demo_contact_button_disabled_without_demo_phone(client, catalog_fixture, settings):
    settings.DEPLOY_PROFILE = "demo"
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert "wa.me/77011234567" not in html and "Контакты в демо-версии недоступны" in html and 'aria-disabled="true"' not in html


def test_detail_methods_show_evidence_label(client, catalog_fixture):
    html = client.get("/ru/specialist/kim-neuro/").content.decode()
    assert "Томатис" in html and "нет доказательств эффективности" in html
    assert "есть доказательная база" in client.get("/ru/specialist/serikov-aba/").content.decode()


def test_detail_kk_falls_back_to_ru_bio(client, catalog_fixture):
    r = client.get("/kk/specialist/kim-neuro/")  # нет kk bio
    assert r.status_code == 200 and "Био: Ким Елена" in r.content.decode()


def test_detail_kk_shows_kk_bio_when_present(client, catalog_fixture):
    html = client.get("/kk/specialist/ivanova-logoped/").content.decode()
    assert "Өмірбаян: Иванова Анна" in html
    assert "Иванова Анна" in html and "Подход: Иванова Анна" in html  # имя и approach не пустые на /kk/


def test_detail_kk_row_with_empty_approach_falls_back_per_field(client, catalog_fixture):
    kim = catalog_fixture.specialists["kim-neuro"]
    kim.create_translation("kk", bio="Өмірбаян: Ким Елена", approach="")
    html = client.get("/kk/specialist/kim-neuro/").content.decode()
    assert "Өмірбаян: Ким Елена" in html and "Подход: Ким Елена" in html
    assert "Подход к работе" not in html and "Жұмыс тәсілі" in html


def test_detail_kk_row_with_empty_bio_falls_back_per_field(client, catalog_fixture):
    kim = catalog_fixture.specialists["kim-neuro"]
    kim.create_translation("kk", bio="", approach="Тәсіл: Ким Елена")
    html = client.get("/kk/specialist/kim-neuro/").content.decode()
    assert "Био: Ким Елена" in html and "Тәсіл: Ким Елена" in html


def test_detail_shows_services_with_prices(client, catalog_fixture):
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert "Консультация логопеда" in html and "45 мин" in html and "8\xa0000" in html


def test_detail_home_visit_has_no_address_links(client, catalog_fixture):
    r = client.get("/ru/specialist/omarova-home/")
    assert r.status_code == 200 and "2gis.kz" not in r.content.decode()


def test_hidden_context_detail_404(client, catalog_fixture):
    assert client.get("/ru/specialist/hidden-logoped/").status_code == 404
    assert client.get("/ru/specialist/no-such-slug/").status_code == 404


def test_detail_demo_badges_are_marked_as_demo(client, catalog_fixture, settings):
    settings.DEPLOY_PROFILE = "demo"
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert html.count("(демо)") >= 1 and "Демо: проверка не проводилась" in html
    settings.DEPLOY_PROFILE = "test"
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert "(демо)" not in html and "Демо: проверка не проводилась" not in html


def test_nanny_page_shows_trainings_total_record_and_prices(client, nannies):
    r = client.get("/ru/nanny/aigul-nanny/")
    html = r.content.decode()
    assert r.status_code == 200
    assert "Няня для ребёнка с особенностями развития" in html and "Обучение и сертификаты" in html
    assert "Первая помощь детям" in html and "Центр «Забота»" in html and "Сертификат №" in html and "2024 год" in html
    assert "Всего: 112 часов обучения" in html and html.count("data-first-aid") == 1
    assert "Справка о несудимости" in html and "Есть, выдана" in html
    assert "С какими особенностями развития есть опыт" in html and "О себе: Сапарова Айгуль" in html
    assert "Как работаю: Сапарова Айгуль" in html and "Когда может работать" in html and "График: Сапарова Айгуль" in html
    assert "3\xa0000 ₸" in html and "15\xa0000 ₸" in html and "За месяц" not in html and "Алмалинский район" in html
    assert "от 3\xa0000 ₸ в час" in html and "data-action-bar" in html
    assert "не проводит коррекционных занятий и не ставит диагнозов" in html
    assert "Каталог специалистов" not in html and 'href="/ru/nannies/"' in html


def test_nanny_page_whatsapp_text_is_about_nanny_work(client, nannies):
    html = client.get("/ru/nanny/aigul-nanny/").content.decode()
    assert "https://wa.me/77011234567?text=" in html and "%D0%BD%D1%8F%D0%BD%D0%B5%D0%B9" in html  # «няней»
    assert 'href="tel:+77011234567"' in html


def test_nanny_page_demo_contacts_use_demo_phone(client, nannies, settings):
    settings.DEPLOY_PROFILE = "demo"
    settings.DEMO_CONTACT_PHONE = "+77012223344"
    html = client.get("/ru/nanny/aigul-nanny/").content.decode()
    assert "wa.me/77012223344" in html and "wa.me/77011234567" not in html


def test_nanny_page_404_for_hidden_nannies_and_wrong_urls(client, nannies):
    for slug in ("no-record-nanny", "no-first-aid-nanny", "no-training-nanny", "no-such-nanny"):
        assert client.get(f"/ru/nanny/{slug}/").status_code == 404, slug
    assert client.get("/ru/specialist/aigul-nanny/").status_code == 404
    assert client.get("/ru/nanny/ivanova-logoped/").status_code == 404


def test_nanny_page_kk(client, nannies):
    r = client.get("/kk/nanny/aigul-nanny/")
    html = r.content.decode()
    assert r.status_code == 200 and "Оқу және сертификаттар" in html and "Обучение и сертификаты" not in html


def test_specialist_page_keeps_shared_blocks(client, catalog_fixture):
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert "data-action-bar" in html and "от 8\xa0000 ₸" in html and 'href="/ru/specialists/"' in html
    assert "Каталог специалистов" in html and "Алматы" in html


@pytest.mark.parametrize("path", ["/ru/specialist/ivanova-logoped/", "/ru/nanny/aigul-nanny/"])
def test_action_bar_sits_above_bottom_nav(client, nannies, path):
    html = client.get(path).content.decode()
    tokens = re.search(r'<div data-action-bar class="([^"]*)"', html).group(1).split()
    assert "bottom-[calc(3.5rem+1px+env(safe-area-inset-bottom))]" in tokens and "bottom-0" not in tokens
