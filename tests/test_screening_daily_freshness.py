"""Daily freshness through real cache, DSA bridge, features, and risk overlay."""

from datetime import datetime
import os
from unittest.mock import Mock

import pandas as pd
import pytest

from src.core import trading_calendar
from src.services.screening import daily
from src.services.screening.models import Pick
from src.services.screening.risk import apply_risk_overlay
from src.services import screening_service


def _freeze_time(monkeypatch, value):
    now = datetime.fromisoformat(value)
    build_context = trading_calendar.build_market_phase_context
    monkeypatch.setattr(
        daily, "build_market_phase_context",
        lambda *, market, current_time=None: build_context(market=market, current_time=current_time or now),
    )
    monkeypatch.setattr(daily.time, "time", lambda: now.timestamp())
    return now


def _history(last_date):
    return pd.DataFrame({
        "date": pd.bdate_range(end=last_date, periods=65).strftime("%Y-%m-%d"),
        "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "volume": 1000.0,
    })


def _cache(tmp_path, hist, acquired_at, code="000001"):
    path = daily._daily_history_cache_path(tmp_path, code=code, source="tencent", lookback_days=120)
    daily._write_daily_history_cache(path, hist, code=code, source="tencent", lookback_days=120)
    stamp = datetime.fromisoformat(acquired_at).timestamp()
    os.utime(path, (stamp, stamp))
    return path


@pytest.mark.parametrize("now,acquired,last_date,code,expected_stale", [
    ("2025-06-06T09:00:00+08:00", "2025-06-05T16:00:00+08:00", "2025-06-05", "000001", False),
    ("2025-06-06T14:00:00+08:00", "2025-06-06T13:00:00+08:00", "2025-06-06", "000001", False),
    ("2025-06-06T16:00:00+08:00", "2025-06-06T14:00:00+08:00", "2025-06-06", "000001", True),
    ("2025-06-06T16:00:00+08:00", "2025-06-06T16:00:00+08:00", "2025-06-05", "000001", True),
    ("2025-06-08T10:00:00+08:00", "2025-06-06T16:00:00+08:00", "2025-06-06", "000001", False),
    ("2025-10-01T16:00:00+08:00", "2025-09-30T16:00:00+08:00", "2025-09-30", "000001", False),
    ("2025-06-09T09:00:00+08:00", "2025-06-06T16:00:00+08:00", "2025-06-06", "000001", False),
    ("2025-06-09T16:00:00+08:00", "2025-06-06T16:00:00+08:00", "2025-06-06", "000001", True),
    ("2025-06-06T18:00:00+00:00", "2025-06-05T21:00:00+00:00", "2025-06-05", "AAPL", False),
    ("2025-06-06T21:00:00+00:00", "2025-06-06T18:00:00+00:00", "2025-06-06", "AAPL", True),
])
def test_cache_requires_session_freshness_in_addition_to_ttl(
    monkeypatch, tmp_path, now, acquired, last_date, code, expected_stale,
):
    _freeze_time(monkeypatch, now)
    path = _cache(tmp_path, _history(last_date), acquired, code)
    cached = daily._read_daily_history_cache(path, ttl_seconds=4 * 86400)
    assert (cached is None) == expected_stale
    degraded = daily._read_daily_history_cache(path, ttl_seconds=4 * 86400, allow_stale=True)
    assert degraded is not None
    assert bool(degraded.attrs.get("daily_stale")) == expected_stale


def test_close_transition_refreshes_partial_bar_and_replaces_cache(monkeypatch, tmp_path):
    _freeze_time(monkeypatch, "2025-06-06T16:00:00+08:00")
    path = _cache(tmp_path, _history("2025-06-06"), "2025-06-06T14:00:00+08:00")
    refreshed = _history("2025-06-06")
    refreshed.loc[64, "close"] = 10.5
    fetch = Mock(return_value=refreshed)
    monkeypatch.setattr(daily, "_fetch_daily_tencent", fetch)
    result = daily.fetch_daily_history("000001", source="tencent", retries=0, cache_dir=tmp_path)
    fetch.assert_called_once()
    assert result.iloc[-1]["close"] == 10.5
    assert not result.attrs.get("daily_stale")
    assert daily._read_daily_history_cache(path, ttl_seconds=86400).iloc[-1]["close"] == 10.5


def test_expired_ttl_still_refreshes_on_non_trading_day(monkeypatch, tmp_path):
    _freeze_time(monkeypatch, "2025-06-08T10:00:00+08:00")
    path = _cache(tmp_path, _history("2025-06-06"), "2025-06-06T16:00:00+08:00")
    assert daily._read_daily_history_cache(path, ttl_seconds=86400) is None


