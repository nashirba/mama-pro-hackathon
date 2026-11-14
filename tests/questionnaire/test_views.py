import re

import pytest

from apps.catalog.models import SpecialistType
from apps.questionnaire.questions import SECTIONS

SCALE_KEYS = {q.key for s in SECTIONS for q in s.questions if q.kind == "scale"}
ALL_ZERO = {k: "0" for k in SCALE_KEYS}
NEUTRAL = "Баллы показывают, как часто наблюдается описанное в утверждениях раздела. Это не оценка нормы и не диагноз."
PLAQUE = "Рекомендация примерная: специалисты пока подбираются без учёта баллов."
NEW_DISCLAIMER = "(Это не является медицинской диагностикой, а носит рекомендательный характер.)"


def _section_html(html: str, section_id: str) -> str:
    start = html.index(f'<section id="{section_id}"')
    return html[start:html.index("</section>", start)]


def _form_html(html: str) -> str:
    start = html.index('<form id="questionnaire-form"')
    return html[start:html.index("</form>", start)]


@pytest.mark.django_db
def test_form_renders_all_sections(client):
    r = client.get("/ru/questionnaire/")
    html = r.content.decode()
    assert r.status_code == 200
    for s in SECTIONS:
        assert str(s.title) in html
    assert html.count('type="radio"') == 264
    assert "Ответы не сохраняются. Баллы считаются только для показа результата." in html
    assert "Это не медицинская диагностика, а рекомендация." in html


@pytest.mark.django_db
def test_form_field_names_are_scale_only(client):
    form = _form_html(client.get("/ru/questionnaire/").content.decode())
    assert 'method="post"' in form and "csrfmiddlewaretoken" in form
    names = set(re.findall(r'<(?:input|textarea)[^>]*\bname="([^"]+)"', form))
    assert names == SCALE_KEYS | {"csrfmiddlewaretoken"}


@pytest.mark.django_db
def test_form_has_no_personal_fields(client):
    form = _form_html(client.get("/ru/questionnaire/").content.decode())
    for text in ("Ф.И.О.", "Дата рождения", "Возраст", 'type="date"'):
        assert text not in form


@pytest.mark.django_db
def test_form_has_no_text_sections(client):
    form = _form_html(client.get("/ru/questionnaire/").content.decode())
    assert "<textarea" not in form
    assert "Общая информация" not in form
    assert "Дополнительная информация от родителей" not in form


@pytest.mark.django_db
def test_form_paginates_by_section(client):
    html = client.get("/ru/questionnaire/").content.decode()
    form = _form_html(html)
    shows = re.findall(r'x-show="step === (\d+)"', form)
    assert shows == [str(i) for i in range(6)]
    ids = re.findall(r'<section aria-labelledby="sec-([a-z]+)"', form)
    assert ids == [s.key for s in SECTIONS]
    tags = re.findall(r"<section [^>]*>", form)
    assert len(tags) == 6
    assert "data-step-cloak" not in tags[0]
    assert all("data-step-cloak" in t for t in tags[1:])
    assert "<noscript><style>[data-step-cloak]" in html
    assert 'x-data="{ step: 0, total: 6,' in form
    assert "[data-step=" in form and "x-init=" in form


@pytest.mark.django_db
def test_form_step_a11y_and_cloak_attributes(client):
    form = _form_html(client.get("/ru/questionnaire/").content.decode())
    for n, section in enumerate(SECTIONS):
        assert f'<h2 id="sec-{section.key}" data-step="{n}" tabindex="-1"' in form
    assert '<div x-cloak aria-hidden="true" class="grid grid-cols-6' in form
    assert re.search(r'<button type="button" x-cloak x-show="step > 0"', form)
    assert re.search(r'<button type="button" x-cloak x-show="step < total - 1"', form)
    assert re.search(r'<button type="submit" x-show="step === total - 1" data-step-cloak', form)
    assert '<div class="flex gap-3">' in form


@pytest.mark.django_db
def test_form_progress_labels(client):
    form = _form_html(client.get("/ru/questionnaire/").content.decode())
    for n in range(1, 7):
        assert form.count(f"Раздел {n} из 6") == 1
    assert form.count('class="h-1.5 rounded-full"') == 6


@pytest.mark.django_db
def test_form_navigation_buttons(client):
    form = _form_html(client.get("/ru/questionnaire/").content.decode())
    assert re.search(r'<button type="button" x-cloak x-show="step > 0"[^>]*>\s*Назад', form)
    assert re.search(r'<button type="button" x-cloak x-show="step < total - 1"[^>]*>\s*Далее', form)
    assert re.search(r'<button type="submit" x-show="step === total - 1" data-step-cloak[^>]*>\s*Получить рекомендацию', form)


@pytest.mark.django_db
def test_form_scale_labels_without_points_and_bulleted(client):
    form = _form_html(client.get("/ru/questionnaire/").content.decode())
    assert "text-xs" not in form   # points are not shown on the options
    for label in ("Никогда", "Редко", "Иногда", "Часто"):
        assert form.count(f">{label}</span>") == 66
    assert form.count('<ul class="list-none') == 6
    assert len(re.findall(r"<li>\s*<fieldset>", form)) == 66
    assert form.count('<span aria-hidden="true" class="text-primary-700">&bull;</span>') == 66


