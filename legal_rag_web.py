from __future__ import annotations

import os
import time
from types import SimpleNamespace
from typing import Any

from flask import Flask, jsonify, render_template, request

from src.legal_case_rag.app import benchmark_service as benchmark
from src.legal_case_rag.app.search_args import (
    build_search_args as build_shared_search_args,
    normalize_sequence,
)
from src.legal_case_rag.retrieval import search as retrieval
from src.legal_case_rag.runtime.env import load_project_env


load_project_env()

app = Flask(__name__)


def build_search_args(payload: dict[str, Any]) -> SimpleNamespace:
    return build_shared_search_args(
        payload,
        default_config=default_frontend_config(),
        retrieval_module=retrieval,
        verify_ssl_default=False,
    )


def public_case_payload(case_doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": case_doc.get("doc_id") or "",
        "case_name": case_doc.get("case_name") or "",
        "reason": case_doc.get("reason") or "",
        "trial_level": case_doc.get("trial_level") or "",
        "court_name": case_doc.get("court_name") or "",
        "judge_date": case_doc.get("judge_date") or "",
        "publish_date": case_doc.get("publish_date") or "",
        "litigants": normalize_sequence(case_doc.get("litigants")),
        "statutes": normalize_sequence(case_doc.get("statutes")),
        "full_text_hash": case_doc.get("full_text_hash") or "",
        "full_text": case_doc.get("full_text") or "",
    }


def default_frontend_config() -> dict[str, Any]:
    return {
        "mode": "hybrid",
        "rerank": True,
        "query_profile": True,
        "query_profile_boost": True,
        "llm_query_rewrite": True,
        "top_k": 8,
        "chunk_top_k": 3,
        "candidate_size": 80,
        "show_context": True,
        "context_window": 180,
        "rerank_top_n": 30,
        "rerank_model_weight": retrieval.CASE_RERANK_MODEL_WEIGHT,
        "rerank_min_interval_ms": retrieval.DEFAULT_RERANK_MIN_INTERVAL_MS,
        "rerank_max_retries": retrieval.DEFAULT_RERANK_MAX_RETRIES,
        "rerank_rank_safe": retrieval.DEFAULT_RERANK_RANK_SAFE,
        "rerank_max_rank_promotion": retrieval.DEFAULT_RERANK_MAX_RANK_PROMOTION,
        "section_type": "",
        "reason": "",
        "trial_level": "",
        "court_name": "",
        "judge_date_from": "",
        "judge_date_to": "",
        "embedding_model": retrieval.DEFAULT_EMBEDDING_MODEL,
        "rerank_model": retrieval.DEFAULT_RERANK_MODEL,
        "embedding_url": retrieval.DEFAULT_EMBEDDING_URL,
        "rerank_url": retrieval.DEFAULT_RERANK_URL,
    }


@app.get("/")
def index() -> str:
    return render_template(
        "legal_rag_index.html",
        defaults=default_frontend_config(),
    )


@app.get("/api/health")
def health() -> Any:
    return jsonify(
        {
            "ok": True,
            "opensearch_url": os.getenv("OPENSEARCH_URL", retrieval.DEFAULT_OPENSEARCH_URL),
            "chunk_index": os.getenv("LEGAL_CHUNK_INDEX", retrieval.DEFAULT_CHUNK_INDEX),
            "case_index": os.getenv("LEGAL_CASE_INDEX", retrieval.DEFAULT_CASE_INDEX),
            "has_opensearch_password": bool(
                os.getenv(retrieval.DEFAULT_OPENSEARCH_PASSWORD_ENV)
            ),
            "has_siliconflow_key": bool(os.getenv(retrieval.DEFAULT_EMBEDDING_KEY_ENV)),
            "defaults": default_frontend_config(),
        }
    )


@app.post("/api/search")
def api_search() -> Any:
    payload = request.get_json(silent=True) or {}
    args = build_search_args(payload)
    if not args.query:
        return jsonify({"ok": False, "error": "query 不能为空。"}), 400

    started = time.perf_counter()
    try:
        result = benchmark.run_retrieval(args)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    duration_ms = int((time.perf_counter() - started) * 1000)
    for item in result.get("results", []):
        case_doc = item.get("case_doc", {})
        case_doc["litigants"] = normalize_sequence(case_doc.get("litigants"))
        case_doc["statutes"] = normalize_sequence(case_doc.get("statutes"))

    result["ok"] = True
    result["duration_ms"] = duration_ms
    result["result_count"] = len(result.get("results", []))
    return jsonify(result)


