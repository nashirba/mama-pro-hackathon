import pytest
from django.core.management import call_command

from apps.catalog.models import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Method,
    ServiceKind,
    SpecialistType,
)
from apps.core.text import normalize_kk
from apps.geo.models import KatoNode


def test_seed_is_idempotent(db):
    call_command("seed_reference_data")
    counts = (SpecialistType.objects.count(), DevelopmentalCondition.objects.count(), Method.objects.count(), ServiceKind.objects.count(), CommunicationLanguage.objects.count())
    call_command("seed_reference_data")
    assert counts == (29, 26, 30, 6, 3)
    assert (SpecialistType.objects.count(), DevelopmentalCondition.objects.count(), Method.objects.count(), ServiceKind.objects.count(), CommunicationLanguage.objects.count()) == counts


def test_condition_groups_and_no_diagnosis_option(db, reference):
    groups = set(DevelopmentalCondition.objects.filter(parent__isnull=True).values_list("slug", flat=True))
    assert groups == {"hearing-impairment", "vision-impairment", "intellectual-impairment", "zpr", "speech-impairment",
                      "motor-impairment", "emotional-volitional", "complex-impairment", "general"}
    nd = DevelopmentalCondition.objects.get(is_no_diagnosis=True)
    assert nd.slug == "no-diagnosis" and nd.parent.slug == "general"
    assert not DevelopmentalCondition.objects.filter(translations__name__icontains="ограниченными возможностями").exists()


@pytest.mark.parametrize("child,parent", [("ras", "emotional-volitional"), ("zrr", "speech-impairment"),
    ("cerebral-palsy", "motor-impairment"), ("epilepsy", "general")])
def test_condition_parent_mapping(db, reference, child, parent):
    assert DevelopmentalCondition.objects.get(slug=child).parent.slug == parent


def test_method_evidence_levels(db, reference):
    level = lambda slug: Method.objects.get(slug=slug).evidence_level
    assert level("aba") == "established"
    assert level("music-therapy") == "limited"                       # 🟢/🟡: худший цвет
    assert level("tomatis") == "not_established_or_harmful"
    assert level("montessori") == "not_therapy"


def test_method_evidence_level_counts(db, reference):
    counts = {level: Method.objects.filter(evidence_level=level).count() for level in Method.EvidenceLevel.values}
    assert counts == {"established": 10, "limited": 7, "not_established_or_harmful": 12, "not_therapy": 1}


def test_kk_fallback_to_ru_when_missing(db, reference):
    # every reference row has a KZ name now, so the fallback is checked on rows that only have RU
    m = Method.objects.language("ru").create(slug="only-ru-method", evidence_level="established", name="Тестовый метод")
    m = Method.objects.language("kk").get(slug="only-ru-method")
    assert not m.has_translation("kk")
    assert m.get_current_language() == "kk"
    assert m.name == "Тестовый метод"
    t = SpecialistType.objects.language("ru").create(slug="only-ru-type", name="Тип", name_plural="Типы", landing_name="Типы")
    t = SpecialistType.objects.language("kk").get(slug="only-ru-type")
    assert not t.has_translation("kk")
    assert t.name_plural == "Типы"


def test_name_plural_and_landing_name(db, reference):
    assert SpecialistType.objects.language("ru").get(slug="logoped").name_plural == "Логопеды"
    assert SpecialistType.objects.language("kk").get(slug="logoped").name_plural == "Логопедтер"
    ras = DevelopmentalCondition.objects.get(slug="ras")
    assert ras.safe_translation_getter("landing_name", language_code="ru") == "Специалисты по РАС"
    assert ras.safe_translation_getter("landing_name", language_code="kk") == "РАС бойынша мамандар"
    assert all(c.safe_translation_getter("landing_name", language_code="kk") for c in DevelopmentalCondition.objects.filter(translations__language_code="kk"))


def test_specialist_type_landing_name_is_in_title_case(db, reference):
    landing = lambda slug, lang: SpecialistType.objects.get(slug=slug).safe_translation_getter("landing_name", language_code=lang)
    assert landing("logoped", "ru") == "Логопеды"
    assert landing("logoped", "kk") == "логопедтер"
    assert landing("aba-therapist", "kk") == "ABA-терапевттер"  # abbreviation intact
    assert landing("early-support-teacher", "kk") == "ерте қолдау педагогтары"
    assert SpecialistType.objects.language("kk").get(slug="logoped").name_plural == "Логопедтер"  # the filter lists keep the capital
    assert landing("music-therapist", "kk") == "музыкалық терапевтер"


