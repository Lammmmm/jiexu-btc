from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.market.repository import MarketRepository
from backend.market.validation import DataIntegrityError
from backend.statistics.ganzhi import GanzhiStatisticsService
from backend.timeutils import day_start


@pytest.fixture
def dataset(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "market.db")
    rows = daily_factory("2025-01-01", "2025-08-28")
    indices = [i for i, row in enumerate(rows) if row.metadata["ganzhi_day"] == "丁酉"]
    assert len(indices) == 4
    for i, close in zip(indices, [110, 90, 100, 105]):
        rows[i] = replace(rows[i], open=D(100), high=D(110), low=D(90), close=D(close))
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2025, 8, 29)))
    return repo, GanzhiStatisticsService(repo, calendar), rows, indices


def test_single_statistics_and_normalization(dataset):
    _, service, rows, indices = dataset
    result = service.summarize(" 丁酉日 ")
    assert result["sampleCount"] == result["matchedCount"] == 4
    assert result["counts"] == {"up": 2, "down": 1, "flat": 1}
    assert result["probabilitiesPct"] == {"up": "50.000000", "down": "25.000000", "flat": "25.000000"}
    assert result["averageChangePct"] == "1.250000"
    assert result["medianChangePct"] == "2.500000"
    assert [r["date"] for r in result["matches"]] == [rows[i].period_id for i in reversed(indices)]


def test_anomaly_and_unclosed_excluded(dataset):
    repo, service, rows, indices = dataset
    abnormal = replace(rows[indices[1]], close_time=rows[indices[1]].open_time + 1000)
    repo.upsert([abnormal])
    repo.set_meta("last_sync_ms", rows[indices[-1]].open_time + 1000)
    result = service.summarize("丁酉")
    assert result["sampleCount"] == 2
    assert result["counts"] == {"up": 1, "down": 0, "flat": 1}
    assert result["excluded"]["source_anomaly"] == result["excluded"]["unclosed"] == 1


def test_listing_day_excluded(dataset):
    repo, service, rows, _ = dataset
    repo.set_meta("first_available_date", rows[0].period_id)
    result = service.summarize(rows[0].metadata["ganzhi_day"])
    assert result["excluded"]["listing_day"] == 1
    assert result["sampleCount"] == 3


def test_without_sync_no_closed_samples(dataset):
    repo, service, _, _ = dataset
    repo.set_meta("last_sync_ms", 0)
    result = service.summarize("丁酉")
    assert result["sampleCount"] == 0
    assert result["excluded"]["unclosed"] == 4
    assert result["probabilitiesPct"] == dict.fromkeys(("up", "down", "flat"))


def test_previous_close_uses_day_outside_filter(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "market.db")
    rows = daily_factory("2025-09-07", "2025-09-08")
    rows[0] = replace(rows[0], open=D(100), high=D(100), low=D(100), close=D(100))
    rows[1] = replace(rows[1], open=D(110), high=D(112), low=D(104), close=D(105))
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2025, 9, 9)))
    service = GanzhiStatisticsService(repo, calendar)
    gz = rows[1].metadata["ganzhi_day"]
    args = {"start": date(2025, 9, 8), "end": date(2025, 9, 8)}
    assert service.summarize(gz, **args)["counts"]["down"] == 1
    result = service.summarize(gz, basis="previous_close", **args)
    assert result["counts"]["up"] == 1
    assert result["matches"][0]["changePct"] == "5.000000"
    assert service.summarize(rows[0].metadata["ganzhi_day"], basis="previous_close")["excluded"]["invalid_previous_close"] == 1
    repo.upsert([replace(rows[0], close_time=rows[0].open_time + 1000)])
    assert service.summarize(gz, basis="previous_close", **args)["excluded"]["invalid_previous_close"] == 1


def test_inclusive_date_filter(dataset):
    _, service, rows, indices = dataset
    day = date.fromisoformat(rows[indices[2]].period_id)
    result = service.summarize("丁酉", start=day, end=day)
    assert result["sampleCount"] == 1
    assert result["probabilitiesPct"]["flat"] == "100.000000"


@pytest.mark.parametrize("ganzhi", ["甲丑", "丁", "火", "not-a-ganzhi", ""])
def test_invalid_ganzhi(dataset, ganzhi):
    with pytest.raises(ValueError):
        dataset[1].summarize(ganzhi)


