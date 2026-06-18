from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .constants import DEFAULT_CASE_FIELDS, DEFAULT_SOURCE_FIELDS, SECTION_WEIGHTS
from .models import ChunkHit
from .opensearch_client import OpenSearchClient
from .query_profile import extract_negative_tags, extract_outcome_tags
from .utils import normalize_list, safe_float, safe_int


def build_filter_clauses(args: argparse.Namespace) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    if args.reason:
        filters.append(exact_or_phrase_filter("reason", args.reason))
    if args.trial_level:
        filters.append(exact_or_phrase_filter("trial_level", args.trial_level))
    if args.court_name:
        filters.append(exact_or_phrase_filter("court_name", args.court_name))
    if args.section_type:
        filters.append(exact_or_phrase_filter("section_type", args.section_type))

    if args.judge_date_from or args.judge_date_to:
        range_clause: dict[str, Any] = {"range": {"judge_date": {}}}
        if args.judge_date_from:
            range_clause["range"]["judge_date"]["gte"] = args.judge_date_from
        if args.judge_date_to:
            range_clause["range"]["judge_date"]["lte"] = args.judge_date_to
        filters.append(range_clause)
    return filters

def exact_or_phrase_filter(field_name: str, value: str) -> dict[str, Any]:
    return {
        "bool": {
            "should": [
                {"term": {f"{field_name}.keyword": value}},
                {"term": {field_name: value}},
                {"match_phrase": {field_name: value}},
            ],
            "minimum_should_match": 1,
        }
    }

def section_type_filter(section_type: str) -> dict[str, Any]:
    return {"term": {"section_type": section_type}}

def route_filters(base_filters: list[dict[str, Any]], section_type: str = "") -> list[dict[str, Any]]:
    filters = list(base_filters)
    if section_type:
        filters.append(section_type_filter(section_type))
    return filters

def bm25_query_body(query: str, filters: list[dict[str, Any]], size: int) -> dict[str, Any]:
    return {
        "size": size,
        "_source": DEFAULT_SOURCE_FIELDS,
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "chunk_text^3.0",
                                "embedding_text^2.0",
                                "section_title^1.4",
                                "reason^1.8",
                                "case_name^1.2",
                            ],
                            "type": "best_fields",
                        }
                    }
                ],
                "filter": filters,
            }
        },
    }

def vector_query_body(
    vector: list[float],
    filters: list[dict[str, Any]],
    size: int,
) -> dict[str, Any]:
    knn_body: dict[str, Any] = {"vector": vector, "k": size}
    if filters:
        knn_body["filter"] = {"bool": {"filter": filters}}

    return {
        "size": size,
        "_source": DEFAULT_SOURCE_FIELDS,
        "query": {
            "knn": {
                "embedding": knn_body,
            }
        },
    }

def source_to_chunk_hit(hit: dict[str, Any], source_name: str) -> ChunkHit:
    source = hit.get("_source", {})
    chunk_text = source.get("chunk_text", "")
    section_type = source.get("section_type", "")
    return ChunkHit(
        chunk_id=source.get("chunk_id") or hit.get("_id", ""),
        doc_id=source.get("doc_id", ""),
        score=float(hit.get("_score") or 0.0),
        chunk_text=chunk_text,
        section_type=section_type,
        section_title=source.get("section_title", ""),
        case_name=source.get("case_name", ""),
        reason=source.get("reason", ""),
        trial_level=source.get("trial_level", ""),
        court_name=source.get("court_name", ""),
        judge_date=source.get("judge_date", ""),
        char_start=safe_int(source.get("char_start")),
        char_end=safe_int(source.get("char_end")),
        line_start=safe_int(source.get("line_start")),
        line_end=safe_int(source.get("line_end")),
        statutes=normalize_list(source.get("statutes")),
        section_weight=safe_float(source.get("section_weight"), SECTION_WEIGHTS.get(section_type or "", 0.6)),
        negative_tags=extract_negative_tags(chunk_text),
        outcome_tags=extract_outcome_tags(chunk_text),
        match_sources=[source_name],
        raw_scores={source_name: float(hit.get("_score") or 0.0)},
    )

def request_query_embedding(
    query: str,
    api_key: str,
    model: str,
    endpoint: str,
    timeout: int = 60,
) -> list[float]:
    payload = {
        "model": model,
        "input": query,
        "encoding_format": "float",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body)
            embedding = data["data"][0]["embedding"]
            if not isinstance(embedding, list):
                raise RuntimeError("Embedding response missing vector payload.")
            return embedding
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Embedding HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Embedding request failed: {exc}") from exc

def search_bm25(
    client: OpenSearchClient,
    index_name: str,
    query: str,
    filters: list[dict[str, Any]],
    size: int,
) -> list[ChunkHit]:
    body = bm25_query_body(query, filters, size)
    response = client.request("POST", f"/{urllib.parse.quote(index_name)}/_search", body)
    return [source_to_chunk_hit(hit, "bm25") for hit in response.get("hits", {}).get("hits", [])]

def search_vector(
    client: OpenSearchClient,
    index_name: str,
    query: str,
    filters: list[dict[str, Any]],
    size: int,
    api_key: str,
    model: str,
    endpoint: str,
) -> list[ChunkHit]:
    vector = request_query_embedding(query, api_key=api_key, model=model, endpoint=endpoint)
    body = vector_query_body(vector, filters, size)
    response = client.request("POST", f"/{urllib.parse.quote(index_name)}/_search", body)
    return [source_to_chunk_hit(hit, "vector") for hit in response.get("hits", {}).get("hits", [])]

def fetch_case_docs(
    client: OpenSearchClient,
    index_name: str,
    doc_ids: list[str],
) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    missing: list[str] = []

    for doc_id in doc_ids:
        path = (
            f"/{urllib.parse.quote(index_name)}/_doc/"
            f"{urllib.parse.quote(doc_id, safe='')}"
        )
        try:
            response = client.request("GET", path)
        except RuntimeError:
            missing.append(doc_id)
            continue
        if response.get("found"):
            source = response.get("_source", {})
            docs[doc_id] = source
        else:
            missing.append(doc_id)

    if not missing:
        return docs

    search_body = {
        "size": len(missing),
        "_source": DEFAULT_CASE_FIELDS,
        "query": {
            "bool": {
                "should": [
                    {"ids": {"values": missing}},
                    {"terms": {"doc_id.keyword": missing}},
                    {"terms": {"doc_id": missing}},
                ],
                "minimum_should_match": 1,
            }
        },
    }
    response = client.request(
        "POST",
        f"/{urllib.parse.quote(index_name)}/_search",
        search_body,
    )
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        doc_id = source.get("doc_id") or hit.get("_id")
        if doc_id:
            docs[doc_id] = source
    return docs
