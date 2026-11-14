from apps.questionnaire.scoring import (
    from_session,
    scale_sections,
    score_answers,
    to_session,
    top_sections,
)


def _answers(**sections):
    data = {}
    for sec, value in sections.items():
        count = len(next(s for s in scale_sections() if s.key == sec).questions)
        for n in range(1, count + 1):
            data[f"{sec}_{n:02d}"] = value
    return data


def _top(data):
    return [s.section.key for s in top_sections(score_answers(data))]


def _by_key(scores):
    return {s.section.key: s for s in scores}


def test_top_is_section_with_all_often():
    d = _answers(speech="0", cognitive="0", emotional="0", social="0", selfcare="0", motor="3")
    scores = score_answers(d)
    assert [s.section.key for s in top_sections(scores)] == ["motor"]
    motor = _by_key(scores)["motor"]
    assert motor.total == 30 and motor.max_total == 30


def test_tie_returns_both_in_order():
    assert _top(_answers(speech="2", social="2")) == ["speech", "social"]


def test_ratio_not_sum():
    assert _top(_answers(selfcare="3", cognitive="2")) == ["selfcare"]


def test_ratio_uses_section_max():
    d = _answers(motor="2")
    d["speech_01"] = "3"
    scores = score_answers(d)
    assert [s.section.key for s in top_sections(scores)] == ["motor"]
    assert _by_key(scores)["speech"].max_total == 36


def test_invalid_values_ignored():
    d = {"speech_01": "5", "speech_02": "abc", "speech_03": "", "speech_04": "3"}
    speech = _by_key(score_answers(d))["speech"]
    assert speech.total == 3 and speech.answered == 1


def test_no_answers():
    scores = score_answers({})
    assert top_sections(scores) == []
    assert len(scores) == 6 and all(s.answered == 0 for s in scores)


def test_all_zero():
    d = _answers(speech="0", cognitive="0", emotional="0", social="0", motor="0", selfcare="0")
    assert len(d) == 66
    assert top_sections(score_answers(d)) == []


def test_session_roundtrip():
    scores = score_answers(_answers(speech="2", motor="1"))
    restored = from_session(to_session(scores))
    assert [(s.section.key, s.total, s.answered) for s in restored] == [
        (s.section.key, s.total, s.answered) for s in scores
    ]
    assert from_session("x") is None
    bad = from_session({"speech": [99, 1], "unknown": [1, 1]})
    assert len(bad) == 6
    speech = _by_key(bad)["speech"]
    assert (speech.total, speech.answered) == (0, 0)