@pytest.mark.django_db
def test_post_scores_and_shows_top(client):
    data = dict(ALL_ZERO, **{k: "3" for k in SCALE_KEYS if k.startswith("motor_")})
    r = client.post("/ru/questionnaire/", data)
    assert r.status_code == 302
    session = client.session
    assert set(session.keys()) == {"questionnaire_scores", "_session_expiry"}
    assert all(
        isinstance(v, list) and all(isinstance(i, int) for i in v)
        for v in session["questionnaire_scores"].values()
    )
    html = client.get(r["Location"]).content.decode()
    top = _section_html(html, "top-sections")
    assert "Наивысший балл" in top
    assert "Двигательное развитие и физическая активность" in top
    assert "баллов: 30 из 30" in top
    assert "Речевое развитие и коммуникация" not in top
    assert "Баллы по разделам" in html
    assert client.session.get_expire_at_browser_close() is True


@pytest.mark.django_db
def test_partial_answers(client):
    r = client.post("/ru/questionnaire/", {"speech_01": "3"})
    html = client.get(r["Location"]).content.decode()
    assert "баллов: 3 из 36" in html
    assert "ответов: 1 из 12" in html
    assert "нет ответов" in html
    assert NEUTRAL in _section_html(html, "top-sections")


@pytest.mark.django_db
def test_tie_lists_both_sections_in_order(client):
    data = {k: "2" for k in SCALE_KEYS if k.startswith(("speech_", "social_"))}
    html = client.get(client.post("/ru/questionnaire/", data)["Location"]).content.decode()
    top = _section_html(html, "top-sections")
    a, b = "Речевое развитие и коммуникация", "Социальное взаимодействие"
    assert a in top and b in top
    assert top.index(a) < top.index(b)


@pytest.mark.django_db
def test_result_without_session(client):
    r = client.get("/ru/questionnaire/result/")
    html = r.content.decode()
    assert r.status_code == 200
    assert "Вы ещё не прошли опросник." in html
    assert "Рекомендация по результатам опросника" in html
    assert "specialist_type_ids" not in html
    assert NEW_DISCLAIMER not in html


@pytest.mark.django_db
def test_post_empty(client):
    r = client.post("/ru/questionnaire/", {})
    html = client.get(r["Location"]).content.decode()
    assert "Вы не ответили ни на одно утверждение со шкалой." in html
    assert "Рекомендация по результатам опросника" in html
    assert "specialist_type_ids" not in html
    assert NEW_DISCLAIMER not in html


@pytest.mark.django_db
def test_all_zero(client):
    r = client.post("/ru/questionnaire/", ALL_ZERO)
    html = client.get(r["Location"]).content.decode()
    assert "Во всех разделах 0 баллов." in html
    assert "Баллы по разделам" in html
    assert 'id="top-sections"' not in html
    assert NEUTRAL in html
    assert "Наивысший балл" not in html


@pytest.mark.django_db
def test_post_redirects_to_result(client):
    r = client.post("/ru/questionnaire/", {"speech_01": "2"})
    assert r.status_code == 302 and r["Location"] == "/ru/questionnaire/result/"


def test_result_lists_recommended_types_in_order(client, reference, monkeypatch):
    order = ("child-psychologist", "logoped", "defectologist")  # differs from DB/seed order
    monkeypatch.setattr("apps.questionnaire.views.RECOMMENDED_TYPE_SLUGS", order)
    r = client.get(client.post("/ru/questionnaire/", {"speech_01": "2"})["Location"])
    html = r.content.decode()
    ids = [SpecialistType.objects.get(slug=s).id for s in order]
    positions = [html.index(f"/ru/specialists/?specialist_type_ids={i}") for i in ids]
    assert positions == sorted(positions)
    assert "Логопед" in html and "Детский психолог" in html
    assert "(Это не является медицинской диагностикой, а носит рекомендательный характер.)" in html
    assert PLAQUE in html
    assert html.index(PLAQUE) < html.index("specialist_type_ids")


@pytest.mark.django_db
def test_result_without_reference_data(client):
    r = client.get(client.post("/ru/questionnaire/", {"speech_01": "2"})["Location"])
    assert r.status_code == 200
    assert "Список специалистов временно недоступен." in r.content.decode()


@pytest.mark.django_db
def test_result_not_caught_by_landing(client):
    r = client.get("/ru/questionnaire/result/")
    assert "questionnaire/result.html" in [t.name for t in r.templates]


@pytest.mark.django_db
def test_kk_form_translated(client):
    r = client.get("/kk/questionnaire/")
    html = r.content.decode()
    assert r.status_code == 200
    assert "Речевое развитие и коммуникация" not in html and "Никогда" not in html
    assert html.count('type="radio"') == 264
    assert "Ешқашан" in html
    assert "Раздел 1 из 6" not in html and "Далее" not in html
    assert "Бөлім 1 / 6" in html and "Келесі" in html


@pytest.mark.django_db
def test_kk_result_translated(client):
    r = client.get(client.post("/kk/questionnaire/", {"speech_01": "2"})["Location"])
    html = r.content.decode()
    assert r.status_code == 200
    assert "Рекомендация по результатам опросника" not in html
    assert "(Это не является медицинской диагностикой, а носит рекомендательный характер.)" not in html
    assert "Сауалнама нәтижелері бойынша ұсыным" in html
    assert "ұсынымдық сипатта" in html
    assert "Наивысший балл" not in html and "баллов:" not in html


def test_kk_home_button(client, catalog_fixture):
    html = client.get("/kk/").content.decode()
    assert 'href="/kk/questionnaire/"' in html
    assert "Не знаете, к кому идти? Пройдите опросник" not in html
    assert "Кімге баруды білмейсіз бе? Сауалнамадан өтіңіз" in html
