from backend.aggregation.aggregator import CandleAggregator
from backend.calendar.service import CalendarService
from backend.market.validation import DataIntegrityError
from backend.period.engine import resolver_for

class ChartService:
    def __init__(self, market_repository, calendar_repository):
        self.market = market_repository
        self.calendar = CalendarService(calendar_repository)
        self.aggregator = CandleAggregator()

    def candles(self, kind, anchor=None):
        resolver = resolver_for(kind, anchor)
        raw = self.market.all()
        first = self.market.get_meta("first_available_date")
        if raw and first and raw[0].period_id != first:
            raise DataIntegrityError(f"Missing daily candle at cache start: {first}")
        joined = self.calendar.join(raw)
        as_of = int(self.market.get_meta("last_sync_ms") or 0)
        result = self.aggregator.aggregate(joined, resolver, as_of_ms=as_of)
        if result:
            # Resolve the theoretical period start, even when the first observed
            # market candle arrives later (listing or partially cached periods).
            starts = self.calendar.repository.range(
                result[0].metadata["startDate"], result[-1].metadata["startDate"])
            field = {"day": "ganzhi_day", "week": "ganzhi_day",
                     "month": "ganzhi_month", "year": "ganzhi_year"}[kind]
            for candle in result:
                day = candle.metadata["startDate"]
                if day not in starts:
                    raise DataIntegrityError(f"Missing calendar period start: {day}")
                row = starts[day]
                candle.metadata.update({
                    "displayGanzhi": row[field],
                    "ganzhiBasis": "period_start_day" if kind == "week" else kind,
                    "ganzhiDate": day,
                    "ganzhi_day": row["ganzhi_day"],
                    "ganzhi_month": row["ganzhi_month"],
                    "ganzhi_year": row["ganzhi_year"],
                    "solar_year_id": row["solar_year_id"],
                })
        return {
            "symbol": "BTCUSDT", "market": "Binance Spot", "timezone": "Asia/Shanghai",
            "period": kind, "customWeekAnchor": str(anchor) if anchor else None,
            "asOf": as_of or None, "sourceCount": len(raw),
            "sourceAnomalies": [c.period_id for c in joined if c.metadata["sourceAnomaly"]],
            "candles": [c.to_dict() for c in result],
        }
