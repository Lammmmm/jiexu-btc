from collections import defaultdict
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.chart_service import ChartService
from backend.config import Settings
from backend.market.repository import MarketRepository
from backend.market.validation import DataIntegrityError
from backend.statistics.ganzhi import GanzhiStatisticsService
from backend.timeutils import day_start


@pytest.fixture
def months(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "months.db")
    raw = daily_factory("2019-01-01", "2025-04-01")
    groups = defaultdict(list)
    for row in raw:
        groups[row.metadata["solar_month_id"]].append(row)
    rows = []
    for index, group in enumerate(groups.values()):
        for i, row in enumerate(group):
            close = [110, 90, 100][index % 3] if i == len(group) - 1 else 100
            rows.append(replace(row, open=D(100), high=D(120), low=D(80), close=D(close)))
    repo.upsert(rows)
    repo.set_meta("first_available_date", rows[0].period_id)
    repo.set_meta("last_sync_ms", day_start(date(2025, 4, 2)))
    return repo, GanzhiStatisticsService(repo, calendar), rows


def test_month_rankings_independent_group_counts(months, monkeypatch):
    repo, service, rows = months
    original = repo.snapshot
    calls = []
    def snapshot():
        calls.append(1)
        return original()
    monkeypatch.setattr(repo, "snapshot", snapshot)
    ranking = service.rankings(period="month")
    assert len(calls) == 1
    groups = defaultdict(list)
    for row in rows:
        groups[row.metadata["solar_month_id"]].append(row)
    expected = {gz: {"up": 0, "down": 0, "flat": 0} for gz in service.options()}
    total = 0
    for group in groups.values():
        first, last = group[0], group[-1]
        if first.period_id != first.metadata["month_start"] or last.period_id != first.metadata["month_end"]:
            continue
        key = "up" if last.close > first.open else "down" if last.close < first.open else "flat"
        expected[first.metadata["ganzhi_month"]][key] += 1
        total += 1
    assert ranking["period"] == "month"
    assert ranking["totalSamples"] == total
    assert ranking["totalExcluded"] == 2
    for side in ("up", "down"):
        ranked = ranking[side + "Ranking"]
        assert len(ranked) == len({r["ganzhi"] for r in ranked}) == 60
        for row in ranked:
            assert row["counts"] == expected[row["ganzhi"]]
        rates = [Fraction(r["counts"][side], r["sampleCount"]) for r in ranked if r["sampleCount"]]
        assert rates == sorted(rates, reverse=True)


def test_month_details_equal_chart_and_use_month_ganzhi(months, calendar):
    repo, service, _ = months
    chart = ChartService(repo, calendar).candles("month")["candles"]
    target = next(c for c in chart if c["metadata"]["startDate"] == "2024-09-07")
    gz = target["metadata"]["displayGanzhi"]
    assert gz != calendar.get("2024-09-07")["ganzhi_day"]
    result = service.summarize(gz + "月", period="month")
    assert result["period"] == "month"
    assert result["matchedCount"] >= 2
    by_id = {c["periodId"]: c for c in chart}
    for match in result["matches"]:
        candle = by_id[match["periodId"]]
        assert match["ganzhi"] == candle["metadata"]["displayGanzhi"]
        assert match["date"] == candle["metadata"]["startDate"]
        assert match["endDate"] == candle["metadata"]["endDate"]
        for key in ("open", "high", "low", "close", "volume"):
            assert match[key] == candle[key]


def test_month_range_is_inclusive_start_date_and_does_not_truncate(months, calendar):
    _, service, _ = months
    gz = calendar.get("2024-09-07")["ganzhi_month"]
    args = {"period": "month", "start": date(2024, 9, 7), "end": date(2024, 9, 7)}
    result = service.summarize(gz, **args)
    assert result["matchedCount"] == result["sampleCount"] == 1
    assert result["matches"][0]["endDate"] == "2024-10-07"
    assert service.summarize(gz, period="month", start=date(2024, 9, 8), end=date(2024, 10, 7))["matchedCount"] == 0
    for side in ("upRanking", "downRanking"):
        ranked = service.rankings(**args)[side]
        assert ranked[0]["ganzhi"] == gz
        assert all(r["sampleCount"] == 0 for r in ranked[1:])


def test_previous_month_close_outside_filter(months, calendar):
    repo, service, _ = months
    candles = ChartService(repo, calendar).candles("month")["candles"]
    i = next(i for i, c in enumerate(candles) if c["metadata"]["startDate"] == "2024-09-07")
    current, previous = candles[i], candles[i - 1]
    result = service.summarize(current["metadata"]["displayGanzhi"], period="month",
                               start=date(2024, 9, 7), end=date(2024, 9, 7), basis="previous_close")
    match = result["matches"][0]
    assert result["sampleCount"] == 1
    assert match["baseline"] == previous["close"]
    expected = (D(current["close"]) / D(previous["close"]) - 1) * 100
    assert D(match["changePct"]) == expected.quantize(D("0.000001"))


