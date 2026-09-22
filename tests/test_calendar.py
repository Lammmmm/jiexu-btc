from datetime import date, timedelta
import hashlib
import json
import random
import sqlite3
import pytest
from lunar_python import Solar
from backend.config import ROOT

def test_coverage_and_manifest(calendar):
    manifest = json.loads((ROOT / "data/calendar_source/manifest.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((ROOT / "data/calendar.db").read_bytes()).hexdigest() == manifest["database_sha256"]
    with sqlite3.connect(calendar.path) as db:
        assert db.execute("SELECT count(*) FROM calendar_days").fetchone()[0] == 73414
    assert calendar.get("1900-01-01")["solar_year_id"] == 1899
    assert calendar.get("2100-12-31")["year_end"].startswith("2101-")

@pytest.mark.parametrize("day,year", [("2026-02-03",2025),("2026-02-04",2026),("2026-02-05",2026)])
def test_lichun(calendar, day, year):
    assert calendar.get(day)["solar_year_id"] == year

@pytest.mark.parametrize("day,month", [("2026-09-06","2026-liqiu"),("2026-09-07","2026-bailu"),("2026-09-08","2026-bailu")])
def test_bailu(calendar, day, month):
    assert calendar.get(day)["solar_month_id"] == month

@pytest.mark.parametrize("day", ["2026-01-05","2026-01-20","2026-02-03"])
def test_xiaohan_belongs_to_previous_year(calendar, day):
    row = calendar.get(day)
    assert row["solar_year_id"] == 2025
    assert row["solar_month_id"] == "2025-xiaohan"

RANDOM_DATES = [date(1900,1,1) + timedelta(days=i) for i in random.Random(42).sample(range(73414), 25)]
@pytest.mark.parametrize("day", RANDOM_DATES)
def test_ganzhi_against_original_library(calendar, day):
    lunar = Solar.fromYmd(day.year,day.month,day.day).getLunar()
    assert calendar.get(day)["ganzhi_day"] == lunar.getDayInGanZhi()
    assert calendar.get(day)["ganzhi_month"] == lunar.getMonthInGanZhi()
    assert calendar.get(day)["ganzhi_year"] == lunar.getYearInGanZhiByLiChun()

def test_term_dates_vary_and_middle_qi_not_month_boundary(calendar):
    assert calendar.get("2024-02-04")["solar_term"] == "立春"
    assert calendar.get("2025-02-03")["solar_term"] == "立春"
    assert calendar.get("2026-09-23")["solar_term"] == "秋分"
    assert calendar.get("2026-09-23")["solar_month_id"] == "2026-bailu"
    assert calendar.get("2026-09-07")["ganzhi_day"] == "甲申"
    assert calendar.get("2026-09-07")["solar_term_exact_time"] == "2026-09-07T22:41:16+08:00"

def test_all_solar_terms_against_source(calendar):
    with sqlite3.connect(calendar.path) as db:
        rows = db.execute("SELECT date,solar_term,solar_term_exact_time FROM calendar_days WHERE solar_term IS NOT NULL").fetchall()
    assert len(rows) == 201 * 24
    for ds, name, exact in rows:
        day = date.fromisoformat(ds)
        lunar = Solar.fromYmd(day.year,day.month,day.day).getLunar()
        assert lunar.getJieQi() == name
        assert any(s.toYmdHms().replace(" ","T")+"+08:00" == exact for s in lunar.getJieQiTable().values())

def test_out_of_range_and_leap_date(calendar):
    assert calendar.get("2000-02-29")["date"] == "2000-02-29"
    with pytest.raises(ValueError):
        calendar.get("2101-01-01")
