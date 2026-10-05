"""Actual aggregation, API projection and stored-report contracts for #2071."""

import copy
from datetime import datetime
from types import SimpleNamespace

import pytest

from api.v1.schemas.strategy_synthesis import project_strategy_synthesis
from src.agent.protocols import AgentOpinion, StrategyOpinion
from src.agent.skills.aggregator import SkillAggregator
from src.agent.skills.engine import StrategyEngine
from src.agent.skills.synthesis import StrategySynthesizer


def synthesis(opinions=None, weights=None, signal="buy"):
    opinions = opinions or [
        StrategyOpinion(skill_id="growth", agent_name="skill_growth", signal="buy", confidence=0.8, reasoning="Growth supported by earnings"),
        StrategyOpinion(skill_id="value", agent_name="skill_value", signal="sell", confidence=0.9, reasoning="Valuation stretched"),
    ]
    return StrategySynthesizer().synthesize(
        opinions, weighted_score=3.8, final_signal=signal,
        weighted_confidence=0.8, conflicts=[], applied_weights=weights,
    )


def test_distribution_uses_actual_outcome_weights_through_engine(monkeypatch):
    service = SimpleNamespace(compute_weights=lambda ids: {"growth": 1.2, "value": 1.0, "neutral": 1.0})
    aggregator = SkillAggregator(weight_service=service)
    monkeypatch.setattr(aggregator, "_use_outcome_autoweight", lambda: True)
    opinions = [
        AgentOpinion(agent_name="skill_growth", signal="buy", confidence=0.8),
        AgentOpinion(agent_name="skill_value", signal="sell", confidence=0.8),
        AgentOpinion(agent_name="skill_neutral", signal="hold", confidence=0.4),
        AgentOpinion(agent_name="skill_invalid", signal="moon", confidence=0.99),
    ]
    result = StrategyEngine(aggregator=aggregator).process(opinions)
    payload = result.synthesis_dict
    assert payload["schema_version"] == "strategy-synthesis-v1"
    buckets = payload["signal_distribution"]
    assert [buckets[k]["count"] for k in ("bullish", "neutral", "bearish")] == [1, 1, 1]
    assert buckets["bullish"]["weight_share"] == pytest.approx(0.96 / 2.16)
    assert buckets["neutral"]["weight_share"] == pytest.approx(0.4 / 2.16)
    assert buckets["bearish"]["weight_share"] == pytest.approx(0.8 / 2.16)
    assert sum(b["weight_share"] for b in buckets.values()) == pytest.approx(1)
    assert payload["summary_params"]["invalid_opinion_count"] == 1
    assert payload["final_signal"] == aggregator.calculate(opinions).final_signal
    assert all(item["skill_id"] != "invalid" for item in payload["supporting_skills"] + payload["opposing_skills"])


@pytest.mark.parametrize("weights", [None, [0.0, 0.0]])
def test_unknown_or_zero_weights_are_not_invented(weights):
    payload = synthesis(weights=weights)
    assert all(item["weight_share"] is None for item in payload["signal_distribution"].values())
    assert payload["signal_distribution"]["bullish"]["count"] == 1


@pytest.mark.parametrize("reverse", [False, True])
def test_primary_dissent_sort_is_deterministic_and_relative_to_final(reverse):
    opinions = [
        StrategyOpinion(skill_id="bull", signal="buy", confidence=0.99),
        StrategyOpinion(skill_id="b", signal="sell", confidence=0.9),
        StrategyOpinion(skill_id="a", signal="hold", confidence=0.9),
        StrategyOpinion(skill_id="heavy", signal="sell", confidence=0.6),
        StrategyOpinion(skill_id="invalid", signal="sell", confidence=1.0, invalid_signal=True),
    ]
    weights = [1.0, 0.8, 0.8, 0.9, 100.0]
    if reverse:
        opinions.reverse()
        weights.reverse()
    payload = synthesis(opinions, weights)
    assert payload["primary_dissent"]["skill_id"] == "heavy"
    weights[opinions.index(next(op for op in opinions if op.skill_id == "heavy"))] = 0.8
    assert synthesis(opinions, weights)["primary_dissent"]["skill_id"] == "a"
    aligned = [StrategyOpinion(skill_id="x", signal="buy", confidence=0.8)]
    assert synthesis(aligned, [1.0])["primary_dissent"] is None


def test_all_invalid_stub_has_empty_distribution():
    result = StrategyEngine().process([AgentOpinion(agent_name="skill_bad", signal="moon", confidence=1.0)])
    payload = result.synthesis_dict
    assert payload["consensus_level"] == "insufficient"
    assert payload["summary_params"]["opinion_count"] == 0
    assert payload["primary_dissent"] is None
    assert all(bucket == {"count": 0, "weight_share": None} for bucket in payload["signal_distribution"].values())


@pytest.mark.parametrize("value", [None, {}, [], "broken", {"final_signal": "moon"}])
def test_absent_or_malformed_synthesis_is_omitted(value):
    assert project_strategy_synthesis({"dashboard": {"strategy_synthesis": value}}) is None


