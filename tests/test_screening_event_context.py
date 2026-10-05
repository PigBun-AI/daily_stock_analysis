"""Event evidence through real ranking, risk, response, and history paths."""

from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from src.config import Config
from src.services import screening_service
from src.services.screening import pipeline, ranker
from src.services.screening.config import Config as PipelineConfig
from src.services.screening.models import Pick, ScreeningConfig, Strategy
from src.storage import DatabaseManager


@pytest.fixture
def screening_run(monkeypatch):
    DatabaseManager.reset_instance()
    database = DatabaseManager(db_url="sqlite:///:memory:")
    runtime = PipelineConfig(
        llm_model="openai/test-model", llm_api_key="test-key", llm_rank_weight=1,
        llm_candidate_multiplier=2, llm_max_candidates=8, llm_max_retries=0,
        post_analyzers=[], daily_enrich_enabled=False, industry_provider="none",
        portfolio_diversity_enabled=False,
    )
    strategy = Strategy(
        name="event_test", display_name="Event test", description="Test",
        screening=ScreeningConfig(enabled=True, factor_weights={"value": 1}),
    )
    state = {"mode": "fresh", "version": 1, "flag_event": False, "model_fails": False, "calls": [], "prompts": []}
    snapshot = pd.DataFrame([
        {"code": f"00000{index}", "name": f"00000{index}", "price": 10, "change_pct": 0,
         "amount": 200_000_000, "pe_ratio": index + 5, "pb_ratio": 1, "volume_ratio": 1, "turnover_rate": 2}
        for index in range(1, 5)
    ])
    monkeypatch.setattr(screening_service, "_get_screening_status_snapshot", lambda: ({}, True, None))
    monkeypatch.setattr(PipelineConfig, "from_env", lambda: runtime)
    monkeypatch.setattr(pipeline, "load_all_strategies", lambda path: {strategy.name: strategy})
    monkeypatch.setattr(pipeline, "fetch_snapshot_with_fallback", lambda *args, **kwargs: snapshot.copy())
    monkeypatch.setattr(screening_service, "_get_dsa_fetcher_manager", lambda: SimpleNamespace(
        get_stock_name=lambda code, **kwargs: f"Resolved {code}",
    ))
    monkeypatch.setattr(screening_service, "get_dsa_realtime_quote", lambda code: {"price": 10, "change_pct": 0})
    monkeypatch.setattr(screening_service, "get_dsa_fundamental_context", lambda code: {"coverage": {"valuation": "available"}})

    def evidence(kind, code, name, **kwargs):
        state["calls"].append((kind, code, kwargs.get("max_results")))
        if state["mode"] == "failed":
            raise RuntimeError(f"{kind} offline")
        items = []
        if state["mode"] != "empty":
            items = [{
                "title": f"{kind} {code} v{state['version']}",
                "snippet": "监管问询" if code == "000001" else "Routine filing",
                "source": "test-provider", "url": f"https://example.test/{kind}/{code}",
                "published_date": None if state["mode"] == "undated" else datetime.now().date().isoformat(),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }]
        return {"success": True, "results": items}

    def provider_response(kind, *args, **kwargs):
        payload = evidence(kind, *args, **kwargs)
        return SimpleNamespace(
            query="test", provider="test-engine", success=payload["success"],
            results=[SimpleNamespace(**item) for item in payload["results"]],
        )

    search_provider = SimpleNamespace(
        is_available=True,
        search_stock_news=lambda *args, **kwargs: provider_response("news", *args, **kwargs),
        search_stock_events=lambda code, name: provider_response("event", code, name, max_results=3),
    )
    monkeypatch.setattr(screening_service, "_get_dsa_search_service", lambda: search_provider)

    def call_llm(prompt, *args, **kwargs):
        state["calls"].append(("llm", "", None))
        state["prompts"].append(prompt)
        if state["model_fails"]:
            raise RuntimeError("model unavailable")
        codes = [code for code in snapshot["code"] if f"{code} " in prompt]
        return json.dumps({"ranked": [
            {"code": code, "llm_score": 90 - index, "confidence": 0.9, "reason": "Test ranking",
             "risk_flags": ["监管问询"] if state["flag_event"] and code == "000001" else []}
            for index, code in enumerate(codes)
        ]}, ensure_ascii=False)

    monkeypatch.setattr(ranker, "_call_llm", call_llm)
    service = screening_service.ScreeningService(Config(screening_enabled=True), db_manager=database)

    def run(max_results=1):
        return service.screen(
            strategy=strategy.name, market="cn", max_results=max_results,
            progress_callback=lambda progress, message: state["calls"].append(("progress", progress, None)),
        )

    yield SimpleNamespace(run=run, state=state, runtime=runtime, database=database, snapshot=snapshot)
    DatabaseManager.reset_instance()