def test_failed_refresh_reaches_quality_and_risk_overlay(monkeypatch, tmp_path):
    _freeze_time(monkeypatch, "2025-06-06T16:00:00+08:00")
    _cache(tmp_path, _history("2025-06-05"), "2025-06-06T14:00:00+08:00")
    monkeypatch.setattr(daily, "_fetch_daily_tencent", Mock(side_effect=RuntimeError("offline")))
    enriched = daily.enrich_daily_features(
        pd.DataFrame([{"code": "000001"}]), source="tencent", fetch_retries=0, cache_dir=tmp_path,
    )
    assert enriched.attrs["daily_success_count"] == 1
    flags = enriched.iloc[0]["daily_quality_flags"]
    assert "stale_cache" in flags
    assert "fallback_errors" in flags
    pick = Pick(
        rank=1, code="000001", name="Test", screen_score=80, final_score=80,
        daily_quality_flags=flags, daily_quality_score=enriched.iloc[0]["daily_quality_score"],
    )
    ranked, _ = apply_risk_overlay([pick])
    assert "daily_stale_cache" in ranked[0].risk_flags
    assert "daily_source_fallback_errors" in ranked[0].risk_flags
    assert ranked[0].final_score < 80


@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("explicit_stale", [False, True])
def test_stale_dsa_history_tries_native_sources_without_overwriting_last_good_cache(
    monkeypatch, tmp_path, fails, explicit_stale,
):
    _freeze_time(monkeypatch, "2025-06-06T16:00:00+08:00")
    path = _cache(tmp_path, _history("2025-06-06"), "2025-06-06T16:00:00+08:00")
    before = path.read_bytes()
    dsa_history = _history("2025-06-06" if explicit_stale else "2025-06-05")
    dsa_history.attrs["daily_stale"] = explicit_stale
    monkeypatch.setattr(screening_service, "get_dsa_daily_history", lambda code, **kwargs: (dsa_history, "db"))
    native = Mock(side_effect=RuntimeError("sources failed")) if fails else Mock(return_value=_history("2025-06-06"))
    monkeypatch.setattr(daily, "fetch_daily_history", native)
    fetcher = screening_service._build_screening_dsa_daily_history_fetcher()
    result = fetcher("000001", source="tencent", retries=0, cache_dir=tmp_path, cache_ttl_seconds=321)
    native.assert_called_once_with(
        "000001", lookback_days=120, source="tencent", retries=0, cache_dir=tmp_path, cache_ttl_seconds=321,
    )
    assert path.read_bytes() == before
    assert bool(result.attrs.get("daily_stale")) == fails
    if fails:
        assert result.attrs["daily_source"] == "dsa:db"
        assert result.attrs["source_errors"] == ["sources failed"]
        assert "stale_cache" in daily.compute_daily_features(result)["daily_quality_flags"]


def test_injected_history_provider_cannot_bypass_freshness_check(monkeypatch):
    _freeze_time(monkeypatch, "2025-06-06T16:00:00+08:00")
    old_history = _history("2025-06-05")
    enriched = daily.enrich_daily_features(
        pd.DataFrame([{"code": "000001"}]), history_fetcher=lambda *args, **kwargs: old_history,
    )
    assert "stale_cache" in enriched.iloc[0]["daily_quality_flags"]
    assert not old_history.attrs.get("daily_stale")


def test_lagging_native_source_is_not_promoted_by_new_cache_timestamp(monkeypatch, tmp_path):
    _freeze_time(monkeypatch, "2025-06-06T16:00:00+08:00")
    path = _cache(tmp_path, _history("2025-06-06"), "2025-06-06T14:00:00+08:00")
    before = path.read_bytes()
    fetch = Mock(side_effect=lambda *args, **kwargs: _history("2025-06-05"))
    monkeypatch.setattr(daily, "_fetch_daily_tencent", fetch)
    for _ in range(2):
        result = daily.fetch_daily_history("000001", source="tencent", retries=0, cache_dir=tmp_path)
        assert result.attrs["daily_stale"]
        assert path.read_bytes() == before
    assert fetch.call_count == 2


def test_calendar_unavailable_retains_ttl_and_preserves_explicit_stale_metadata(monkeypatch, tmp_path):
    _freeze_time(monkeypatch, "2025-06-06T16:00:00+08:00")
    monkeypatch.setattr(trading_calendar, "_XCALS_AVAILABLE", False)
    old_history = _history("2025-06-05")
    path = _cache(tmp_path, old_history, "2025-06-06T16:00:00+08:00")
    assert daily._read_daily_history_cache(path, ttl_seconds=86400) is not None
    old_history.attrs["daily_stale"] = True
    _cache(tmp_path, old_history, "2025-06-06T16:00:00+08:00")
    assert daily._read_daily_history_cache(path, ttl_seconds=86400) is None
    assert daily._read_daily_history_cache(path, ttl_seconds=86400, allow_stale=True).attrs["daily_stale"]


@pytest.mark.parametrize("dates", [["bad"], ["2025-06-05"], ["2025-06-09"]])
def test_missing_invalid_old_or_future_dates_are_not_current(monkeypatch, dates):
    _freeze_time(monkeypatch, "2025-06-06T16:00:00+08:00")
    assert daily.daily_history_is_stale(pd.DataFrame({"date": dates, "close": 10}), code="000001")
    assert daily.daily_history_is_stale(pd.DataFrame({"close": [10]}), code="000001")


def test_compact_dates_and_missing_latest_close(monkeypatch):
    _freeze_time(monkeypatch, "2025-06-06T16:00:00+08:00")
    hist = pd.DataFrame({"trade_date": [20250605, 20250606], "close": [10, 11]})
    assert not daily.daily_history_is_stale(hist, code="000001")
    hist.loc[1, "close"] = float("nan")
    assert daily.daily_history_is_stale(hist, code="000001")
