import legal_case_advisor_web
import legal_rag_web


def route_paths(app):
    return {rule.rule for rule in app.url_map.iter_rules()}


def test_legal_rag_web_registers_page_and_api_routes():
    paths = route_paths(legal_rag_web.app)

    assert "/" in paths
    assert "/api/health" in paths
    assert "/api/search" in paths
    assert "/api/benchmark/evaluate" in paths
    assert "/api/cases/<path:doc_id>" in paths


def test_legal_case_advisor_web_registers_page_and_api_routes():
    paths = route_paths(legal_case_advisor_web.app)

    assert "/" in paths
    assert "/api/health" in paths
    assert "/api/analyze" in paths
    assert "/api/analyze/stream" in paths
    assert "/api/cases/<path:doc_id>" in paths
