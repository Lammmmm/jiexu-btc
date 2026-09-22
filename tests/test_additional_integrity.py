from dataclasses import replace
from datetime import date
from decimal import Decimal
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app, SyncCoordinator
from backend.config import ROOT, Settings
from backend.market.binance_client import BinanceClient, BinanceError
from backend.market.repository import MarketRepository
from backend.market.updater import MarketDataService

def test_unclosed_yesterday_gets_final_prices(tmp_path,daily_factory):
    rows=daily_factory("2026-01-01","2026-01-03")
    repo=MarketRepository(tmp_path/"market.db")
    repo.upsert(rows[:2])
    repo.set_meta("first_available_date","2026-01-01")
    final_yesterday=replace(rows[1],close=rows[1].close+1,volume=Decimal("99.12345678"))
    fresh=[rows[0],final_yesterday,rows[2]]
    class Client:
        def server_time(self): return rows[2].open_time+1000
        def daily(self,start,end):
            yield [c for c in fresh if start<=c.open_time<=end]
    MarketDataService(Client(),repo).sync()
    assert repo.all()[1].close==final_yesterday.close
    assert repo.all()[1].volume==Decimal("99.12345678")

def test_retry_after_propagates_to_coordinator(tmp_path,monkeypatch):
    import backend.app as module
    class Client:
        def __init__(self,*args): pass
        def server_time(self): raise BinanceError("rate limited",retry_after=3600)
        def close(self): pass
    monkeypatch.setattr(module,"BinanceClient",Client)
    monkeypatch.setattr(module.time,"time",lambda:1000)
    settings=Settings(market_db=tmp_path/"market.db")
    sync=SyncCoordinator(MarketRepository(settings.market_db),settings)
    sync.sync()
    assert sync.next_retry==4600
    assert sync.error=="rate limited"
    assert not sync.busy

def test_api_reports_integrity_failure(tmp_path,daily_factory):
    settings=Settings(market_db=tmp_path/"market.db",calendar_db=ROOT/"data/calendar.db",auto_sync=False)
    repo=MarketRepository(settings.market_db)
    rows=daily_factory("2026-01-01","2026-01-03")
    repo.upsert(rows)
    with repo.connection() as db:
        db.execute("DELETE FROM daily_candles WHERE date='2026-01-02'")
    with TestClient(create_app(settings)) as client:
        result=client.get("/api/candles?period=year")
    assert result.status_code==409
    assert result.json()["type"]=="data_integrity_error"

def test_server_error_retry_then_success():
    count=0
    def handler(request):
        nonlocal count
        count+=1
        return httpx.Response(503 if count<3 else 200,json={"serverTime":12345})
    client=BinanceClient(client=httpx.Client(base_url="https://test",transport=httpx.MockTransport(handler)),sleep=lambda _:None)
    assert client.server_time()==12345
    assert count==3
