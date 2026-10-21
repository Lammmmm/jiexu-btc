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
        assert strength["intradayRangeStart"] == "2023-01-01"
        assert strength["intradayRangeSampleCount"] == 5
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
        assert day["strength"]["intradayRangeSampleCount"] == 4
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
        targets = [row.period_id for row in rows if row.metadata["ganzhi_day"] == ganzhi]
        for target, direction in zip(targets, (None, "up", "down", None)):
            end = str(date.fromordinal(date.fromisoformat(target).toordinal() + 1))
            day = client.get("/api/calendar/days", params={"start": target, "end": end}).json()["days"][0]
            assert day["actualLargeMoveDirection"] == direction
            above = client.get("/api/calendar/days", params={"start": target, "end": end, "threshold": 5}).json()["days"][0]
            assert above["actualLargeMoveDirection"] is None


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
        assert recent["days"][0]["strength"]["intradayRangeStart"] == recent["windowStart"]
        assert recent["benchmark"]["strength"]["intradayRangeStart"] == recent["windowStart"]
        assert recent["days"][0]["strength"]["start"] == recent["windowStart"]
        assert recent["days"][0]["strength"]["sampleCount"] == recent["days"][0]["sampleCount"]
        assert recent["days"][0]["strength"]["largeMove"]["sampleCount"] == recent["days"][0]["sampleCount"]
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


def test_strength_uses_2023_onward_without_changing_direction_samples(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "strength-cutoff.db")
    target = "2023-01-01"
    ganzhi = calendar.get(target)["ganzhi_day"]
    rows = []
    for row in daily_factory("2022-07-05", "2023-03-31"):
        early = row.period_id < target
        matched = row.metadata["ganzhi_day"] == ganzhi
        close = Decimal(150) if early and matched else Decimal(100)
        if row.period_id == "2022-12-31":
            close = Decimal(110)  # Previous-close mode may read outside the strength window.
        if row.period_id == target:
            close = Decimal(103)
        elif row.period_id == "2023-03-02":
            close = Decimal(95)
        high = Decimal(150) if early else Decimal(106) if row.period_id == "2023-03-02" else Decimal(104)
        low = Decimal(50) if early else Decimal(90) if row.period_id == "2023-03-02" else Decimal(98)
        rows.append(replace(row, open=Decimal(100), high=high, low=low, close=close))
    repo.upsert(rows)
    repo.set_meta("last_sync_ms", day_start(date(2023, 4, 1)))
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        params = {"start": target, "end": "2023-01-02"}
        result = client.get("/api/calendar/days", params=params).json()
        day = result["days"][0]
        strength = day["strength"]
        # Three pre-2023 +50% returns/ranges belong only to the direction sample.
        assert day["sampleCount"] == 5
        assert day["upPct"] == "80.000000"
        assert strength["start"] == "2023-01-01"
        assert strength["sampleCount"] == 2
        assert strength["sampleStart"] == "2023-01-01"
        assert strength["sampleEnd"] == "2023-03-02"
        assert strength["medianAbsoluteChangePct"] == "4.000000"
        assert strength["averageChangePct"] == "-1.000000"
        assert strength["upMedianChangePct"] == "3.000000"
        assert strength["downMedianChangePct"] == "-5.000000"
        assert strength["upSampleCount"] == strength["downSampleCount"] == 1
        assert strength["medianIntradayRangePct"] == "11.000000"
        assert strength["intradayRangeStart"] == strength["start"]
        assert strength["intradayRangeSampleCount"] == 2
        assert strength["intradayRangeSampleStart"] == strength["sampleStart"]
        assert strength["intradayRangeSampleEnd"] == strength["sampleEnd"]
        large = strength["largeMove"]
        assert large["start"] == strength["start"]
        assert large["sampleCount"] == 2
        assert large["counts"] == {"up": 1, "down": 1, "total": 2}
        assert large["probabilitiesPct"] == {"up": "50.000000", "down": "50.000000", "total": "100.000000"}
        benchmark = result["benchmark"]["strength"]
        assert benchmark["medianIntradayRangePct"] == "6.000000"
        assert benchmark["start"] == "2023-01-01"
        assert benchmark["sampleCount"] == benchmark["largeMove"]["sampleCount"] == 90
        assert benchmark["sampleStart"] == "2023-01-01"
        assert benchmark["sampleEnd"] == "2023-03-31"

        summary = client.get("/api/statistics/ganzhi", params={"ganzhi": ganzhi}).json()
        assert summary["sampleCount"] == 5
        assert summary["averageChangePct"] == "-1.000000"
        assert summary["medianChangePct"] == "-1.000000"
        assert summary["bestChangePct"] == "3.000000"
        assert summary["worstChangePct"] == "-5.000000"
        assert summary["strength"] == strength
        ranking = client.get("/api/statistics/ganzhi/rankings").json()
        ranked = next(row for row in ranking["upRanking"] if row["ganzhi"] == ganzhi)
        assert ranked["strength"] == strength
        assert ranked["probabilitiesPct"] == summary["probabilitiesPct"]

        threshold5 = client.get("/api/calendar/days", params={**params, "threshold": 5}).json()["days"][0]["strength"]["largeMove"]
        assert threshold5["sampleCount"] == 2
        assert threshold5["counts"] == {"up": 0, "down": 1, "total": 1}
        assert threshold5["probabilitiesPct"]["total"] == "50.000000"

        filtered = client.get("/api/statistics/ganzhi", params={
            "ganzhi": ganzhi, "start": "2023-01-02", "end": "2023-03-02",
        }).json()["strength"]
        assert filtered["start"] == "2023-01-02"
        assert filtered["sampleCount"] == 1
        assert filtered["sampleStart"] == filtered["sampleEnd"] == "2023-03-02"
        assert filtered["medianAbsoluteChangePct"] == "5.000000"
        assert filtered["medianIntradayRangePct"] == "16.000000"

        previous = client.get("/api/calendar/days", params={**params, "basis": "previous_close"}).json()["days"][0]
        assert previous["sampleCount"] == 4  # First cached day has no previous close.
        assert previous["upPct"] == "50.000000"
        assert previous["strength"]["sampleCount"] == 2
        assert previous["strength"]["upSampleCount"] == 0
        assert previous["strength"]["downSampleCount"] == 2
        assert previous["strength"]["medianIntradayRangePct"] == strength["medianIntradayRangePct"]
        assert previous["strength"]["largeMove"]["probabilitiesPct"]["down"] == "100.000000"
        assert previous["actualChangePct"] == "-6.363636"
        assert previous["actualLargeMoveDirection"] == "down"

        old = client.get("/api/calendar/days", params={
            "start": "2022-09-03", "end": "2022-09-04",
        }).json()["days"][0]
        assert old["ganzhi"] == ganzhi
        assert old["actualChangePct"] == "50.000000"
        assert old["actualLargeMoveDirection"] == "up"
        assert old["strength"] == strength

        only_old = client.get("/api/statistics/ganzhi", params={
            "ganzhi": ganzhi, "end": "2022-12-31",
        }).json()
        assert only_old["sampleCount"] == 3
        assert only_old["probabilitiesPct"]["up"] == "100.000000"
        assert only_old["strength"]["sampleCount"] == 0
        assert only_old["averageChangePct"] is None
        assert only_old["medianChangePct"] is None
        assert only_old["bestChangePct"] is None
        assert only_old["worstChangePct"] is None


