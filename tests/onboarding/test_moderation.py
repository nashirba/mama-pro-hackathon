import pytest
from django.core.exceptions import ValidationError

from apps.onboarding import services
from apps.onboarding.models import BlockedPhone
from apps.search.models import SearchOffer
from apps.search.query import SearchParams, search


def _submitted(app):
    services.submit(app)
    return app


def test_approve_specialist_puts_profile_in_catalog(client, ready_specialist, staff, django_capture_on_commit_callbacks):
    app = _submitted(ready_specialist)
    with django_capture_on_commit_callbacks(execute=True):
        profile = services.approve(app, staff)
    app.refresh_from_db()
    assert app.status == "approved" and app.profile == profile and app.decided_by == staff
    assert profile.display_name == "Серикова Алия" and profile.slug == "aliya-serikova"
    assert profile.whatsapp_phone == app.user.phone
    assert list(profile.specialist_types.values_list("slug", flat=True)) == ["logoped"]
    assert SearchOffer.objects.filter(specialist=profile).count() == 2  # in person + online
    assert profile.slug in {c.specialist.slug for c in search(SearchParams()).cards}
    html = client.get(f"/ru/specialist/{profile.slug}/").content.decode()
    assert "Проверено Мама Про" in html
    assert profile.demo_verification_levels == ["identity", "education", "credential", "safety"]


def test_approve_nanny_is_shown_in_nannies(client, ready_nanny, staff, django_capture_on_commit_callbacks):
    app = _submitted(ready_nanny)
    with django_capture_on_commit_callbacks(execute=True):
        profile = services.approve(app, staff)
    assert profile.is_nanny and profile.trainings.get().is_first_aid
    r = client.get("/ru/nannies/")
    assert profile.slug in {c.specialist.slug for c in r.context["result"].cards}


def test_needs_changes_returns_to_applicant(client, ready_specialist, staff):
    app = _submitted(ready_specialist)
    services.request_changes(app, "Загрузите приложение к диплому", staff)
    assert app.status == "needs_changes" and app.is_editable
    client.force_login(app.user)
    html = client.get("/ru/cabinet/").content.decode()
    assert "Загрузите приложение к диплому" in html and "Нужна доработка" in html
    services.submit(app)
    assert app.status == "submitted"


def test_reject_blocks_phone(client, ready_specialist, staff):
    app = _submitted(ready_specialist)
    services.reject(app, "Документы не подтвердились", staff)
    assert app.status == "rejected"
    assert BlockedPhone.objects.filter(phone=app.user.phone).exists()
    client.force_login(app.user)
    html = client.get("/ru/cabinet/").content.decode()
    assert "Подать новую анкету с этого номера нельзя" in html
    assert client.post("/ru/cabinet/application/submit/").status_code == 200
    app.refresh_from_db()
    assert app.status == "rejected"


def test_decision_only_on_submitted(ready_specialist, staff):
    with pytest.raises(ValidationError):
        services.approve(ready_specialist, staff)
    with pytest.raises(ValidationError):
        services.reject(ready_specialist, "нет", staff)


def test_admin_queue_and_decision(client, ready_specialist, staff, django_capture_on_commit_callbacks):
    _submitted(ready_specialist)
    client.force_login(staff)
    r = client.get("/ru/admin/onboarding/application/?status__exact=submitted")
    assert "Серикова" in r.content.decode()
    url = f"/ru/admin/onboarding/application/{ready_specialist.pk}/change/"
    page = client.get(url).content.decode()
    assert f"/ru/cabinet/application/documents/{ready_specialist.documents.get().pk}/" in page
    # A rejection without a reason is refused.
    doc_id = str(ready_specialist.documents.get().pk)
    r = client.post(url, {"decision": "reject", "moderator_comment": "", "documents-TOTAL_FORMS": "1", "documents-0-id": doc_id,
                          "documents-INITIAL_FORMS": "1", "courses-TOTAL_FORMS": "0", "courses-INITIAL_FORMS": "0"})
    assert r.status_code == 200
    ready_specialist.refresh_from_db()
    assert ready_specialist.status == "submitted"
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"decision": "approve", "moderator_comment": "",
                          "documents-TOTAL_FORMS": "1", "documents-INITIAL_FORMS": "1", "documents-0-id": doc_id,
                          "courses-TOTAL_FORMS": "0", "courses-INITIAL_FORMS": "0"})
    ready_specialist.refresh_from_db()
    assert ready_specialist.status == "approved"
    assert ready_specialist.profile.demo_verification_levels == ["identity", "education", "credential", "safety"]
    # Staff can open the document.
    doc = ready_specialist.documents.get()
    assert client.get(f"/ru/cabinet/application/documents/{doc.pk}/").status_code == 200
