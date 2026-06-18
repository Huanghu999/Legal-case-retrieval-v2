# 法律检索系统重构实施计划

> **给自动化执行者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步实施。本计划使用复选框（`- [ ]`）跟踪进度。

**目标：** 将臃肿的入口与检索模块拆成更小、更专注的文件，增加自动 `.env` 加载，并清理无意义的包样板文件。

**架构：** 保留两个 Flask 入口脚本，但把共享运行时逻辑移到独立小模块中。检索层拆分为环境加载、OpenSearch 访问、排序/重排辅助函数和结果格式化，让 `search.py` 只负责编排。

**技术栈：** Python 3.13、Flask、pytest、仅使用标准库解析 `.env`

## Global Constraints

- 保留现有 CLI 和 Flask 入口：`legal_rag_web.py`、`legal_case_advisor_web.py`，以及通过 `src.legal_case_rag` 的 `python -m` 风格导入。
- 密钥不要进 git：`.env` 保持忽略；`.env.example` 提交占位内容。
- 新增配置加载优先使用标准库，不为了 `.env` 新增运行时依赖。
- 只有在导入检查证明命名空间包仍可正常工作后，才删除空的 `__init__.py`。

---

### Task 1: 添加自动 `.env` 加载

**Files:**
- Create: `src/legal_case_rag/runtime/env.py`
- Create: `tests/test_env_loader.py`
- Modify: `legal_rag_web.py`
- Modify: `legal_case_advisor_web.py`
- Create: `.env`
- Create: `.env.example`

**Interfaces:**
- Consumes: `Path`, `os.environ`
- Produces: `load_project_env()`, `load_env_file()`

- [ ] **步骤 1：先写失败测试**

```python
from pathlib import Path

from src.legal_case_rag.runtime.env import load_env_file


def test_load_env_file_sets_missing_values_and_keeps_existing(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("A=one\nB='two words'\nC=three\n", encoding="utf-8")
    monkeypatch.setenv("B", "kept")

    values = load_env_file(env_path)

    assert values == {"A": "one", "B": "two words", "C": "three"}
    assert os.environ["A"] == "one"
    assert os.environ["B"] == "kept"
    assert os.environ["C"] == "three"
```

- [ ] **步骤 2：运行测试，确认它失败**

运行：`pytest tests/test_env_loader.py -v`
预期：失败，因为 `src.legal_case_rag.runtime.env` 还不存在。

- [ ] **步骤 3：写最小实现**

```python
def load_env_file(path: Path | str | None = None, *, override: bool = False) -> dict[str, str]:
    ...
```

- [ ] **步骤 4：运行测试，确认通过**

运行：`pytest tests/test_env_loader.py -v`
预期：通过。

### Task 2: 将检索辅助函数拆成更小模块

**Files:**
- Create: `src/legal_case_rag/retrieval/opensearch_client.py`
- Create: `src/legal_case_rag/retrieval/search_queries.py`
- Create: `src/legal_case_rag/retrieval/search_rerank.py`
- Create: `src/legal_case_rag/retrieval/search_results.py`
- Modify: `src/legal_case_rag/retrieval/search.py`

**Interfaces:**
- Consumes: `ChunkHit`, `QueryProfile`, search constants
- Produces: smaller helper functions imported by `search.py`

- [ ] 将 OpenSearch 请求和查询构造辅助函数移出 `search.py`。
- [ ] 将 rerank 和 guardrail 相关辅助函数移出 `search.py`。
- [ ] 将输出格式化辅助函数移出 `search.py`。
- [ ] 保留 `search.py` 中的 `run_search()`、`parse_args()`、`validate_args()` 和 `main()`。
- [ ] 运行 `python -m py_compile src/legal_case_rag/retrieval/*.py` 并修复导入错误。

### Task 3: 拆分 Web 服务层代码

**Files:**
- Create: `src/legal_case_rag/app/benchmark_service.py`
- Modify: `legal_rag_web.py`

**Interfaces:**
- Consumes: retrieval module, benchmark JSONL files
- Produces: benchmark evaluation helpers and Flask route delegation

- [ ] 将 benchmark 指标与聚合辅助函数移出 `legal_rag_web.py`。
- [ ] 让 Flask 路由处理器保持轻量。
- [ ] 运行 `python -m py_compile legal_rag_web.py src/legal_case_rag/app/*.py`。

### Task 4: 删除无用的包样板文件

**Files:**
- Delete: `src/__init__.py`
- Delete: `src/legal_case_rag/__init__.py`
- Delete: `src/legal_case_rag/retrieval/__init__.py`
- Delete: `src/legal_case_rag/app/__init__.py`
- Delete: `src/legal_case_rag/data_pipeline/__init__.py`

**Interfaces:**
- Consumes: namespace-package imports
- Produces: cleaner package tree

- [ ] 删除空的 `__init__.py` 文件。
- [ ] 运行导入冒烟测试，验证 `src.legal_case_rag.retrieval.search` 和 `src.legal_case_rag.app.advisor_service` 可正常导入。

### Task 5: 验证与收尾

**Files:**
- Modify: `README.md` only if startup instructions need a note

**Interfaces:**
- Consumes: final module layout
- Produces: verified codebase

- [ ] 运行 `pytest -v`。
- [ ] 运行 `python -m py_compile legal_rag_web.py legal_case_advisor_web.py src/legal_case_rag/**/*.py`。
- [ ] 查看 `git status` 并汇总剩余改动。