def test_condition_kk_landing_name_case(db, reference):
    landing = lambda slug: DevelopmentalCondition.objects.get(slug=slug).safe_translation_getter("landing_name", language_code="kk")
    assert landing("ras") == "РАС бойынша мамандар"
    assert landing("down-syndrome") == "Даун синдромы бойынша мамандар"
    assert landing("epilepsy") == "эпилепсия бойынша мамандар"
    assert landing("cerebral-palsy").startswith("балалар церебралды")


def test_evidence_level_labels(db, reference):
    labels = {m.evidence_level: m.get_evidence_level_display() for m in Method.objects.all()}
    assert labels == {
        "established": "есть доказательная база",
        "limited": "ограниченная доказательная база",
        "not_established_or_harmful": "нет доказательств эффективности",
        "not_therapy": "педагогическая система, не терапия",
    }


def test_ru_fields_complete_and_kk_rows_filled(db, reference):
    for model, fields in ((SpecialistType, ("name", "name_plural", "landing_name")), (DevelopmentalCondition, ("name", "landing_name"))):
        for obj in model.objects.all():
            for f in fields:
                assert obj.safe_translation_getter(f, language_code="ru"), (obj.slug, f)
            if obj.has_translation("kk"):
                for f in fields:
                    assert obj.safe_translation_getter(f, language_code="kk"), (obj.slug, f)
                if model is DevelopmentalCondition:
                    assert obj.safe_translation_getter("landing_name", language_code="kk") != obj.safe_translation_getter("landing_name", language_code="ru"), obj.slug


@pytest.mark.parametrize("slug,plural", [
    ("defectologist", "Дефектологтар"), ("special-educator", "Арнайы педагогтар"),
    ("oligophrenopedagog", "Олигофренопедагогтар"), ("surdopedagog", "Сурдопедагогтар"),
    ("tiflopedagog", "Тифлопедагогтар"), ("ergopedagog", "Эргопедагогтар"),
    ("early-support-teacher", "Ерте қолдау педагогтары"), ("school-psychologist", "Педагог-психологтар"),
    ("logoped", "Логопедтер"), ("tutor", "Педагог-ассистенттер")])
def test_kk_plural_vowel_harmony(db, reference, slug, plural):
    assert SpecialistType.objects.language("kk").get(slug=slug).name_plural == plural


def test_search_key_normalized_all_languages(db, reference):
    key = DevelopmentalCondition.objects.get(slug="ras").search_key
    assert "аутизм" in key and "аутистикалык" in key      # синоним RU и KZ-имя после normalize_kk


def test_search_key_refreshed_on_translation_and_synonym_change(db, reference):
    logoped = SpecialistType.objects.get(slug="logoped")
    logoped.set_current_language("kk")
    logoped.name = "Сөйлеу маманы"
    logoped.save()
    assert "сойлеу" in SpecialistType.objects.get(slug="logoped").search_key
    logoped.synonyms = "речевик"
    logoped.save()
    assert "речевик" in SpecialistType.objects.get(slug="logoped").search_key


def test_normalize_kk():
    assert normalize_kk("Қарағанды") == normalize_kk("Караганды") == "караганды"
    assert normalize_kk("ӘҒҚҢӨҰҮҺІ") == "агкноуухи"
    assert normalize_kk("ABA-терапевт, аба") == "aba терапевт аба"


def test_landing_slugs_disjoint(db, reference, kato_demo):
    types = set(SpecialistType.objects.values_list("slug", flat=True))
    conditions = set(DevelopmentalCondition.objects.values_list("slug", flat=True))
    cities = set(KatoNode.objects.filter(level=KatoNode.Level.CITY).values_list("slug", flat=True))
    assert cities
    assert not (types & conditions)
    assert not (types & cities)
    assert not (conditions & cities)


def test_nanny_is_not_a_specialist_type(db, reference):
    assert not SpecialistType.objects.filter(slug="nanny").exists()


def test_seed_removes_legacy_nanny_type(db):
    SpecialistType.objects.language("ru").create(slug="nanny", name="Няня или сиделка", name_plural="Няни", landing_name="Няни")
    call_command("seed_reference_data")
    assert not SpecialistType.objects.filter(slug="nanny").exists()


def test_childcare_service_kind(db, reference):
    kind = ServiceKind.objects.get(slug="childcare")
    assert kind.safe_translation_getter("name", language_code="ru") == "Услуги няни"
    assert kind.safe_translation_getter("name", language_code="kk") == "Бала күтуші қызметі"