def test_strength_has_no_samples_before_2023(tmp_path, calendar, daily_factory):
    repo = MarketRepository(tmp_path / "early-strength.db")
    repo.upsert(daily_factory("2022-07-05", "2022-12-31"))
    repo.set_meta("last_sync_ms", day_start(date(2023, 1, 1)))
    with TestClient(create_app(Settings(market_db=repo.path, auto_sync=False))) as client:
        result = client.get("/api/calendar/days", params={
            "start": "2022-09-03", "end": "2022-09-04",
        }).json()
        day = result["days"][0]
        assert day["sampleCount"] > 0
        assert day["upPct"] is not None
        assert day["actualChangePct"] is not None
        for strength in (day["strength"], result["benchmark"]["strength"]):
            assert strength["start"] == "2023-01-01"
            assert strength["sampleCount"] == strength["intradayRangeSampleCount"] == 0
            assert strength["sampleStart"] is None
            assert strength["sampleEnd"] is None
            for metric in ("medianAbsoluteChangePct", "averageChangePct", "upMedianChangePct",
                           "downMedianChangePct", "medianIntradayRangePct"):
                assert strength[metric] is None
            assert strength["largeMove"]["sampleCount"] == 0
            assert strength["largeMove"]["counts"] == {"up": 0, "down": 0, "total": 0}
            assert strength["largeMove"]["probabilitiesPct"] == {"up": None, "down": None, "total": None}
