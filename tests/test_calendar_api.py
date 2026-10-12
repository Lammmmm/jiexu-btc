from dataclasses import replace
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.market.repository import MarketRepository
from backend.timeutils import day_start


def test_calendar_days_join_ganzhi_terms_and_historical_rates(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "market.db")
    rows = daily_factory("2026-09-01", "2026-10-12")
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2026, 10, 13)))
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        result = client.get("/api/calendar/days", params={
            "start": "2026-08-30", "end": "2026-10-11",
        }).json()
        assert result["start"] == "2026-08-30"
        assert result["endExclusive"] == "2026-10-11"
        assert len(result["days"]) == 42
        assert result["days"][0]["date"] == "2026-08-30"
        assert result["days"][-1]["date"] == "2026-10-10"
        day = next(d for d in result["days"] if d["date"] == "2026-09-23")
        assert day["ganzhi"] == calendar.get("2026-09-23")["ganzhi_day"]
        assert day["solarTerm"] == "秋分"
        expected = client.get("/api/statistics/ganzhi", params={"ganzhi": day["ganzhi"]}).json()
        assert day["upPct"] == expected["probabilitiesPct"]["up"]
        assert day["sampleCount"] == expected["sampleCount"]
        assert day["strength"] == expected["strength"]
        actual = next(match for match in expected["matches"] if match["date"] == day["date"])
        assert day["actualChangePct"] == actual["changePct"]
        assert day["actualDirection"] == actual["direction"]
        previous = client.get("/api/calendar/days", params={
            "start": "2026-09-20", "end": "2026-09-27", "basis": "previous_close",
        }).json()
        prior_day = next(d for d in previous["days"] if d["date"] == "2026-09-23")
        prior_expected = client.get("/api/statistics/ganzhi", params={
            "ganzhi": day["ganzhi"], "basis": "previous_close",
        }).json()
        assert prior_day["upPct"] == prior_expected["probabilitiesPct"]["up"]
        prior_actual = next(match for match in prior_expected["matches"] if match["date"] == day["date"])
        assert prior_day["actualChangePct"] == prior_actual["changePct"]
        for params in [
            {"start": "2026-09-01", "end": "2026-09-01"},
            {"start": "2026-09-01", "end": "2026-11-01"},
            {"start": "2026-09-01", "end": "2026-09-08", "basis": "invalid"},
            {"start": "2026-09-01", "end": "2026-09-08", "threshold": 4},
            {"start": "2026-09-01", "end": "2026-09-08", "window": "invalid"},
        ]:
            assert client.get("/api/calendar/days", params=params).status_code == 422


def test_calendar_still_shows_dates_before_market_history(tmp_path, calendar):
    repo = MarketRepository(tmp_path / "empty.db")
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        result = client.get("/api/calendar/days", params={
            "start": "1900-01-01", "end": "1900-01-08",
        }).json()
        assert len(result["days"]) == 7
        assert all(day["ganzhi"] for day in result["days"])
        assert all(day["upPct"] is None and day["sampleCount"] == 0 for day in result["days"])
        assert all(day["signalDirection"] == "none" and day["actualChangePct"] is None for day in result["days"])
        assert all(day["strength"]["medianAbsoluteChangePct"] is None for day in result["days"])
        assert result["benchmark"]["sampleCount"] == 0
        assert result["benchmark"]["strength"]["largeMove"]["probabilitiesPct"]["total"] is None


def test_calendar_majority_threshold_and_finalized_actuals(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "majority.db")
    target_dates = ("2025-01-04", "2025-01-05", "2025-01-06")
    target_ganzhi = {ds: calendar.get(ds)["ganzhi_day"] for ds in target_dates}
    closes = {
        target_ganzhi[target_dates[0]]: (110, 110, 110, 90),
        target_ganzhi[target_dates[1]]: (90, 90, 90, 110),
        target_ganzhi[target_dates[2]]: (110, 110, 90, 90),
    }
    seen = {ganzhi: 0 for ganzhi in closes}
    rows = []
    for row in daily_factory("2025-01-01", "2025-08-28"):
        ganzhi = row.metadata["ganzhi_day"]
        if ganzhi in closes:
            close = Decimal(closes[ganzhi][seen[ganzhi]])
            seen[ganzhi] += 1
        else:
            close = Decimal(100)
        rows.append(replace(row, open=Decimal(100), high=Decimal(120),
                            low=Decimal(80), close=close))
    assert set(seen.values()) == {4}
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2025, 8, 29)))
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        params = {"start": "2025-01-04", "end": "2025-01-07"}
        days = client.get("/api/calendar/days", params=params).json()["days"]
        assert [day["signalDirection"] for day in days] == ["up", "down", "neutral"]
        assert [day["signalPct"] for day in days] == ["75.000000", "75.000000", None]
        assert [(day["upPct"], day["downPct"]) for day in days] == [
            ("75.000000", "25.000000"), ("25.000000", "75.000000"),
            ("50.000000", "50.000000"),
        ]
        assert [day["actualChangePct"] for day in days] == [
            "10.000000", "-10.000000", "10.000000",
        ]
        assert [day["actualDirection"] for day in days] == ["up", "down", "up"]
        previous = client.get("/api/calendar/days", params={**params, "basis": "previous_close"}).json()["days"]
        expected = client.get("/api/statistics/ganzhi", params={
            "ganzhi": target_ganzhi[target_dates[1]], "basis": "previous_close",
        }).json()
        match = next(m for m in expected["matches"] if m["date"] == target_dates[1])
        assert previous[1]["actualChangePct"] == match["changePct"]
        assert previous[1]["actualChangePct"] == "-18.181818"

    repo.set_meta("last_sync_ms", day_start(date(2025, 1, 5)) + 1000)
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        days = client.get("/api/calendar/days", params={
            "start": "2025-01-04", "end": "2025-01-07",
        }).json()["days"]
        assert days[0]["actualChangePct"] == "10.000000"
        assert days[1]["actualChangePct"] is None
        assert days[2]["actualChangePct"] is None


