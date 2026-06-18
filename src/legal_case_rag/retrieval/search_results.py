from __future__ import annotations

from typing import Any

from .models import ChunkHit


def build_context(full_text: str, char_start: int | None, char_end: int | None, window: int) -> str:
    if not full_text:
        return ""
    start = 0 if char_start is None else max(0, char_start - window)
    end = len(full_text) if char_end is None else min(len(full_text), char_end + window)
    prefix = full_text[start : char_start or start]
    hit = full_text[char_start or start : char_end or end]
    suffix = full_text[char_end or end : end]
    if not hit:
        hit = full_text[start:end]
        prefix = ""
        suffix = ""
    return compact_text(prefix) + "【命中】" + compact_text(hit) + "【/命中】" + compact_text(suffix)

def compact_text(text: str, limit: int | None = None) -> str:
    cleaned = " ".join(text.replace("\u3000", " ").split())
    if limit is not None and len(cleaned) > limit:
        return cleaned[: limit - 1] + "…"
    return cleaned

def build_result_entry(
    case_hit: dict[str, Any],
    case_doc: dict[str, Any],
    show_context: bool,
    context_window: int,
    include_full_text: bool = False,
) -> dict[str, Any]:
    full_text = case_doc.get("full_text", "")
    case_doc_payload = {
        "doc_id": case_doc.get("doc_id") or case_hit.get("doc_id") or "",
        "case_name": case_doc.get("case_name") or case_hit.get("case_name") or "",
        "reason": case_doc.get("reason") or case_hit.get("reason") or "",
        "trial_level": case_doc.get("trial_level") or case_hit.get("trial_level") or "",
        "court_name": case_doc.get("court_name") or case_hit.get("court_name") or "",
        "judge_date": case_doc.get("judge_date") or case_hit.get("judge_date") or "",
        "publish_date": case_doc.get("publish_date") or "",
        "litigants": case_doc.get("litigants") or [],
        "statutes": case_doc.get("statutes") or [],
        "full_text_hash": case_doc.get("full_text_hash") or "",
    }
    if include_full_text:
        case_doc_payload["full_text"] = full_text

    matched_chunks: list[dict[str, Any]] = []
    for chunk in case_hit["matched_chunks"]:
        chunk_payload = chunk.to_dict()
        if show_context:
            chunk_payload["context_text"] = build_context(
                full_text,
                chunk.char_start,
                chunk.char_end,
                context_window,
            )
        else:
            chunk_payload["context_text"] = ""
        matched_chunks.append(chunk_payload)

    return {
        **{
            key: value
            for key, value in case_hit.items()
            if key not in {"matched_chunks", "_rerank_chunks"}
        },
        "matched_chunks": matched_chunks,
        "case_doc": case_doc_payload,
    }
