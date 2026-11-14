from apps.onboarding.models import Application
from tests.factories import SpecialistFactory, UserFactory
from tests.onboarding.conftest import pdf


def test_specialist_cabinet_shows_draft_status(client, specialist_user):
    client.force_login(specialist_user)
    html = client.get("/ru/cabinet/").content.decode()
    assert "Черновик" in html and "Отправить на проверку" in html and "Скан диплома" in html
    assert "Добавить ребёнка" not in html


def test_specialist_cannot_add_children(client, specialist_user):
    client.force_login(specialist_user)
    assert client.get("/ru/cabinet/children/add/").headers["Location"] == "/ru/cabinet/"


def test_parent_cabinet_unchanged(client, db):
    client.force_login(UserFactory())
    assert "Добавить ребёнка" in client.get("/ru/cabinet/").content.decode()
    assert not Application.objects.exists()


def test_profile_without_application_links_to_catalog(client, db):
    profile = SpecialistFactory()
    profile.user.role = "specialist"
    profile.user.save()
    client.force_login(profile.user)
    html = client.get("/ru/cabinet/").content.decode()
    assert f"/ru/specialist/{profile.slug}/" in html
    assert not Application.objects.exists()


def test_save_draft_with_partial_data(client, specialist_user, reference, kato_demo):
    client.force_login(specialist_user)
    client.get("/ru/cabinet/")
    r = client.post("/ru/cabinet/application/", {"bio": "Логопед", "age_min": "3"})
    assert r.headers["Location"] == "/ru/cabinet/"
    app = Application.objects.get(user=specialist_user)
    assert app.bio == "Логопед" and app.age_min == 3 and app.status == "draft"


def test_form_rejects_reversed_age_range(client, specialist_user):
    client.force_login(specialist_user)
    client.get("/ru/cabinet/")
    r = client.post("/ru/cabinet/application/", {"age_min": "10", "age_max": "3"})
    assert r.status_code == 200


def test_nanny_form_has_no_specialist_fields(client, nanny_user, reference):
    client.force_login(nanny_user)
    client.get("/ru/cabinet/")
    html = client.get("/ru/cabinet/application/").content.decode()
    assert 'name="price_hour"' in html and 'name="criminal_record_issued_on"' in html
    assert 'name="specialist_types"' not in html and 'name="price_session"' not in html


def test_upload_document_and_owner_only_access(client, specialist_user):
    client.force_login(specialist_user)
    client.get("/ru/cabinet/")
    r = client.post("/ru/cabinet/application/documents/add/", {"kind": "diploma", "file": pdf()})
    assert r.headers["Location"] == "/ru/cabinet/"
    doc = Application.objects.get(user=specialist_user).documents.get()
    assert doc.content_type == "application/pdf"
    r = client.get(f"/ru/cabinet/application/documents/{doc.pk}/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    client.force_login(UserFactory())
    assert client.get(f"/ru/cabinet/application/documents/{doc.pk}/").status_code == 404


def test_upload_rejects_non_document(client, specialist_user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client.force_login(specialist_user)
    client.get("/ru/cabinet/")
    fake = SimpleUploadedFile("x.pdf", b"<html>", content_type="application/pdf")
    r = client.post("/ru/cabinet/application/documents/add/", {"kind": "diploma", "file": fake})
    assert r.status_code == 200 and "Загрузите PDF, JPG или PNG" in r.content.decode()


def test_nanny_adds_course(client, nanny_user):
    client.force_login(nanny_user)
    client.get("/ru/cabinet/")
    client.post(
        "/ru/cabinet/application/courses/add/",
        {"title": "Уход", "issuer": "Центр", "year": "2025", "hours": "40", "certificate_number": "N-1", "is_first_aid": "on"},
    )
    assert Application.objects.get(user=nanny_user).courses.get().is_first_aid


def test_submit_incomplete_is_refused(client, specialist_user):
    client.force_login(specialist_user)
    client.get("/ru/cabinet/")
    r = client.post("/ru/cabinet/application/submit/")
    assert r.status_code == 200
    assert Application.objects.get(user=specialist_user).status == "draft"


def test_submit_ready_shows_wait_for_call(client, ready_specialist):
    client.force_login(ready_specialist.user)
    assert client.post("/ru/cabinet/application/submit/").headers["Location"] == "/ru/cabinet/"
    ready_specialist.refresh_from_db()
    assert ready_specialist.status == "submitted"
    html = client.get("/ru/cabinet/").content.decode()
    assert "ожидайте звонка" in html
    # A submitted application is read-only for the applicant.
    assert client.get("/ru/cabinet/application/").headers["Location"] == "/ru/cabinet/"