@app.post("/api/benchmark/evaluate")
def api_benchmark_evaluate() -> Any:
    payload = request.get_json(silent=True) or {}
    limit = benchmark.clamp_int(payload.get("limit"), 58, 1, 58)
    top_k = benchmark.clamp_int(payload.get("top_k"), 100, 1, 100)
    candidate_size = benchmark.clamp_int(payload.get("candidate_size"), 300, top_k, 300)
    rerank_top_n = benchmark.clamp_int(payload.get("rerank_top_n"), max(top_k, min(candidate_size, 100)), 1, 150)
    rerank_model_weight = benchmark.clamp_float(
        payload.get("rerank_model_weight"),
        retrieval.CASE_RERANK_MODEL_WEIGHT,
        0.0,
        1.0,
    )
    rerank_min_interval_ms = benchmark.clamp_int(
        payload.get("rerank_min_interval_ms"),
        retrieval.DEFAULT_RERANK_MIN_INTERVAL_MS,
        0,
        10000,
    )
    rerank_max_retries = benchmark.clamp_int(
        payload.get("rerank_max_retries"),
        retrieval.DEFAULT_RERANK_MAX_RETRIES,
        0,
        8,
    )
    rerank_rank_safe = benchmark.bool_value(
        payload.get("rerank_rank_safe"),
        retrieval.DEFAULT_RERANK_RANK_SAFE,
    )
    rerank_max_rank_promotion = benchmark.clamp_int(
        payload.get("rerank_max_rank_promotion"),
        retrieval.DEFAULT_RERANK_MAX_RANK_PROMOTION,
        0,
        100,
    )
    display_top_n = benchmark.clamp_int(payload.get("display_top_n"), min(top_k, 20), 1, min(top_k, 50))
    include_details = benchmark.bool_value(payload.get("include_details"), True)
    llm_query_rewrite = benchmark.bool_value(payload.get("llm_query_rewrite"), False)
    methods = benchmark.normalize_benchmark_methods(payload.get("methods"))

    started = time.perf_counter()
    try:
        queries = benchmark.load_benchmark_queries(limit=limit)
        qrels = benchmark.load_benchmark_qrels()
    except Exception as exc:
        return jsonify({"ok": False, "error": f"加载 benchmark 数据失败：{exc}"}), 500

    method_results = {
        method: benchmark.run_benchmark_method(
            method,
            queries=queries,
            qrels=qrels,
            top_k=top_k,
            candidate_size=candidate_size,
            chunk_top_k=2,
            rerank_top_n=rerank_top_n,
            rerank_model_weight=rerank_model_weight,
            rerank_min_interval_ms=rerank_min_interval_ms,
            rerank_max_retries=rerank_max_retries,
            rerank_rank_safe=rerank_rank_safe,
            rerank_max_rank_promotion=rerank_max_rank_promotion,
            llm_query_rewrite=llm_query_rewrite,
            route_weight_overrides={},
            display_top_n=display_top_n,
            include_details=include_details,
        )
        for method in methods
    }
    comparison = benchmark.build_method_comparison(method_results)
    all_errors = [
        {"method": method, **error}
        for method, method_payload in method_results.items()
        for error in method_payload["errors"]
    ]
    successful_methods = {
        method: method_payload
        for method, method_payload in method_results.items()
        if method_payload["queries"]
    }
    if not successful_methods and all_errors:
        first_error = all_errors[0]
        return jsonify(
            {
                "ok": False,
                "error": f"{first_error.get('method')} / {first_error.get('query_id')} 检索失败：{first_error.get('error')}",
                "errors": all_errors,
            }
        ), 500

    duration_ms = int((time.perf_counter() - started) * 1000)
    if "hybrid_rerank" in successful_methods:
        primary_method = "hybrid_rerank"
    elif successful_methods:
        primary_method = next(iter(successful_methods))
    else:
        primary_method = methods[0]
    return jsonify(
        {
            "ok": True,
            "duration_ms": duration_ms,
            "settings": {
                "limit": len(queries),
                "top_k": top_k,
                "candidate_size": candidate_size,
                "rerank_top_n": rerank_top_n,
                "rerank_model_weight": rerank_model_weight,
                "rerank_hybrid_weight": 1.0 - rerank_model_weight,
                "rerank_min_interval_ms": rerank_min_interval_ms,
                "rerank_max_retries": rerank_max_retries,
                "rerank_rank_safe": rerank_rank_safe,
                "rerank_max_rank_promotion": rerank_max_rank_promotion,
                "llm_query_rewrite": llm_query_rewrite,
                "display_top_n": display_top_n,
                "methods": methods,
                "primary_method": primary_method,
                "case_index": os.getenv("LEGAL_CASE_INDEX", retrieval.DEFAULT_CASE_INDEX),
                "chunk_index": os.getenv("LEGAL_CHUNK_INDEX", retrieval.DEFAULT_CHUNK_INDEX),
            },
            "methods": method_results,
            "metrics": method_results[primary_method]["metrics"],
            "queries": method_results[primary_method]["queries"],
            "comparison": comparison,
            "errors": all_errors,
        }
    )


@app.get("/api/cases/<path:doc_id>")
def api_case(doc_id: str) -> Any:
    try:
        case_doc = retrieval.fetch_single_case(
            doc_id=doc_id,
            opensearch_url=os.getenv("OPENSEARCH_URL", retrieval.DEFAULT_OPENSEARCH_URL),
            opensearch_username=os.getenv(
                "OPENSEARCH_USERNAME",
                retrieval.DEFAULT_OPENSEARCH_USERNAME,
            ),
            opensearch_password=os.getenv(retrieval.DEFAULT_OPENSEARCH_PASSWORD_ENV),
            case_index=os.getenv("LEGAL_CASE_INDEX", retrieval.DEFAULT_CASE_INDEX),
            verify_ssl=False,
            timeout=30,
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    if not case_doc:
        return jsonify({"ok": False, "error": "未找到对应文书。"}), 404

    return jsonify({"ok": True, "case": public_case_payload(case_doc)})


if __name__ == "__main__":
    host = os.getenv("LEGAL_RAG_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("LEGAL_RAG_WEB_PORT", "7860"))
    app.run(host=host, port=port, debug=False)