def test_projection_filters_malformed_fields_and_sensitive_extras_without_recomputing():
    payload = synthesis(weights=[0.8, 0.4])
    payload["confidence"] = float("nan")
    payload["supporting_skills"] += [None, "bad", {}, {"skill_id": "invalid", "signal": "buy", "invalid_signal": True}]
    payload["opposing_skills"][0]["raw_prompt"] = "secret-prompt"
    payload["primary_dissent"]["raw_prompt"] = "secret-prompt"
    payload["summary_params"]["api_key"] = "secret-key"
    payload["conflicts"] = [{"conflict_type": "directional_opposition", "severity": "high", "participants": ["growth", "value"], "metadata": {"token": "secret-key"}}, {}, "bad"]
    payload["deliberation"] = {"mode": "mediator_v0", "summary": "bad", "responses": [{"raw_prompt": "secret-prompt"}]}
    payload["revision_projection"] = {"mode": "authoritative", "projected_signal": "sell", "final_signal_overridden": True}
    raw = {"dashboard": {"strategy_synthesis": payload}}
    original = copy.deepcopy(raw)
    projected = project_strategy_synthesis(raw)
    assert projected.confidence is None
    assert projected.final_signal == "buy"
    assert len(projected.supporting_skills) == len(projected.opposing_skills) == len(projected.conflicts) == 1
    assert projected.primary_dissent == projected.opposing_skills[0]
    assert projected.revision_projection is None
    assert projected.deliberation.summary is None
    assert "secret" not in projected.model_dump_json()
    assert projected.signal_distribution.bullish.weight_share == pytest.approx(2 / 3)
    assert raw["dashboard"]["strategy_synthesis"]["supporting_skills"] == original["dashboard"]["strategy_synthesis"]["supporting_skills"]
    legacy = project_strategy_synthesis({"dashboard": {"strategy_synthesis": {"final_signal": "hold"}}})
    assert legacy.signal_distribution is None and legacy.primary_dissent is None


def test_primary_dissent_cannot_introduce_an_unstored_opinion():
    payload = synthesis(weights=[0.8, 0.4])
    payload["primary_dissent"]["skill_id"] = "invented"
    assert project_strategy_synthesis({"dashboard": {"strategy_synthesis": payload}}).primary_dissent is None


def test_openapi_publishes_the_optional_display_contract():
    from api.app import create_app

    schemas = create_app().openapi()["components"]["schemas"]
    assert "strategy_synthesis" in schemas["ReportDetails"]["properties"]
    assert "primary_dissent" in schemas["StrategySynthesis"]["properties"]
    assert "raw_data" not in schemas["StrategyDisplayOpinion"]["properties"]


def test_in_memory_result_without_a_saved_snapshot_still_projects_synthesis(monkeypatch):
    from api.v1.endpoints import analysis

    monkeypatch.setattr(analysis, "_load_sync_fundamental_sources", lambda **kwargs: (None, None, None))
    payload = synthesis(weights=[0.8, 0.4])
    raw = {"dashboard": {"strategy_synthesis": payload}}
    task = SimpleNamespace(task_id="unsaved", stock_code="600519", stock_name="贵州茅台", created_at=datetime.now(), result={
        "stock_code": "600519", "report": {"summary": {}, "details": {"raw_result": raw}},
    })
    result = analysis._build_task_analysis_result(task)
    assert result.report["details"]["strategy_synthesis"] == project_strategy_synthesis(raw).model_dump()


def test_sync_task_and_history_use_same_projection_from_real_sqlite(tmp_path, monkeypatch):
    from api.v1.endpoints import analysis, history
    from api.v1.schemas.analysis import AnalyzeRequest
    from src.analyzer import AnalysisResult
    from src.services.analysis_service import AnalysisService
    from src.storage import DatabaseManager

    monkeypatch.setattr(DatabaseManager, "_instance", None)
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'reports.db'}")
    payload = synthesis(weights=[0.8, 0.4])
    result = AnalysisResult(code="600519", name="贵州茅台", sentiment_score=70, operation_advice="持有", trend_prediction="震荡", dashboard={"strategy_synthesis": payload})
    saved = {}

    def analyze(self, **kwargs):
        saved["query_id"] = kwargs["query_id"]
        saved["id"] = db.save_analysis_history(result, kwargs["query_id"], "detailed", None, save_snapshot=False)
        return {"stock_code": "600519", "stock_name": "贵州茅台", "report": {"summary": {"sentiment_score": 70}}}

    monkeypatch.setattr(AnalysisService, "analyze_stock", analyze)
    monkeypatch.setattr(analysis, "get_task_queue", lambda: SimpleNamespace(get_task=lambda task_id: None))
    try:
        sync = analysis._handle_sync_analysis("600519", AnalyzeRequest(stock_code="600519", async_mode=False))
        assert saved["id"] > 0
        stored = history.get_history_detail(str(saved["id"]), db_manager=db)
        db_status = analysis.get_analysis_status(saved["query_id"])
        task = SimpleNamespace(task_id=saved["query_id"], stock_code="600519", stock_name="贵州茅台", created_at=datetime.now(), result={
            "query_id": saved["query_id"], "stock_code": "600519", "report": {"summary": {"sentiment_score": 70}},
        })
        memory = analysis._build_task_analysis_result(task)
        expected = project_strategy_synthesis({"dashboard": result.dashboard}).model_dump()
        assert sync.report["details"]["strategy_synthesis"] == expected
        assert stored.details.strategy_synthesis.model_dump() == expected
        assert db_status.result.report["details"]["strategy_synthesis"] == expected
        assert memory.report["details"]["strategy_synthesis"] == expected
        assert stored.details.raw_result["dashboard"]["strategy_synthesis"] == payload
    finally:
        db._engine.dispose()
