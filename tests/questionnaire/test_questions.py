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
    assert [s.key for s in SECTIONS] == ["speech", "cognitive", "emotional", "social", "motor", "selfcare"]
    assert [len(s.questions) for s in SECTIONS] == [12, 13, 12, 11, 10, 8]


def test_keys_unique_and_formatted():
    keys = [q.key for s in SECTIONS for q in s.questions]
    assert len(keys) == len(set(keys)) == 66
    for s in SECTIONS:
        for n, q in enumerate(s.questions, 1):
            assert q.key == f"{s.key}_{n:02d}" and re.fullmatch(r"[a-z]+_\d{2}", q.key)


def test_scale_sections_have_hint_and_only_scale():
    for section in SECTIONS:
        assert str(section.hint) == "Оцените следующие утверждения:"
        assert {q.kind for q in section.questions} == {"scale"}


def test_no_text_sections():
    assert not {"general", "parents"} & {s.key for s in SECTIONS}
    titles = {str(s.title) for s in SECTIONS}
    assert not titles & {"Общая информация", "Дополнительная информация от родителей"}


def test_reverse_keys():
    assert {q.key for s in SECTIONS for q in s.questions if q.reverse} == REVERSE_KEYS


def test_texts_from_document():
    texts = {q.key: str(q.text) for s in SECTIONS for q in s.questions}
    assert texts["speech_01"] == "Ребёнок понимает обращённую к нему речь."
    assert texts["speech_08"] == "Различает и правильно использует слова по смыслу."
    assert texts["emotional_10"] == "Может причинять вред себе (бьёт себя, кусает, ударяется)."


def test_scale_and_recommendation():
    assert [(v, str(label)) for v, label in SCALE] == [(0, "Никогда"), (1, "Редко"), (2, "Иногда"), (3, "Часто")]
    assert RECOMMENDED_TYPE_SLUGS == ("logoped", "defectologist", "child-psychologist")
