from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkHit:
    chunk_id: str
    doc_id: str
    score: float
    chunk_text: str
    section_type: str = ""
    section_title: str = ""
    case_name: str = ""
    reason: str = ""
    trial_level: str = ""
    court_name: str = ""
    judge_date: str = ""
    char_start: int | None = None
    char_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    statutes: list[str] = field(default_factory=list)
    section_weight: float | None = None
    negative_tags: list[str] = field(default_factory=list)
    outcome_tags: list[str] = field(default_factory=list)
    match_sources: list[str] = field(default_factory=list)
    raw_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "score": self.score,
            "chunk_text": self.chunk_text,
            "section_type": self.section_type,
            "section_title": self.section_title,
            "case_name": self.case_name,
            "reason": self.reason,
            "trial_level": self.trial_level,
            "court_name": self.court_name,
            "judge_date": self.judge_date,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "statutes": self.statutes,
            "section_weight": self.section_weight,
            "negative_tags": self.negative_tags,
            "outcome_tags": self.outcome_tags,
            "match_sources": self.match_sources,
            "raw_scores": self.raw_scores,
        }
