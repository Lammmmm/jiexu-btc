import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.config import Settings, ROOT
from backend.calendar.repository import CalendarRepository
from backend.chart_service import ChartService
from backend.statistics.ganzhi import GanzhiStatisticsService
from backend.market.binance_client import BinanceClient
from backend.market.repository import MarketRepository
from backend.market.updater import MarketDataService
from backend.market.validation import DataIntegrityError
from backend.period.engine import CustomWeekPeriod
from backend.economic.service import EconomicCalendar

logger = logging.getLogger(__name__)

class SyncCoordinator:
    def __init__(self, market, settings):
        self.market, self.settings = market, settings
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.busy = False
        self.error = None
        self.last_result = None
        self.next_retry = 0.0

    def sync(self):
        with self.lock:
            if self.busy or time.time() < self.next_retry:
                return
            self.busy = True
        client = BinanceClient(self.settings.binance_url)
        try:
            self.last_result = MarketDataService(client,self.market).sync()
            self.error = None
        except Exception as exc:
            self.error = str(exc)
            self.next_retry = time.time() + max(self.settings.sync_seconds, getattr(exc,"retry_after",0))
            logger.exception("Market sync failed; retaining local cache")
        finally:
            client.close()
            with self.lock:
                self.busy = False

    def loop(self):
        while not self.stop.is_set():
            self.sync()
            self.stop.wait(self.settings.sync_seconds)

