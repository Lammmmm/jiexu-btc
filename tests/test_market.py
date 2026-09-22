from dataclasses import replace
from datetime import date
from decimal import Decimal
import httpx
import pytest
from backend.market.binance_client import BinanceClient, BinanceError
from backend.market.repository import MarketRepository
from backend.market.updater import MarketDataService
from backend.market.validation import validate_daily, DataIntegrityError
from backend.timeutils import DAY_MS, day_start

def raw(c):
    return [c.open_time,str(c.open),str(c.high),str(c.low),str(c.close),str(c.volume),c.close_time]

def test_timezone_parameters_pagination(daily_factory):
    rows = daily_factory("2020-01-01","2022-09-27") # 1001 days
    requests = []
    def handler(request):
        p = request.url.params
        requests.append(p)
        assert p["timeZone"] == "8" and p["interval"] == "1d" and p["symbol"] == "BTCUSDT"
        selected = [c for c in rows if int(p["startTime"]) <= c.open_time <= int(p["endTime"])]
        return httpx.Response(200,json=[raw(c) for c in selected[:1000]])
    client = BinanceClient(client=httpx.Client(base_url="https://test",transport=httpx.MockTransport(handler)))
    fetched = [c for page in client.daily(rows[0].open_time,rows[-1].close_time) for c in page]
    assert len(fetched) == 1001
    assert len(requests) == 2
    assert int(requests[1]["startTime"]) == rows[1000].open_time
    assert fetched[0].open_time % DAY_MS == 16*60*60*1000

@pytest.mark.parametrize("kind", ["duplicate","invalid","nan","utc","out_of_order"])
def test_invalid_data_rejected(daily_factory,kind):
    rows = daily_factory("2026-01-01","2026-01-03")
    if kind == "duplicate":
        rows = [rows[0],rows[0]]
    elif kind == "invalid":
        rows[0] = replace(rows[0], high=Decimal(1))
    elif kind == "nan":
        rows[0] = replace(rows[0], open=Decimal("NaN"))
    elif kind == "utc":
        rows[0] = replace(rows[0], open_time=rows[0].open_time+8*3600000)
    else:
        rows.reverse()
    with pytest.raises(DataIntegrityError):
        validate_daily(rows)

def test_early_close_preserved_and_logged(daily_factory,caplog):
    row = daily_factory("2026-01-01","2026-01-01")[0]
    row = replace(row,close_time=row.open_time+12345)
    validate_daily([row])
    assert "Early source close time" in caplog.text
    assert row.close_time == row.open_time+12345

def test_incremental_repair_and_idempotency(tmp_path,daily_factory):
    rows = daily_factory("2026-01-01","2026-01-10")
    requests = []
    class Client:
        def server_time(self):
            return day_start(date(2026,1,10))+60000
        def daily(self,start,end):
            requests.append((start,end))
            selection = [c for c in rows if start <= c.open_time <= end]
            if selection:
                yield selection
    repo = MarketRepository(tmp_path/"market.db")
    service = MarketDataService(Client(),repo)
    assert service.sync()["downloaded"] == 10
    assert service.sync()["downloaded"] == 2
    with repo.connection() as db:
        db.execute("DELETE FROM daily_candles WHERE date IN ('2026-01-01','2026-01-04','2026-01-05')")
    assert service.sync()["downloaded"] == 5
    assert len(repo.all()) == 10
    assert len(requests) == 5
    assert repo.all()[0].volume == Decimal("0.00000003")

def test_failed_hole_repair_does_not_claim_success(tmp_path,daily_factory):
    rows = daily_factory("2026-01-01","2026-01-03")
    repo = MarketRepository(tmp_path/"market.db")
    repo.upsert([rows[0]])
    repo.upsert([rows[2]])
    repo.set_meta("first_available_date","2026-01-01")
    class Client:
        def server_time(self):
            return rows[-1].open_time+1234
        def daily(self,start,end):
            return iter([])
    with pytest.raises(DataIntegrityError,match="Missing"):
        MarketDataService(Client(),repo).sync()
    assert repo.get_meta("last_sync_ms") is None

def test_rate_limit_is_explicit():
    client = BinanceClient(client=httpx.Client(base_url="https://test",transport=httpx.MockTransport(
        lambda r: httpx.Response(429,headers={"Retry-After":"120"},json={"msg":"slow down"}))))
    with pytest.raises(BinanceError,match="Retry-After=120"):
        client.server_time()

def test_transport_retries_are_bounded():
    attempts = []
    def handler(request):
        attempts.append(request)
        raise httpx.ConnectError("offline")
    client = BinanceClient(client=httpx.Client(base_url="https://test",transport=httpx.MockTransport(handler)),sleep=lambda n:None)
    with pytest.raises(BinanceError):
        client.server_time()
    assert len(attempts) == 3


def test_repeated_source_anomaly_only_logs_once(daily_factory,caplog):
    from backend.market.validation import warn_early_close
    warn_early_close.cache_clear()
    row=daily_factory("2026-01-02","2026-01-02")[0]
    row=replace(row,close_time=row.open_time+12345)
    validate_daily([row])
    validate_daily([row])
    assert caplog.text.count("Early source close time")==1
    assert row.close_time==row.open_time+12345
    warn_early_close.cache_clear()
