import re

from apps.catalog.models import DevelopmentalCondition, SpecialistType
from apps.geo.models import KatoNode

FILTER_NAMES = [
    "kato_id", "district_id", "specialist_type_ids", "child_age_min", "child_age_max", "condition_ids", "price_min", "price_max",
    "price_month_min", "price_month_max", "free_only", "formats", "language_codes", "experience_min",
    "method_ids", "sort", "q", "near",
]


def slugs(response) -> list[str]:
    return [c.specialist.slug for c in response.context["result"].cards]


def test_results_page_all_filters_render(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    for name in FILTER_NAMES:
        assert f'name="{name}"' in html, name
    # Every catalog profile passed all checks, so there is no verification filter.
    assert 'name="verification_levels"' not in html


def test_near_me_button_present_and_distance_option_hidden_without_near(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    assert "data-geolocate" in html and 'value="distance"' not in html


def test_distance_option_shown_with_near(client, catalog_fixture):
    r = client.get("/ru/specialists/?near=76.9,43.25&sort=distance")
    html = r.content.decode()
    assert '<option value="distance" selected>' in html and 'name="near" value="76.9,43.25"' in html
    assert slugs(r)[:2] == ["ivanova-logoped", "serikov-aba"]


def test_near_value_is_not_localized_in_kk(client, catalog_fixture):
    html = client.get("/kk/specialists/?near=76.9,43.25&sort=distance").content.decode()
    assert 'name="near" value="76.9,43.25"' in html


def test_sort_distance_without_near_falls_back_to_relevance(client, catalog_fixture):
    r = client.get("/ru/specialists/?sort=distance")
    assert r.status_code == 200 and r.context["params"].sort == "relevance"


def test_age_quick_groups_are_links(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    for lo, hi in [(0, 3), (3, 7), (7, 12), (12, 18)]:
        assert f"child_age_min={lo}&amp;child_age_max={hi}" in html


def test_age_quick_groups_keep_other_params(client, catalog_fixture):
    html = client.get("/ru/specialists/?formats=online&child_age_min=1").content.decode()
    assert "?formats=online&amp;child_age_min=3&amp;child_age_max=7" in html


def test_district_overrides_city(client, catalog_fixture):
    k = catalog_fixture.kato
    r = client.get(f"/ru/specialists/?kato_id={k['almaty'].id}&district_id={k['almalinskiy'].id}")
    assert slugs(r) == ["ivanova-logoped"]


def test_htmx_returns_partial(client, catalog_fixture):
    r = client.get(f"/ru/specialists/?kato_id={catalog_fixture.kato['almaty'].id}", HTTP_HX_REQUEST="true")
    html = r.content.decode()
    assert "<html" not in html and 'id="results"' not in html and 'data-specialist="ivanova-logoped"' in html


def test_full_page_has_results_container(client, catalog_fixture):
    assert 'id="results"' in client.get("/ru/specialists/").content.decode()


def test_empty_state(client, catalog_fixture):
    r = client.get("/ru/specialists/?price_max=100")
    html = r.content.decode()
    assert r.status_code == 200 and "Ничего не нашлось" in html and "formats=online" not in html  # no city: no way to widen
    html = client.get("/ru/specialists/?price_max=100&kato_id=1").content.decode()
    assert "formats=online" in html


def test_landing_title_type(client, catalog_fixture):
    assert "Логопеды в Алматы" in client.get("/ru/almaty/logoped/").content.decode()
    assert "Алматыдағы логопедтер" in client.get("/kk/almaty/logoped/").content.decode()


def test_landing_title_condition(client, catalog_fixture):
    assert "Специалисты по РАС в Алматы" in client.get("/ru/almaty/ras/").content.decode()
    assert "Алматыдағы РАС бойынша мамандар" in client.get("/kk/almaty/ras/").content.decode()


def test_landing_title_keeps_abbreviations_and_lowercases_kk_words(client, catalog_fixture):
    assert "Алматыдағы эпилепсия бойынша мамандар" in client.get("/kk/almaty/epilepsy/").content.decode()
    assert "Алматыдағы ABA-терапевттер" in client.get("/kk/almaty/aba-therapist/").content.decode()


def test_landing_title_kk_without_kk_row_is_all_ru(client, catalog_fixture):
    # the reference data now has KZ names for every type and condition, so make rows that only have RU
    only_ru_type = SpecialistType.objects.language("ru").create(
        slug="only-ru-type", name="Тестовый тип", name_plural="Тестовые типы", landing_name="Тестовые типы"
    )
    assert not only_ru_type.has_translation("kk")
    html = client.get("/kk/almaty/only-ru-type/").content.decode()
    assert "Тестовые типы в Алматы" in html
    only_ru_condition = DevelopmentalCondition.objects.language("ru").create(
        slug="only-ru-condition", name="Тестовая особенность", landing_name="Специалисты по тестовой особенности"
    )
    assert not only_ru_condition.has_translation("kk")
    assert "Специалисты по тестовой особенности в Алматы" in client.get("/kk/almaty/only-ru-condition/").content.decode()


def test_landing_title_kk_for_city_without_kk_locative_is_all_ru(client, catalog_fixture):
    KatoNode.objects.create(code="889", level="city", slug="ru-only", name="Тест", name_locative="в Тесте")
    assert "Логопеды в Тесте" in client.get("/kk/ru-only/logoped/").content.decode()


def test_landing_title_without_locative_uses_colon_form(client, catalog_fixture):
    KatoNode.objects.create(code="888", level="city", slug="no-loc", name="Тест")
    assert "Логопеды: Тест" in client.get("/ru/no-loc/logoped/").content.decode()


def test_landing_preselects_filters(client, catalog_fixture):
    assert slugs(client.get("/ru/almaty/logoped/")) == ["ivanova-logoped"]
    assert slugs(client.get("/ru/almaty/ras/")) == ["serikov-aba"]


def checked_values(html: str, name: str) -> list[str]:
    return re.findall(rf'<input type="checkbox" name="{name}" value="([^"]+)"[^>]*? checked>', html)


def test_landing_form_shows_preselected_city_and_type(client, catalog_fixture):
    html = client.get("/ru/almaty/logoped/").content.decode()
    almaty_id = catalog_fixture.kato["almaty"].id
    assert f'<option value="{almaty_id}" selected>' in html
    assert checked_values(html, "specialist_type_ids") == [str(SpecialistType.objects.get(slug="logoped").id)]
    assert checked_values(html, "condition_ids") == []


def test_landing_form_shows_preselected_condition(client, catalog_fixture):
    html = client.get("/ru/almaty/ras/").content.decode()
    assert checked_values(html, "condition_ids") == [str(DevelopmentalCondition.objects.get(slug="ras").id)]
    assert checked_values(html, "specialist_type_ids") == []


def test_unknown_landing_404(client, catalog_fixture):
    assert client.get("/ru/nowhere/logoped/").status_code == 404
    assert client.get("/ru/almaty/nonexistent/").status_code == 404


def test_card_has_no_separate_online_chip(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    assert 'data-badge="online"' not in html


def test_card_price_labels(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    assert "бесплатно" in html and "цена по запросу" in html and "от 8" in html


def test_kk_page_text_search_finds_ru_profiles(client, catalog_fixture):
    r = client.get("/kk/specialists/?q=логопед")
    assert {"ivanova-logoped", "nurlan-online"} <= set(slugs(r))


def test_kk_cards_show_specialist_names(client, catalog_fixture):
    html = client.get("/kk/specialists/").content.decode()
    for name in ("Иванова Анна", "Сериков Данияр", "Ахметов Нурлан", "Бекова Айгерим"):  # у них есть строка перевода kk
        assert name in html


def test_demo_contact_button_disabled_without_phone(client, catalog_fixture, settings):
    settings.DEPLOY_PROFILE = "demo"
    html = client.get("/ru/specialists/").content.decode()
    # every card offers WhatsApp and a call; without a demo number they look the same and do nothing
    card = card_html(html, "ivanova-logoped")
    assert card.count("data-demo-contact") == 2 and "в демо-версии не работает" not in card
    assert "data-contact-number" not in card
    assert "wa.me/77011234567" not in html and "tel:+77011234567" not in html


def test_demo_contact_buttons_lead_only_to_demo_phone(client, catalog_fixture, settings):
    settings.DEPLOY_PROFILE = "demo"
    settings.DEMO_CONTACT_PHONE = "+77000000000"
    html = client.get("/ru/specialists/").content.decode()
    assert "https://wa.me/77000000000?text=" in html and "tel:+77000000000" in html
    assert "+7 700 000 00 00" in card_html(html, "ivanova-logoped")
    assert "77011234567" not in html and "в демо-версии не работает" not in html


def card_html(html: str, slug: str) -> str:
    return re.search(rf'<article data-specialist="{slug}".*?</article>', html, re.S).group(0)


def test_contact_button_hidden_without_phone_outside_demo(client, catalog_fixture, settings):
    settings.DEPLOY_PROFILE = "test"
    html = client.get("/ru/specialists/").content.decode()
    assert "в демо-версии не работает" not in html
    free = card_html(html, "sergeev-free")  # no whatsapp_phone and no public_phone
    assert "wa.me" not in free and "tel:" not in free and "aria-disabled" not in free
    card = card_html(html, "ivanova-logoped")
    assert "https://wa.me/77011234567" in card and "tel:+77011234567" in card and "+7 701 123 45 67" in card


def test_htmx_history_restore_returns_full_page(client, catalog_fixture):
    r = client.get("/ru/specialists/", HTTP_HX_REQUEST="true", HTTP_HX_HISTORY_RESTORE_REQUEST="true")
    html = r.content.decode()
    assert "<html" in html and 'id="results"' in html and 'name="q"' in html


def test_htmx_response_varies_and_updates_heading_out_of_band(client, catalog_fixture):
    r = client.get("/ru/specialists/?kato_id=1", HTTP_HX_REQUEST="true")
    assert "HX-Request" in r["Vary"]
    html = r.content.decode()
    assert '<h1 id="page-heading" hx-swap-oob="true"' in html and "Логопеды" not in html


def test_full_page_heading_is_not_out_of_band_and_keeps_landing_title(client, catalog_fixture):
    html = client.get("/ru/almaty/logoped/").content.decode()
    assert "hx-swap-oob" not in html
    assert re.search(r'<h1 id="page-heading" class="[^"]*">Логопеды в Алматы</h1>', html)


def test_age_quick_group_has_href_and_client_handler(client, catalog_fixture):
    # the href alone works without JS; with JS @click.prevent sets the inputs from the live form state
    html = client.get("/ru/specialists/?formats=online").content.decode()
    link = re.search(r'<a href="([^"]*child_age_min=3&amp;child_age_max=7)"[^>]*>', html)
    assert link and link.group(1).startswith("/ru/specialists/?formats=online&amp;")
    assert '@click.prevent="setAge($el.closest(\'form\'), 3, 7)"' in link.group(0)


def test_links_carry_no_empty_params(client, catalog_fixture):
    html = client.get("/ru/specialists/?q=&near=&price_min=&price_max=100&formats=in_person&kato_id=1").content.decode()
    hrefs = re.findall(r'href="(/ru/specialists/\?[^"]*)"', html)
    assert hrefs
    for href in hrefs:
        assert "q=" not in href and "near=" not in href and "price_min=" not in href, href
    assert "price_max=100&amp;formats=in_person&amp;formats=online" in html  # the "online" link


def test_card_shows_single_verified_mark(client, catalog_fixture, settings):
    settings.DEPLOY_PROFILE = "demo"
    html = client.get("/ru/specialists/").content.decode()
    card = card_html(html, "ivanova-logoped")
    assert card.count("data-verified") == 1 and "Проверено Мама Про" in card
    assert "Демо: проверка не проводилась" in card and "Образование подтверждено" not in card
    assert "data-demo-notice" not in html and "Подтверждённые документы" not in html and 'name="verification_levels"' not in html


def test_card_mark_unmarked_outside_demo(client, catalog_fixture, settings):
    settings.DEPLOY_PROFILE = "test"
    html = client.get("/ru/specialists/").content.decode()
    assert "(демо)" not in html and "Демо: проверка не проводилась" not in html


def test_specialists_intro_explains_verification(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    assert "Что значит проверенный специалист" in html
    assert "прошли все проверки Мама Про" in html
    for level in ("Личность подтверждена", "Образование подтверждено", "Квалификация подтверждена", "Проверка на безопасность пройдена"):
        assert level in html


def test_specialists_intro_not_on_nannies_page(client, catalog_fixture):
    assert "Что значит проверенный специалист" not in client.get("/ru/nannies/").content.decode()


def test_home_still_lists_verification_levels(client, catalog_fixture):
    html = client.get("/ru/").content.decode()
    assert html.count("Квалификация подтверждена") == 1 and "Видели диплом по специальности" in html


def test_results_map_is_shorter_than_viewport_on_desktop(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    assert "xl:h-[calc(100vh-8rem)]" in html and "xl:h-[calc(100vh-2rem)]" not in html