def create_app(settings=None):
    settings = settings or Settings.from_env()
    market = MarketRepository(settings.market_db)
    calendar = CalendarRepository(settings.calendar_db)
    charts = ChartService(market,calendar)
    coordinator = SyncCoordinator(market,settings)
    statistics = GanzhiStatisticsService(market,calendar)
    economics = EconomicCalendar(ROOT / "data/us-economic-events.json", settings.market_db.parent / "us-economic-events.cache.json")

    @asynccontextmanager
    async def lifespan(app):
        if settings.auto_sync:
            worker = threading.Thread(target=coordinator.loop,daemon=True,name="binance-sync")
            worker.start()
            economic_worker = threading.Thread(target=economics.loop, daemon=True, name="bls-calendar-sync")
            economic_worker.start()
        yield
        coordinator.stop.set()
        economics.stop.set()

    app = FastAPI(title="节序 · BTC 看盘 V1",lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost","testserver","[::1]"])
    app.state.coordinator = coordinator
    app.state.economics = economics

    @app.middleware("http")
    async def local_mutations_only(request:Request,call_next):
        if request.method not in ("GET","HEAD","OPTIONS"):
            origin = request.headers.get("origin")
            expected = str(request.base_url).rstrip("/")
            if origin and origin != expected:
                return JSONResponse({"detail":"Cross-origin mutation is not allowed"},status_code=403)
        return await call_next(request)

    @app.exception_handler(DataIntegrityError)
    async def integrity_error(request,exc):
        return JSONResponse({"detail":str(exc),"type":"data_integrity_error"},status_code=409)

    @app.get("/api/config")
    def config():
        return {
            "symbol":"BTCUSDT","timezone":"Asia/Shanghai","debugMode":settings.debug_mode,
            "customWeekAnchor":str(settings.custom_week_anchor) if settings.custom_week_anchor else None,
            "syncSeconds":settings.sync_seconds,"autoSync":settings.auto_sync,
            "calendar":calendar.metadata,
        }

    @app.get("/api/status")
    def status():
        raw = market.all()
        last_sync = int(market.get_meta("last_sync_ms") or 0)
        now = int(time.time()*1000)
        economic = economics.snapshot()
        return {
            "economicCalendarVersion":economic["version"], "economicCalendarError":economic["error"],
            "syncing":coordinator.busy,"error":coordinator.error,"lastSync":last_sync or None,
            "stale":not last_sync or now-last_sync > settings.sync_seconds*3000,
            "count":len(raw),"firstDate":raw[0].period_id if raw else None,
            "lastDate":raw[-1].period_id if raw else None,
            "nextRetry":int(coordinator.next_retry*1000) if coordinator.next_retry>time.time() else None,
            "lastResult":coordinator.last_result,
        }

    @app.post("/api/sync",status_code=202)
    def sync():
        if time.time() < coordinator.next_retry:
            raise HTTPException(429,detail=f"同步冷却中，{int(coordinator.next_retry-time.time())+1} 秒后可重试")
        if not coordinator.busy:
            threading.Thread(target=coordinator.sync,daemon=True,name="manual-sync").start()
        return {"accepted":True}

    @app.get("/api/economic-events")
    def economic_events():
        return economics.snapshot()

    @app.get("/api/candles")
    def candles(period:Literal["day","week","month","year"]="day",anchor:date|None=None):
        try:
            return charts.candles(period,anchor or settings.custom_week_anchor)
        except DataIntegrityError:
            raise
        except ValueError as exc:
            raise HTTPException(422,detail=str(exc)) from exc

    @app.get("/api/calendar/days")
    def calendar_days(
        start: date,
        end: date,
        basis: Literal["open", "previous_close"] = "open",
        threshold: Literal["2", "3", "5"] = "3",
        window: Literal["all", "recent3"] = "all",
    ):
        """FullCalendar visible range; end is exclusive."""
        if not start < end <= start + timedelta(days=56):
            raise HTTPException(422, detail="日历日期范围必须为连续的 1—56 天。")
        try:
            overlay = statistics.calendar_overlay(start=start, end=end, basis=basis, threshold=threshold, window=window)
        except DataIntegrityError:
            raise
        coverage_start = max(start, date.fromisoformat(calendar.metadata["start_date"]))
        coverage_end = min(end - timedelta(days=1), date.fromisoformat(calendar.metadata["end_date"]))
        rows = calendar.range(coverage_start, coverage_end) if coverage_start <= coverage_end else {}
        days = []
        for i in range((end - start).days):
            ds = str(start + timedelta(days=i))
            row = rows.get(ds)
            if row:
                rate = overlay["rates"][row["ganzhi_day"]]
                actual = overlay["actual"].get(ds, {})
                days.append({
                    "date": ds, "ganzhi": row["ganzhi_day"],
                    "solarTerm": row["solar_term"],
                    **rate,
                    "actualDirection": actual.get("actualDirection"),
                    "actualChangePct": actual.get("actualChangePct"),
                    "actualLargeMoveDirection": actual.get("actualLargeMoveDirection"),
                })
            else:
                days.append({"date": ds, "ganzhi": None, "solarTerm": None,
                             "upPct": None, "downPct": None, "sampleCount": 0,
                             "signalDirection": "none", "signalPct": None,
                             "actualDirection": None, "actualChangePct": None, "actualLargeMoveDirection": None,
                             "sampleStart": None, "sampleEnd": None, "strength": None})
        return {
            "start": str(start), "endExclusive": str(end), "basis": basis,
            "asOf": overlay["asOf"], "days": days,
            "window": overlay["window"], "windowStart": overlay["windowStart"],
            "thresholdPct": overlay["thresholdPct"], "benchmark": overlay["benchmark"],
        }

    @app.get("/api/statistics/ganzhi/options")
    def ganzhi_options():
        return {"options": statistics.options()}

    @app.get("/api/statistics/ganzhi")
    def ganzhi_statistics(
        ganzhi: str = Query(..., min_length=1, max_length=16),
        start: date | None = None,
        end: date | None = None,
        basis: Literal["open", "previous_close"] = "open",
        period: Literal["day", "month"] = "day",
    ):
        try:
            return statistics.summarize(ganzhi, start=start, end=end, basis=basis, period=period)
        except DataIntegrityError:
            raise
        except ValueError as exc:
            raise HTTPException(422, detail=str(exc)) from exc

    @app.get("/api/statistics/ganzhi/rankings")
    def ganzhi_rankings(
        start: date | None = None,
        end: date | None = None,
        basis: Literal["open", "previous_close"] = "open",
        period: Literal["day", "month"] = "day",
    ):
        try:
            return statistics.rankings(start=start, end=end, basis=basis, period=period)
        except DataIntegrityError:
            raise
        except ValueError as exc:
            raise HTTPException(422, detail=str(exc)) from exc

    @app.get("/api/debug/{day}")
    def debug(day:date,anchor:date|None=None):
        if not settings.debug_mode:
            raise HTTPException(404,detail="DEBUG_MODE 未开启")
        try:
            row = calendar.get(day)
        except ValueError as exc:
            raise HTTPException(422,detail=str(exc)) from exc
        effective_anchor = anchor or settings.custom_week_anchor
        row["custom_week_id"] = CustomWeekPeriod(effective_anchor).for_date(day).id if effective_anchor else None
        row["custom_week_anchor"] = str(effective_anchor) if effective_anchor else None
        row["candle"] = next((c.to_dict() for c in market.all() if c.period_id == str(day)),None)
        return row

    @app.get("/")
    def index():
        return FileResponse(ROOT/"frontend/index.html")

    app.mount("/static",StaticFiles(directory=ROOT/"frontend"),name="static")
    return app