def test_event_evidence_reaches_llm_then_existing_risk_overlay_and_history(screening_run):
    screening_run.state["flag_event"] = True
    response = screening_run.run()
    prompt = screening_run.state["prompts"][0]
    assert "event_evidence=" in prompt
    assert "监管问询" in prompt
    assert "source=test-provider" in prompt
    assert "published_date=" + datetime.now().date().isoformat() in prompt
    assert "https://example.test/event/000001" in prompt
    calls = screening_run.state["calls"]
    llm_position = next(index for index, call in enumerate(calls) if call[0] == "llm")
    assert all(index < llm_position for index, call in enumerate(calls) if call[0] in {"news", "event"})
    # The model ranks 000001 first by 1 point; its real 1.2-point risk penalty
    # lets 000002 enter the one-stock result, before service-side enrichment.
    selected = response["candidates"][0]
    assert selected["code"] == "000002"
    assert selected["name"] == "Resolved 000002"
    assert selected["dsa_context"]["profile"] == "pre_rank_research"
    assert selected["dsa_events"][0]["title"] == "event 000002 v1"
    assert selected["factor_scores"]
    assert selected["raw"]["factor_scores"] == selected["factor_scores"]
    stored = screening_run.database.get_screening_run(response["run_id"])
    assert stored is not None
    persisted = stored["result"]
    assert persisted["candidates"][0]["dsa_events"] == selected["dsa_events"]


@pytest.mark.parametrize("mode", ["fresh", "empty", "undated", "failed"])
def test_pre_rank_queries_are_not_repeated_after_selection(screening_run, mode):
    screening_run.state["mode"] = mode
    response = screening_run.run()
    calls = screening_run.state["calls"]
    for code in ("000001", "000002"):
        assert calls.count(("news", code, 3)) == 1
        assert calls.count(("event", code, 3)) == 1
    assert response["candidate_count"] == 1
    context = response["candidates"][0]["dsa_context"]
    assert context["news_included"] and context["events_included"]
    prompt = screening_run.state["prompts"][0]
    if mode == "undated":
        assert "published_date=unknown" in prompt
        assert "retrieved_at=unknown" in prompt
    elif mode == "empty":
        assert "event_evidence=no_results" in prompt
    elif mode == "failed":
        assert "event_evidence=unavailable" in prompt
        assert any("event offline" in warning for warning in response["dsa_enrichment"]["warnings"])


def test_pre_rank_queries_respect_existing_candidate_cap(screening_run):
    screening_run.run(max_results=2)
    calls = screening_run.state["calls"]
    for kind in ("news", "event"):
        assert [call[1] for call in calls if call[0] == kind] == ["000001", "000002", "000003"]
    prompt = screening_run.state["prompts"][0]
    assert "000004 " in prompt
    assert "news_evidence=not_collected" in prompt
    assert "未采集、无结果或查询失败均不代表风险已排除" in prompt


def test_factor_fallback_keeps_news_queries_after_selection(screening_run):
    screening_run.runtime.llm_api_key = ""
    response = screening_run.run()
    calls = screening_run.state["calls"]
    assert not screening_run.state["prompts"]
    final_enrichment = next(index for index, call in enumerate(calls) if call[:2] == ("progress", 92))
    assert all(index > final_enrichment for index, call in enumerate(calls) if call[0] in {"news", "event"})
    assert len([call for call in calls if call[0] == "news"]) == 1
    assert response["candidates"][0]["dsa_context"]["profile"] == "post_rank_full"


def test_newly_selected_candidate_outside_pre_rank_cap_is_enriched_once(screening_run, monkeypatch):
    original_call = ranker._call_llm

    def promote_fourth(*args, **kwargs):
        result = json.loads(original_call(*args, **kwargs))
        result["ranked"][-1]["llm_score"] = 99
        return json.dumps(result)

    monkeypatch.setattr(ranker, "_call_llm", promote_fourth)
    response = screening_run.run(max_results=2)
    calls = screening_run.state["calls"]
    final_enrichment = next(index for index, call in enumerate(calls) if call[:2] == ("progress", 92))
    assert [index for index, call in enumerate(calls) if call == ("event", "000004", 3)][0] > final_enrichment
    assert calls.count(("event", "000004", 3)) == 1
    assert calls.count(("event", "000001", 3)) == 1
    selected = response["candidates"][0]
    assert selected["code"] == "000004"
    assert selected["dsa_context"]["profile"] == "post_rank_full"


def test_llm_failure_reuses_pre_rank_queries_for_factor_fallback(screening_run):
    screening_run.state["model_fails"] = True
    response = screening_run.run()
    assert response["llm_ranked"] is False
    for code in ("000001", "000002"):
        assert screening_run.state["calls"].count(("event", code, 3)) == 1
    assert response["candidates"][0]["dsa_context"]["events_included"] is True


def test_context_cache_is_private_to_each_run(screening_run):
    first = screening_run.run()
    screening_run.state["version"] = 2
    second = screening_run.run()
    assert first["candidates"][0]["dsa_events"][0]["title"].endswith("v1")
    assert second["candidates"][0]["dsa_events"][0]["title"].endswith("v2")
    assert screening_run.state["calls"].count(("event", "000001", 3)) == 2


def test_bounded_prompt_keeps_candidate_identity_with_large_event_payloads():
    picks = [Pick(rank=index, code=f"00000{index}", name=f"Stock {index}", final_score=90, screen_score=90)
             for index in (1, 2)]
    for pick in picks:
        pick.dsa_context = {"events": {"success": True, "results": [
            {"title": "t" * 5000, "snippet": "s" * 5000, "url": "u" * 5000,
             "source": "p" * 5000, "published_date": None}
            for _ in range(10)
        ]}}
        evidence = ranker._format_dsa_evidence_for_prompt(pick.dsa_context["events"])
        assert len(evidence) < 1800
        assert evidence.count("published_date=unknown") == 3
    degradation = []
    prompt = ranker._build_ranking_prompt(picks, "", "", max_chars=3000, degradation=degradation)
    assert len(prompt) <= 3000
    assert all(pick.code in prompt for pick in picks)
    assert degradation
