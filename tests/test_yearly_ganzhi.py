from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.market.repository import MarketRepository
from backend.statistics.ganzhi import GanzhiStatisticsService
from backend.timeutils import day_start


@pytest.fixture
def across_new_year(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "annual.db")
    rows = daily_factory("2024-11-01", "2025-04-30")
    chosen = next(r.metadata["ganzhi_day"] for r in rows if r.period_id == "2024-12-20")
    matched = [r for r in rows if r.metadata["ganzhi_day"] == chosen]
    assert any(r.period_id == "2024-12-20" for r in matched)
    assert any(r.period_id == "2025-02-18" for r in matched)
    for i, row in enumerate(matched):
        rows[rows.index(row)] = replace(row, open=D(100), high=D(110), low=D(90),
                                        close=D([110, 90, 100][i % 3]))
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2025, 5, 1)))
    return repo, GanzhiStatisticsService(repo, calendar), chosen


def test_yearly_bounds_and_probabilities(across_new_year):
    _, service, chosen = across_new_year
    result = service.summarize(chosen, start=date(2024, 12, 1), end=date(2025, 2, 28))
    groups = result["yearly"]
    assert [g["year"] for g in groups] == [2025, 2024]
    assert [(g["start"], g["endExclusive"]) for g in groups] == [
        ("2025-01-01", "2026-01-01"), ("2024-01-01", "2025-01-01")]
    assert sum(g["sampleCount"] for g in groups) == result["sampleCount"]
    assert sum(g["matchedCount"] for g in groups) == result["matchedCount"]
    for group in groups:
        rows = [r for r in result["matches"] if group["start"] <= r["date"] < group["endExclusive"]]
        assert group["matchedCount"] == len(rows)
        assert group["counts"]["up"] == sum(r["direction"] == "up" for r in rows)
        assert group["counts"]["down"] == sum(r["direction"] == "down" for r in rows)
        assert group["sampleCount"] == sum(r["included"] for r in rows)
        assert D(group["probabilitiesPct"]["up"]) == (D(group["counts"]["up"]) * 100 / group["sampleCount"]).quantize(D("0.000001"))
    assert sum(g["counts"]["up"] for g in groups) == result["counts"]["up"]


def test_partial_date_range_and_exclusions(across_new_year):
    repo, service, chosen = across_new_year
    result = service.summarize(chosen, start=date(2025, 1, 1), end=date(2025, 2, 28))
    assert [g["year"] for g in result["yearly"]] == [2025]
    assert result["yearly"][0]["sampleCount"] == result["sampleCount"]
    row = next(r for r in repo.all() if r.period_id == "2025-02-18")
    repo.upsert([replace(row, close_time=row.open_time + 1000)])
    result = service.summarize(chosen, start=date(2025, 2, 18), end=date(2025, 2, 18))
    group = result["yearly"][0]
    assert group["matchedCount"] == group["excludedCount"] == 1
    assert group["sampleCount"] == 0
    assert group["probabilitiesPct"] == {"up": None, "down": None, "flat": None}


def test_previous_close_and_api(across_new_year):
    repo, service, chosen = across_new_year
    result = service.summarize(chosen, basis="previous_close")
    assert sum(g["sampleCount"] for g in result["yearly"]) == result["sampleCount"]
    assert sum(g["counts"]["up"] for g in result["yearly"]) == result["counts"]["up"]
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        response = client.get("/api/statistics/ganzhi", params={"ganzhi": chosen, "basis": "previous_close"})
        assert response.status_code == 200
        assert response.json()["yearly"] == result["yearly"]
        ranking = client.get("/api/statistics/ganzhi/rankings").json()
        assert "yearly" not in ranking["upRanking"][0]
        monthly = client.get("/api/statistics/ganzhi", params={"ganzhi": chosen, "period": "month"}).json()
        assert monthly["yearly"] == []
