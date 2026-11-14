import re

from apps.questionnaire.questions import RECOMMENDED_TYPE_SLUGS, SCALE, SECTIONS

REVERSE_KEYS = {
    "speech_12", "cognitive_12", "cognitive_13",
    "emotional_08", "emotional_09", "emotional_10", "emotional_11", "emotional_12",
    "social_10", "social_11",
    "motor_06", "motor_07", "motor_08", "motor_09", "motor_10",
    "selfcare_08",
}


def test_sections_and_counts():
    assert [s.key for s in SECTIONS] == ["general", "speech", "cognitive", "emotional", "social", "motor", "selfcare", "parents"]
    assert [len(s.questions) for s in SECTIONS] == [4, 12, 13, 12, 11, 10, 8, 6]


def test_keys_unique_and_formatted():
    keys = [q.key for s in SECTIONS for q in s.questions]
    assert len(keys) == len(set(keys)) == 76
    for s in SECTIONS:
        for n, q in enumerate(s.questions, 1):
            assert q.key == f"{s.key}_{n:02d}" and re.fullmatch(r"[a-z]+_\d{2}", q.key)


def test_scale_sections_have_hint_and_only_scale():
    by_key = {s.key: s for s in SECTIONS}
    for key in ["speech", "cognitive", "emotional", "social", "motor", "selfcare"]:
        assert str(by_key[key].hint) == "Оцените следующие утверждения:"
        assert {q.kind for q in by_key[key].questions} == {"scale"}
    for key in ["general", "parents"]:
        assert str(by_key[key].hint) == "" and "scale" not in {q.kind for q in by_key[key].questions}


def test_general_has_no_personal_fields():
    general = SECTIONS[0].questions
    assert [q.kind for q in general] == ["textarea"] * 4
    all_texts = {str(q.text) for s in SECTIONS for q in s.questions}
    assert not all_texts & {"Ф.И.О. ребёнка", "Дата рождения", "Возраст"}
    assert {q.kind for q in SECTIONS[-1].questions} == {"textarea"}


def test_reverse_keys():
    assert {q.key for s in SECTIONS for q in s.questions if q.reverse} == REVERSE_KEYS


def test_texts_from_document():
    texts = {q.key: str(q.text) for s in SECTIONS for q in s.questions}
    assert texts["general_01"] == "Посещает ли ребёнок образовательное учреждение?"
    assert texts["general_04"] == "Какие специалисты уже работали с ребёнком?"
    assert texts["speech_01"] == "Ребёнок понимает обращённую к нему речь."
    assert texts["speech_08"] == "Различает и правильно использует слова по смыслу."
    assert texts["emotional_10"] == "Может причинять вред себе (бьёт себя, кусает, ударяется)."
    assert texts["parents_06"] == "Какой результат от коррекционных занятий вы хотели бы получить?"


def test_scale_and_recommendation():
    assert [(v, str(label)) for v, label in SCALE] == [(0, "Никогда"), (1, "Редко"), (2, "Иногда"), (3, "Часто")]
    assert RECOMMENDED_TYPE_SLUGS == ("logoped", "defectologist", "child-psychologist")
