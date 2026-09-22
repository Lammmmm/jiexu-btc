from datetime import date
import pytest
from backend.chart_service import ChartService
from backend.market.repository import MarketRepository

@pytest.mark.parametrize("day,year,month",[
    ("2026-02-03","乙巳","己丑"),
    ("2026-02-04","丙午","庚寅"),
    ("2026-09-06","丙午","丙申"),
    ("2026-09-07","丙午","丁酉"),
    ("2027-02-04","丁未","壬寅"),
])
def test_calendar_ganzhi_changes_at_date_boundary(calendar,day,year,month):
    row=calendar.get(day)
    assert row["ganzhi_year"]==year
    assert row["ganzhi_month"]==month

@pytest.mark.parametrize("kind,field",[
    ("day","ganzhi_day"),("week","ganzhi_day"),
    ("month","ganzhi_month"),("year","ganzhi_year"),
])
def test_chart_label_uses_correct_cycle_and_true_start(tmp_path,calendar,daily_factory,kind,field):
    repo=MarketRepository(tmp_path/"market.db")
    # The week starts Aug 30, month Aug 7, year Feb 4: all before cached Sep 1.
    repo.upsert(daily_factory("2026-09-01","2026-09-17"))
    result=ChartService(repo,calendar).candles(kind,anchor=date(2026,8,30))
    for candle in result["candles"]:
        m=candle["metadata"]
        start=calendar.get(m["startDate"])
        assert m["displayGanzhi"]==start[field]
        assert m["ganzhiDate"]==m["startDate"]
    if kind=="week":
        m=result["candles"][0]["metadata"]
        assert m["startDate"]=="2026-08-30"
        assert m["observedStart"]=="2026-09-01"
        assert m["displayGanzhi"]!=calendar.get("2026-09-01")["ganzhi_day"]
