def test_detail_has_2gis_and_route_links(client, catalog_fixture):
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert "https://2gis.kz/almaty/geo/76.91%2C43.251" in html
    assert "https://2gis.kz/almaty/directions/points/%7C76.91%2C43.251" in html


def test_detail_has_whatsapp_button(client, catalog_fixture):
    assert "https://wa.me/77011234567?text=" in client.get("/ru/specialist/ivanova-logoped/").content.decode()


def test_detail_demo_contact_button_disabled_without_demo_phone(client, catalog_fixture, settings):
    settings.DEPLOY_PROFILE = "demo"
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert "wa.me/77011234567" not in html and 'aria-disabled="true"' in html and "в демо-версии не работает" in html


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