def test_calendar_strength_distribution_and_thresholds(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "strength.db")
    ganzhi = calendar.get("2025-01-04")["ganzhi_day"]
    changes = (Decimal(-5), Decimal(-3), Decimal(0), Decimal(1), Decimal(9))
    rows, targets = [], []
    for row in daily_factory("2025-01-01", "2025-10-27"):
        if row.metadata["ganzhi_day"] == ganzhi:
            change = changes[len(targets)]
            targets.append(row.period_id)
        else:
            change = Decimal(0)
        rows.append(replace(row, open=Decimal(100), high=Decimal(120), low=Decimal(80),
                            close=Decimal(100) + change))
    assert len(targets) == 5
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2025, 10, 28)))
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        params = {"start": "2025-01-04", "end": "2025-01-05"}
        result = client.get("/api/calendar/days", params=params).json()
        day = result["days"][0]
        strength = day["strength"]
        assert day["sampleCount"] == 5
        assert strength["medianAbsoluteChangePct"] == "3.000000"
        assert strength["averageChangePct"] == "0.400000"
        assert strength["upMedianChangePct"] == "5.000000"
        assert strength["downMedianChangePct"] == "-4.000000"
        assert strength["upSampleCount"] == 2
        assert strength["downSampleCount"] == 2
        assert strength["medianIntradayRangePct"] == "40.000000"
        assert strength["largeMove"]["counts"] == {"up": 1, "down": 2, "total": 3}
        assert strength["largeMove"]["probabilitiesPct"] == {
            "up": "20.000000", "down": "40.000000", "total": "60.000000",
        }
        assert result["benchmark"]["sampleCount"] == 300
        assert result["benchmark"]["strength"]["medianAbsoluteChangePct"] == "0.000000"
        threshold5 = client.get("/api/calendar/days", params={**params, "threshold": 5}).json()
        large5 = threshold5["days"][0]["strength"]["largeMove"]
        assert large5["counts"] == {"up": 1, "down": 1, "total": 2}
        assert large5["probabilitiesPct"]["total"] == "40.000000"

    # The last +9% sample is still forming, so it contributes to neither direction nor strength.
    repo.set_meta("last_sync_ms", day_start(date.fromisoformat(targets[-1])) + 1000)
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        day = client.get("/api/calendar/days", params=params).json()["days"][0]
        assert day["sampleCount"] == 4
        assert day["strength"]["medianAbsoluteChangePct"] == "2.000000"
        assert day["strength"]["largeMove"]["probabilitiesPct"]["total"] == "50.000000"


def test_calendar_strength_classifies_before_rounding(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "precision.db")
    ganzhi = calendar.get("2025-01-04")["ganzhi_day"]
    closes = tuple(map(Decimal, ("102.99999999", "103", "97", "97.00000001")))
    rows, seen = [], 0
    for row in daily_factory("2025-01-01", "2025-08-28"):
        close = closes[seen] if row.metadata["ganzhi_day"] == ganzhi else Decimal(100)
        if row.metadata["ganzhi_day"] == ganzhi:
            seen += 1
        rows.append(replace(row, open=Decimal(100), high=Decimal(110), low=Decimal(90), close=close))
    assert seen == 4
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2025, 8, 29)))
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        result = client.get("/api/calendar/days", params={"start": "2025-01-04", "end": "2025-01-05"}).json()
        assert result["days"][0]["actualChangePct"] == "3.000000"
        large = result["days"][0]["strength"]["largeMove"]
        assert large["counts"] == {"up": 1, "down": 1, "total": 2}
        assert large["probabilitiesPct"]["total"] == "50.000000"


def test_calendar_recent_window_preserves_old_actuals(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "recent.db")
    rows = daily_factory("2021-01-01", "2026-01-02")
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2026, 1, 3)))
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        params = {"start": "2021-01-04", "end": "2021-01-05"}
        full = client.get("/api/calendar/days", params=params).json()
        recent = client.get("/api/calendar/days", params={**params, "window": "recent3"}).json()
        assert recent["windowStart"] == "2023-01-03"
        day = recent["days"][0]
        expected = client.get("/api/statistics/ganzhi", params={
            "ganzhi": day["ganzhi"], "start": recent["windowStart"],
        }).json()
        assert day["strength"] == expected["strength"]
        assert day["sampleCount"] == expected["sampleCount"]
        assert day["sampleCount"] < full["days"][0]["sampleCount"]
        assert day["sampleStart"] >= recent["windowStart"]
        assert day["actualChangePct"] == full["days"][0]["actualChangePct"]
        assert day["actualChangePct"] is not None
        assert recent["benchmark"]["sampleCount"] == (date(2026, 1, 3) - date(2023, 1, 3)).days
