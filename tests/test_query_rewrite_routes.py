from src.legal_case_rag.retrieval.llm_query_rewriter import LlmQueryRewrite
from src.legal_case_rag.retrieval.query_profile import build_query_profile, build_query_routes


def routes_by_name(routes):
    return {route.name: route for route in routes}


def test_llm_rewrite_reuses_existing_route_names():
    profile = build_query_profile("法院如何认定事实买卖合同成立？")

    default_routes = build_query_routes(profile)
    rewrite_routes = build_query_routes(
        profile,
        LlmQueryRewrite(
            expanded_query="事实买卖合同成立 微信对账 发票抵扣",
            legal_issue="无书面合同 根据履行行为认定事实买卖合同成立",
            fact_elements="微信对账 增值税发票抵扣 送货单主体不明",
            main_leaf="A1_口头或事实买卖合同成立认定",
            focus_labels=["合同成立与否", "货款给付"],
            used=True,
        ),
    )

    assert [route.name for route in rewrite_routes] == [route.name for route in default_routes]


def test_llm_rewrite_replaces_section_queries_with_aligned_fields():
    profile = build_query_profile("法院如何认定事实买卖合同成立？")
    rewrite = LlmQueryRewrite(
        expanded_query="事实买卖合同成立 微信对账 发票抵扣",
        legal_issue="无书面合同 根据履行行为认定事实买卖合同成立",
        fact_elements="微信对账 增值税发票抵扣 送货单主体不明",
        statutes="合同法第八条",
        main_leaf="A1_口头或事实买卖合同成立认定",
        focus_labels=["合同成立与否", "货款给付"],
        used=True,
    )

    routes = routes_by_name(build_query_routes(profile, rewrite))

    assert routes["bm25_raw"].query == profile.raw_query
    assert routes["vector_raw"].query == profile.raw_query
    assert routes["bm25_focus"].query == rewrite.expanded_query
    assert routes["vector_focus"].query == rewrite.expanded_query
    assert "A1_口头或事实买卖合同成立认定" in routes["bm25_fine_issue"].query
    assert "合同成立与否" in routes["bm25_reasoning"].query
    assert routes["bm25_facts"].query == rewrite.fact_elements
    assert "合同法第八条" in routes["bm25_legal"].query


def test_empty_llm_fields_fall_back_to_rule_queries():
    profile = build_query_profile("法院如何认定事实买卖合同成立？")

    default_routes = build_query_routes(profile)
    rewrite_routes = build_query_routes(profile, LlmQueryRewrite(used=False, fallback_reason="invalid_json"))

    assert [route.__dict__ for route in rewrite_routes] == [route.__dict__ for route in default_routes]