def test_anomaly_excludes_whole_month_and_next_previous_close(months, calendar):
    repo, service, rows = months
    row = next(r for r in rows if r.period_id == "2024-09-10")
    repo.upsert([replace(row, close_time=row.open_time + 1000)])
    for day, reason, basis in [
        ("2024-09-07", "source_anomaly", "open"),
        ("2024-10-08", "invalid_previous_close", "previous_close"),
    ]:
        result = service.summarize(calendar.get(day)["ganzhi_month"], period="month",
                                   start=date.fromisoformat(day), end=date.fromisoformat(day), basis=basis)
        assert result["sampleCount"] == 0
        assert result["excluded"][reason] == 1


def test_incomplete_and_unclosed_months(months, calendar):
    repo, service, _ = months
    first = service.summarize(calendar.get("2019-01-01")["ganzhi_month"], period="month",
                              end=date(2019, 1, 1))
    assert first["excluded"]["incomplete_period"] == 1
    current = service.summarize(calendar.get("2025-04-01")["ganzhi_month"], period="month",
                                start=date(2025, 3, 1))
    assert current["excluded"]["unclosed"] == 1
    repo.set_meta("last_sync_ms", 0)
    result = service.rankings(period="month")
    assert result["totalSamples"] == 0


def test_listing_on_month_boundary_still_excluded(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "listing.db")
    rows = daily_factory("2024-09-07", "2024-11-06")
    repo.upsert(rows)
    repo.set_meta("first_available_date", "2024-09-07")
    repo.set_meta("last_sync_ms", day_start(date(2024, 11, 7)))
    service = GanzhiStatisticsService(repo, calendar)
    first = service.summarize(calendar.get("2024-09-07")["ganzhi_month"], period="month")
    assert first["excluded"]["listing_day"] == 1
    next_month = service.summarize(calendar.get("2024-10-08")["ganzhi_month"], period="month", basis="previous_close")
    assert next_month["excluded"]["invalid_previous_close"] == 1


def test_empty_months(tmp_path, calendar):
    service = GanzhiStatisticsService(MarketRepository(tmp_path / "empty.db"), calendar)
    assert service.summarize("丁酉", period="month")["sampleCount"] == 0
    result = service.rankings(period="month")
    assert result["totalSamples"] == 0
    assert len(result["upRanking"]) == 60
    assert all(r["probabilitiesPct"]["up"] is None for r in result["upRanking"])


def test_month_api_and_integrity(months, calendar):
    repo, service, _ = months
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        response = client.get("/api/statistics/ganzhi/rankings", params={"period": "month"})
        assert response.status_code == 200
        assert response.json()["totalSamples"] == service.rankings(period="month")["totalSamples"]
        response = client.get("/api/statistics/ganzhi", params={"period": "month", "ganzhi": "丁酉"})
        assert response.status_code == 200
        assert response.json()["period"] == "month"
        assert client.get("/api/statistics/ganzhi/rankings", params={"period": "year"}).status_code == 422
        with repo.connection() as conn:
            conn.execute("DELETE FROM daily_candles WHERE date='2024-09-10'")
        assert client.get("/api/statistics/ganzhi/rankings", params={"period": "month"}).status_code == 409
    with pytest.raises(DataIntegrityError):
        service.summarize("丁酉", period="month")


def test_month_magnitudes_use_2023_onward_but_direction_keeps_old_months(months, calendar):
    from statistics import median
    repo, service, raw = months
    repo.upsert([replace(row, high=D(200), low=D(1)) for row in raw if row.period_id < "2023-01-01"])
    gz = calendar.get("2024-09-07")["ganzhi_month"]
    result = service.summarize(gz, period="month")
    modern = [match for match in result["matches"] if match["included"] and match["date"] >= "2023-01-01"]
    old = [match for match in result["matches"] if match["included"] and match["date"] < "2023-01-01"]
    assert old and modern
    strength = result["strength"]
    assert result["sampleCount"] == len(old) + len(modern)
    assert strength["start"] == "2023-01-01"
    assert strength["sampleCount"] == len(modern)
    assert strength["sampleStart"] == min(match["date"] for match in modern)
    assert strength["sampleEnd"] == max(match["date"] for match in modern)
    assert strength["medianIntradayRangePct"] == "40.000000"
    changes = [(D(match["close"]) / D(match["baseline"]) - 1) * 100 for match in modern]
    assert D(result["averageChangePct"]) == (sum(changes) / len(changes)).quantize(D("0.000001"))
    assert D(result["medianChangePct"]) == median(changes).quantize(D("0.000001"))
    assert D(result["bestChangePct"]) == max(changes).quantize(D("0.000001"))
    assert D(result["worstChangePct"]) == min(changes).quantize(D("0.000001"))
    assert strength["largeMove"]["sampleCount"] == len(modern)
