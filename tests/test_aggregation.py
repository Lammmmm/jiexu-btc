from datetime import date
from decimal import Decimal
from dataclasses import replace
import pytest
from backend.aggregation.aggregator import CandleAggregator
from backend.period.engine import CustomWeekPeriod, SolarMonthPeriod, SolarYearPeriod, resolver_for
from backend.timeutils import day_start
from backend.market.validation import DataIntegrityError

AS_OF = day_start(date(2027,1,1))

def test_month_ohlcv_exact(daily_factory):
    daily = daily_factory("2025-09-07", "2025-10-07")
    result = CandleAggregator().aggregate(daily, SolarMonthPeriod(), as_of_ms=AS_OF)
    assert len(result) == 1
    c = result[0]
    assert c.period_id == "2025-bailu"
    assert (c.open,c.high,c.low,c.close,c.volume) == (
        Decimal("100.00000001"),Decimal("135.00000001"),Decimal("98.00000001"),
        Decimal("133.00000001"),Decimal("465.00000093"))
    assert c.metadata["isComplete"]
    assert c.metadata["endDate"] == "2025-10-07"

def test_year_ohlcv_exact(daily_factory):
    daily = daily_factory("2025-02-03", "2026-02-03")
    result = CandleAggregator().aggregate(daily, SolarYearPeriod(), as_of_ms=AS_OF)
    assert len(result) == 1
    c = result[0]
    assert (c.open,c.high,c.low,c.close,c.volume) == (
        Decimal("100.00000001"), Decimal("470.00000001"), Decimal("98.00000001"),
        Decimal("468.00000001"), Decimal("66795.00001098"))
    assert c.metadata["dayCount"] == 366
    assert c.metadata["isComplete"]

@pytest.mark.parametrize("day,index,start", [
    ("2026-01-01",0,"2026-01-01"),("2026-01-07",0,"2026-01-01"),
    ("2026-01-08",1,"2026-01-08"),("2026-01-14",1,"2026-01-08"),
    ("2026-01-15",2,"2026-01-15"),("2025-12-31",-1,"2025-12-25"),
    ("2025-12-24",-2,"2025-12-18"),
])
def test_custom_week_boundaries(day,index,start):
    p = CustomWeekPeriod(date(2026,1,1)).for_date(date.fromisoformat(day))
    assert p.id == f"week:2026-01-01:{index}"
    assert str(p.start) == start

def test_custom_week_ohlc(daily_factory):
    daily = daily_factory("2026-01-01","2026-01-21")
    result = CandleAggregator().aggregate(daily,CustomWeekPeriod(date(2026,1,1)),as_of_ms=AS_OF)
    assert len(result) == 3
    for i,c in enumerate(result):
        start = Decimal("100.00000001") + i*7
        assert (c.open,c.high,c.low,c.close,c.volume) == (
            start,start+11,start-2,start+9,Decimal(i*49+21)+Decimal("0.00000021"))
        assert c.metadata["dayCount"] == 7

def test_unconfigured_anchor_rejected():
    with pytest.raises(ValueError, match="CUSTOM_WEEK_ANCHOR"):
        resolver_for("week")

def test_partial_and_live_periods(daily_factory):
    daily = daily_factory("2026-09-10","2026-09-17")
    c = CandleAggregator().aggregate(daily,SolarMonthPeriod(),as_of_ms=day_start(date(2026,9,17)))[0]
    assert not c.metadata["isComplete"]
    assert not c.metadata["isClosed"]
    assert c.metadata["startDate"] == "2026-09-07"
    assert c.metadata["observedStart"] == "2026-09-10"

def test_missing_candle_prevents_aggregation(daily_factory):
    daily = daily_factory("2026-01-01","2026-01-05")
    with pytest.raises(DataIntegrityError,match="Missing"):
        CandleAggregator().aggregate(daily[:2]+daily[3:],SolarMonthPeriod(),as_of_ms=AS_OF)

def test_anomaly_propagates(daily_factory):
    daily = daily_factory("2025-09-07","2025-10-07")
    daily[0] = replace(daily[0],metadata={**daily[0].metadata,"sourceAnomaly":True})
    c = CandleAggregator().aggregate(daily,SolarMonthPeriod(),as_of_ms=AS_OF)[0]
    assert c.metadata["sourceAnomalies"] == ["2025-09-07"]
    assert not c.metadata["isComplete"]
