"""Low-sensitivity display projection of authoritative strategy synthesis.

Historical payloads are normalized by the shared report helper, then validated
field by field. This boundary does not infer weights, votes or final signals.
"""

from typing import Any, List, Literal, Optional, Type, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.report_language import normalize_strategy_synthesis_payload

StrategySignal = Literal["strong_buy", "buy", "hold", "sell", "strong_sell"]
ConflictSeverity = Literal["none", "low", "medium", "high"]
ConsensusLevel = Literal["insufficient", "low", "medium", "high"]


class DisplayModel(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class StrategyDisplayOpinion(DisplayModel):
    skill_id: str = Field(min_length=1)
    signal: StrategySignal
    agent_name: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    reasoning: Optional[str] = None
    conditions_met: List[str] = Field(default_factory=list)


class StrategyDisplayConflict(DisplayModel):
    conflict_type: str = Field(min_length=1)
    severity: ConflictSeverity
    participants: List[str] = Field(default_factory=list)


class SignalDistributionBucket(DisplayModel):
    count: int = Field(ge=0, strict=True)
    weight_share: Optional[float] = Field(None, ge=0, le=1)


class SignalDistribution(DisplayModel):
    bullish: SignalDistributionBucket
    neutral: SignalDistributionBucket
    bearish: SignalDistributionBucket


class StrategySummaryParams(DisplayModel):
    opinion_count: Optional[int] = Field(None, ge=0, strict=True)
    total_opinion_count: Optional[int] = Field(None, ge=0, strict=True)
    invalid_opinion_count: Optional[int] = Field(None, ge=0, strict=True)


class DeliberationDisplaySummary(DisplayModel):
    resolution_status: Optional[str] = None
    confidence_adjustment: Optional[float] = Field(None, ge=-1, le=1)
    unresolved_conflict_types: List[str] = Field(default_factory=list)


class StrategyDisplayDeliberation(DisplayModel):
    status: Optional[str] = None
    mode: Optional[str] = None
    rounds: Optional[int] = Field(None, ge=0)
    summary: Optional[DeliberationDisplaySummary] = None


class StrategyRevisionProjection(DisplayModel):
    mode: Literal["preview_only"]
    final_signal_overridden: Literal[False]
    projected_signal: StrategySignal
    projected_confidence: Optional[float] = Field(None, ge=0, le=1)
    projected_conflict_count: Optional[int] = Field(None, ge=0)
    projected_conflict_severity: Optional[ConflictSeverity] = None
    projected_consensus_level: Optional[ConsensusLevel] = None
    changed_skill_count: Optional[int] = Field(None, ge=0)


class StrategySynthesis(DisplayModel):
    schema_version: Optional[Literal["strategy-synthesis-v1"]] = None
    final_signal: StrategySignal
    weighted_score: Optional[float] = Field(None, ge=0, le=5)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    original_confidence: Optional[float] = Field(None, ge=0, le=1)
    consensus_level: Optional[ConsensusLevel] = None
    conflict_count: Optional[int] = Field(None, ge=0)
    conflict_severity: Optional[ConflictSeverity] = None
    summary_key: Optional[str] = None
    summary_params: Optional[StrategySummaryParams] = None
    signal_distribution: Optional[SignalDistribution] = None
    supporting_skills: List[StrategyDisplayOpinion] = Field(default_factory=list)
    opposing_skills: List[StrategyDisplayOpinion] = Field(default_factory=list)
    primary_dissent: Optional[StrategyDisplayOpinion] = None
    conflicts: List[StrategyDisplayConflict] = Field(default_factory=list)
    deliberation: Optional[StrategyDisplayDeliberation] = None
    revision_projection: Optional[StrategyRevisionProjection] = None


T = TypeVar("T", bound=DisplayModel)


def _display_fields(model: Type[T], value: Any) -> Optional[T]:
    """Drop malformed optional fields; required identity failures omit the item."""
    if not isinstance(value, dict):
        return None
    data = dict(value)
    while True:
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            fields = {error["loc"][0] for error in exc.errors() if error["loc"]}
            if not fields or any(model.model_fields[field].is_required() for field in fields):
                return None
            for field in fields:
                data.pop(field, None)


def project_strategy_synthesis(raw_result: Any) -> Optional[StrategySynthesis]:
    """Read the stored authoritative dashboard; do not recompute old reports."""
    if not isinstance(raw_result, dict):
        return None
    dashboard = raw_result.get("dashboard")
    if not isinstance(dashboard, dict):
        return None
    payload = normalize_strategy_synthesis_payload(dashboard.get("strategy_synthesis"))
    if not payload:
        return None
    for key, model in (
        ("supporting_skills", StrategyDisplayOpinion),
        ("opposing_skills", StrategyDisplayOpinion),
        ("conflicts", StrategyDisplayConflict),
    ):
        payload[key] = [
            item for value in payload[key]
            if not value.get("invalid_signal")
            and (item := _display_fields(model, value)) is not None
        ]
    for key, model in (
        ("summary_params", StrategySummaryParams),
        ("signal_distribution", SignalDistribution),
        ("primary_dissent", StrategyDisplayOpinion),
        ("deliberation", StrategyDisplayDeliberation),
        ("revision_projection", StrategyRevisionProjection),
    ):
        payload[key] = _display_fields(model, payload.get(key))
    # A stale or malformed selected dissent must not introduce a new opinion.
    primary = payload["primary_dissent"]
    if primary not in payload["opposing_skills"]:
        payload["primary_dissent"] = None
    return _display_fields(StrategySynthesis, payload)
