#!/usr/bin/env python
"""预热 LLM 查询改写缓存：遍历所有 benchmark query，将改写结果保存到缓存文件。

用法:
  python scripts/cache_llm_rewrites.py
  python scripts/cache_llm_rewrites.py --queries data/caselaw-benchmark release/data/queries.jsonl
  python scripts/cache_llm_rewrites.py --cache benchmark_dataset/llm_rewrite_cache.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.legal_case_rag.retrieval.llm_query_rewriter import (
    load_rewrite_cache,
    rewrite_query_with_llm,
    save_rewrite_cache,
)

DEFAULT_QUERIES = Path("data") / "caselaw-benchmark release" / "data" / "queries.jsonl"
DEFAULT_CACHE = Path("benchmark_dataset") / "llm_rewrite_cache.json"


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="预热 LLM 查询改写缓存。")
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES), help="queries.jsonl 路径")
    parser.add_argument("--cache", default=str(DEFAULT_CACHE), help="缓存文件路径")
    args = parser.parse_args()

    queries_path = Path(args.queries)
    cache_path = args.cache

    if not queries_path.exists():
        print(f"错误：queries 文件不存在: {queries_path}")
        return 1

    queries = read_jsonl(queries_path)
    print(f"共 {len(queries)} 条 query")

    # 加载已有缓存
    cache = load_rewrite_cache(cache_path)
    already_cached = sum(
        1 for q in queries if q.get("query_text", "") in cache
    )
    print(f"已有缓存: {already_cached} 条")

    # 逐条调用 LLM（有缓存的会自动跳过）
    new_count = 0
    error_count = 0
    for i, query in enumerate(queries, 1):
        query_text = query.get("query_text", "")
        if not query_text:
            continue
        if query_text in cache:
            continue

        print(f"[{i}/{len(queries)}] 改写中: {query_text[:60]}...")
        rewrite = rewrite_query_with_llm(
            query_text,
            enabled=True,
            cache_path=cache_path,
        )
        if rewrite.used:
            new_count += 1
            print(f"  ✓ expanded_query: {rewrite.expanded_query[:60]}")
        else:
            error_count += 1
            print(f"  ✗ fallback: {rewrite.fallback_reason}")

    # 最终统计
    final_cache = load_rewrite_cache(cache_path)
    print(f"\n完成！缓存共 {len(final_cache)} 条，本次新增 {new_count} 条，失败 {error_count} 条")
    print(f"缓存文件: {cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
