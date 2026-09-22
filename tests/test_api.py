from dataclasses import replace
from datetime import date
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import Settings,ROOT
from backend.market.repository import MarketRepository

def client_for(tmp_path,daily_factory,debug=True):
    settings = Settings(market_db=tmp_path/"market.db",calendar_db=ROOT/"data/calendar.db",auto_sync=False,debug_mode=debug)
    repo=MarketRepository(settings.market_db)
    rows=daily_factory("2026-09-01","2026-09-17")
    repo.upsert(rows)
    repo.set_meta("last_sync_ms",rows[-1].open_time+1000)
    return TestClient(create_app(settings))

def test_period_routes_and_no_default_anchor(tmp_path,daily_factory):
    with client_for(tmp_path,daily_factory) as client:
        assert client.get("/api/candles?period=day").json()["sourceCount"]==17
        assert client.get("/api/candles?period=week").status_code==422
        assert client.get("/api/candles?period=week&anchor=2026-01-01").status_code==200
        assert len(client.get("/api/candles?period=month").json()["candles"])==2
        assert len(client.get("/api/candles?period=year").json()["candles"])==1
        assert client.get("/api/candles?period=garbage").status_code==422
        assert client.get("/api/candles?period=week&anchor=bad").status_code==422

def test_debug_and_status(tmp_path,daily_factory):
    with client_for(tmp_path,daily_factory) as client:
        row=client.get("/api/debug/2026-09-07?anchor=2026-01-01").json()
        assert row["ganzhi_day"]=="甲申"
        assert row["solar_month_id"]=="2026-bailu"
        assert row["custom_week_id"].startswith("week:2026-01-01:")
        assert row["candle"]["periodId"]=="2026-09-07"
        assert client.get("/api/debug/1899-01-01").status_code==422
        assert client.get("/api/status").json()["count"]==17
        assert client.get("/api/config").json()["customWeekAnchor"] is None

def test_debug_disabled_and_cross_origin_guard(tmp_path,daily_factory):
    with client_for(tmp_path,daily_factory,False) as client:
        assert client.get("/api/debug/2026-09-07").status_code==404
        assert client.post("/api/sync",headers={"Origin":"https://unrelated.example"}).status_code==403