def test_invalid_filters(dataset):
    service = dataset[1]
    for method in (lambda **kwargs: service.summarize("丁酉", **kwargs), service.rankings):
        with pytest.raises(ValueError):
            method(start=date(2025, 2, 1), end=date(2025, 1, 1))
        with pytest.raises(ValueError):
            method(start=date(1899, 1, 1))
        with pytest.raises(ValueError):
            method(basis="unknown")


def test_empty_cache(tmp_path, calendar):
    service = GanzhiStatisticsService(MarketRepository(tmp_path / "empty.db"), calendar)
    assert service.summarize("丁酉")["sampleCount"] == 0
    result = service.rankings()
    assert result["totalSamples"] == 0
    for side in ("upRanking", "downRanking"):
        assert len(result[side]) == 60
        assert result[side][0]["ganzhi"] == "甲子"
        assert all(row["probabilitiesPct"]["up"] is None for row in result[side])


def test_rankings_one_snapshot_and_exact_order(dataset, monkeypatch):
    repo, service, rows, _ = dataset
    for row in rows:
        if row.metadata["ganzhi_day"] == "甲子":
            repo.upsert([replace(row, open=D(100), high=D(100), low=D(90), close=D(90))])
    snapshot = repo.snapshot
    calls = []
    def tracked():
        calls.append(True)
        return snapshot()
    monkeypatch.setattr(repo, "snapshot", tracked)
    result = service.rankings()
    assert len(calls) == 1
    assert result["totalSamples"] == 240
    assert result["totalExcluded"] == 0
    for direction in ("up", "down"):
        ranking = result[direction + "Ranking"]
        assert len(ranking) == len({r["ganzhi"] for r in ranking}) == 60
        rates = [Fraction(r["counts"][direction], r["sampleCount"]) for r in ranking]
        assert rates == sorted(rates, reverse=True)
        assert [r["rank"] for r in ranking] == list(range(1, 61))
        assert all("matches" not in r for r in ranking)
    assert result["downRanking"][0]["ganzhi"] == "甲子"
    assert result["downRanking"][1]["ganzhi"] == "丁酉"
    single = service.summarize("丁酉")
    ranked = next(r for r in result["upRanking"] if r["ganzhi"] == "丁酉")
    for key in ("counts", "probabilitiesPct", "sampleCount", "excluded"):
        assert ranked[key] == single[key]


def test_rankings_zero_samples_last(dataset):
    _, service, rows, indices = dataset
    day = date.fromisoformat(rows[indices[2]].period_id)
    result = service.rankings(start=day, end=day)
    for side in ("upRanking", "downRanking"):
        assert result[side][0]["ganzhi"] == "丁酉"
        assert all(row["sampleCount"] == 0 for row in result[side][1:])


def test_missing_day_rejected(dataset):
    repo, service, _, _ = dataset
    with repo.connection() as conn:
        conn.execute("DELETE FROM daily_candles WHERE date='2025-01-02'")
    with pytest.raises(DataIntegrityError):
        service.summarize("丁酉")
    with pytest.raises(DataIntegrityError):
        service.rankings()


def test_api_contract(dataset, calendar):
    repo, _, _, _ = dataset
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        assert len(client.get("/api/statistics/ganzhi/options").json()["options"]) == 60
        assert client.get("/api/statistics/ganzhi", params={"ganzhi": "丁酉"}).json()["sampleCount"] == 4
        result = client.get("/api/statistics/ganzhi/rankings").json()
        assert len(result["upRanking"]) == len(result["downRanking"]) == 60
        for path, params in [
            ("/api/statistics/ganzhi", {"ganzhi": "甲丑"}),
            ("/api/statistics/ganzhi/rankings", {"start": "bad"}),
            ("/api/statistics/ganzhi/rankings", {"basis": "invalid"}),
            ("/api/statistics/ganzhi/rankings", {"start": "2026-01-01", "end": "2025-01-01"}),
        ]:
            assert client.get(path, params=params).status_code == 422
        with repo.connection() as conn:
            conn.execute("DELETE FROM daily_candles WHERE date='2025-01-02'")
        assert client.get("/api/statistics/ganzhi/rankings").status_code == 409
