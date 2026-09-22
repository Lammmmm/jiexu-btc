"""Real-data verification, separate from offline unit tests; saves an auditable report."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
import httpx
from backend.config import Settings, ROOT
from backend.chart_service import ChartService
from backend.market.repository import MarketRepository
from backend.calendar.repository import CalendarRepository
from backend.timeutils import day_start, DAY_MS

def main():
    s = Settings.from_env()
    market = MarketRepository(s.market_db)
    calendar = CalendarRepository(s.calendar_db)
    charts = ChartService(market,calendar)
    report = {"marketCount":len(market.all()),"checks":[]}
    for kind,pid,start,end in [
        ("month","2025-bailu","2025-09-07","2025-10-07"),
        ("year","2025","2025-02-03","2026-02-03"),
    ]:
        with market.connection() as db:
            rows = db.execute("SELECT * FROM daily_candles WHERE date BETWEEN ? AND ? ORDER BY date",(start,end)).fetchall()
        # Independent recomputation from original SQLite text values; no aggregator helpers.
        expected = {
            "open":rows[0]["open"],
            "high":str(max(Decimal(r["high"]) for r in rows)),
            "low":str(min(Decimal(r["low"]) for r in rows)),
            "close":rows[-1]["close"],
            "volume":str(sum((Decimal(r["volume"]) for r in rows),Decimal(0))),
        }
        actual = next(c for c in charts.candles(kind)["candles"] if c["periodId"] == pid)
        assert all(Decimal(actual[k]) == Decimal(v) for k,v in expected.items())
        assert actual["metadata"]["isComplete"]
        report["checks"].append({"kind":kind,"periodId":pid,"start":start,"end":end,"days":len(rows),
                                 "expected":expected,"actual":{k:actual[k] for k in expected},"passed":True})
    # Confirm timezone-adjusted 1d prices independently against 24 official 1h bars.
    d = date(2025,9,7)
    with httpx.Client(base_url=s.binance_url,timeout=20) as client:
        response = client.get("/api/v3/klines",params={"symbol":"BTCUSDT","interval":"1h",
            "startTime":day_start(d),"endTime":day_start(d)+DAY_MS-1,"limit":24})
        response.raise_for_status()
        hours = response.json()
    assert len(hours)==24 and hours[0][0]==day_start(d)
    expected = {"open":hours[0][1],"high":str(max(Decimal(r[2]) for r in hours)),
                "low":str(min(Decimal(r[3]) for r in hours)),"close":hours[-1][4],
                "volume":str(sum((Decimal(r[5]) for r in hours),Decimal(0)))}
    daily = next(c for c in market.all() if c.period_id==str(d))
    assert all(getattr(daily,k)==Decimal(v) for k,v in expected.items())
    report["checks"].append({"kind":"UTC+8 1d vs 24 hourly bars","date":str(d),"expected":expected,"passed":True})
    report["sourceAnomalies"] = charts.candles("day")["sourceAnomalies"]
    target = ROOT/"artifacts/market-verification.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
