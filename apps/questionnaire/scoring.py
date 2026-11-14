from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .questions import SECTIONS, Section

SCALE_VALUES: frozenset[str] = frozenset({"0", "1", "2", "3"})
MAX_POINTS = 3


@dataclass(frozen=True)
class SectionScore:
    section: Section
    total: int
    answered: int

    @property
    def max_total(self) -> int:
        return MAX_POINTS * len(self.section.questions)

    @property
    def ratio(self) -> float:
        return self.total / self.max_total


def scale_sections() -> tuple[Section, ...]:
    return tuple(
        s for s in SECTIONS if s.questions and all(q.kind == "scale" for q in s.questions)
    )


def score_answers(data: Mapping[str, str]) -> list[SectionScore]:
    scores = []
    for section in scale_sections():
        total = answered = 0
        for question in section.questions:
            value = data.get(question.key)
            if value in SCALE_VALUES:
                total += int(value)
                answered += 1
        scores.append(SectionScore(section, total, answered))
    return scores


def top_sections(scores: Sequence[SectionScore]) -> list[SectionScore]:
    """Sections with the highest total/max ratio; empty if nothing scored above 0."""
    best = max((s.ratio for s in scores), default=0.0)
    if best <= 0:
        return []
    return [s for s in scores if s.ratio == best]


def to_session(scores: Sequence[SectionScore]) -> dict[str, list[int]]:
    return {s.section.key: [s.total, s.answered] for s in scores}


def _valid_pair(value: object, section: Section) -> tuple[int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    total, answered = value
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (total, answered)):
        return None
    if not 0 <= answered <= len(section.questions):
        return None
    if not 0 <= total <= MAX_POINTS * answered:
        return None
    return total, answered


def from_session(raw: object) -> list[SectionScore] | None:
    if not isinstance(raw, dict):
        return None
    scores = []
    for section in scale_sections():
        total, answered = _valid_pair(raw.get(section.key), section) or (0, 0)
        scores.append(SectionScore(section, total, answered))
    return scores
