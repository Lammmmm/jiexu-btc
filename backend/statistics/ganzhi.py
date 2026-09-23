"""Historical Ganzhi frequencies for daily candles and solar-month candles."""
from fractions import Fraction
from decimal import Decimal
from statistics import median

from backend.aggregation.aggregator import CandleAggregator
from backend.period.engine import SolarMonthPeriod
from backend.calendar.service import CalendarService
from backend.market.validation import DataIntegrityError, validate_daily
from backend.timeutils import DAY_MS

EXCLUSION_REASONS = ("unclosed", "source_anomaly", "listing_day", "invalid_previous_close", "incomplete_period")

def decimal_string(value):
    return format(value.quantize(Decimal("0.000001")), "f") if value is not None else None


def yearly_breakdown(matches):
    """Calendar-year bins [January 1, next January 1), using the same filtered rows."""
    years = {}
    for match in matches:
        year = int(match["date"][:4])
        if year not in years:
            years[year] = {
                "year": year, "start": f"{year}-01-01", "endExclusive": f"{year + 1}-01-01",
                "matchedCount": 0, "sampleCount": 0, "excludedCount": 0,
                "counts": {"up": 0, "down": 0, "flat": 0},
            }
        bucket = years[year]
        bucket["matchedCount"] += 1
        if match["included"]:
            bucket["sampleCount"] += 1
            bucket["counts"][match["direction"]] += 1
        else:
            bucket["excludedCount"] += 1
    for bucket in years.values():
        count = bucket["sampleCount"]
        bucket["probabilitiesPct"] = {
            direction: decimal_string(Decimal(n) / count * 100) if count else None
            for direction, n in bucket["counts"].items()
        }
    return [years[year] for year in sorted(years, reverse=True)]


class GanzhiStatisticsService:
    def __init__(self, market_repository, calendar_repository):
        self.market = market_repository
        self.calendar = calendar_repository
        self.calendar_service = CalendarService(calendar_repository)

    def options(self):
        return self.calendar.ganzhi_options()

    def summarize(self, ganzhi, *, start=None, end=None, basis="open", period="day"):
        ganzhi = ganzhi.strip().removesuffix("月" if period == "month" else "日").strip()
        if ganzhi not in self.options():
            raise ValueError("请输入有效的六十甲子干支，例如丁酉、丙午。")
        self._validate_filters(start, end, basis, period)
        return self._summarize(ganzhi, self._prepare(period), start=start, end=end, basis=basis, period=period)

    def rankings(self, *, start=None, end=None, basis="open", period="day"):
        self._validate_filters(start, end, basis, period)
        options = self.options()
        prepared = self._prepare(period)
        summaries = []
        for ganzhi in options:
            summary = self._summarize(ganzhi, prepared, start=start, end=end, basis=basis, period=period)
            summary.pop("matches")
            summary.pop("yearly", None)
            summaries.append(summary)
        order = {ganzhi: index for index, ganzhi in enumerate(options)}

        def ranked(direction):
            def key(row):
                n = row["sampleCount"]
                return (n == 0, -Fraction(row["counts"][direction], n) if n else 0,
                        -n, order[row["ganzhi"]])
            return [dict(row, rank=i + 1) for i, row in enumerate(sorted(summaries, key=key))]

        raw, cache, _, _ = prepared
        return {
            "symbol": "BTCUSDT", "timezone": "Asia/Shanghai", "period": period, "basis": basis,
            "start": str(start) if start else None, "end": str(end) if end else None,
            "asOf": int(cache.get("last_sync_ms") or 0) or None,
            "availableStart": raw[0].period_id if raw else None,
            "availableEnd": raw[-1].period_id if raw else None,
            "totalGanzhi": len(options),
            "totalSamples": sum(row["sampleCount"] for row in summaries),
            "totalExcluded": sum(row["excludedCount"] for row in summaries),
            "upRanking": ranked("up"), "downRanking": ranked("down"),
        }

    def _validate_filters(self, start, end, basis, period):
        if period not in ("day", "month"):
            raise ValueError("统计周期必须是 day 或 month。")
        if basis not in ("open", "previous_close"):
            raise ValueError("涨跌口径必须是 open 或 previous_close。")
        if start and end and start > end:
            raise ValueError("开始日期不能晚于结束日期。")
        for day in (start, end):
            if day and not self.calendar.metadata["start_date"] <= str(day) <= self.calendar.metadata["end_date"]:
                raise ValueError("筛选日期超出本地历法范围（1900—2100）。")

    def _prepare(self, period):
        raw, cache = self.market.snapshot()
        validate_daily(raw)
        if raw and cache.get("first_available_date") and raw[0].period_id != cache["first_available_date"]:
            raise DataIntegrityError("Missing daily candle at cache start")
        joined = self.calendar_service.join(raw)
        if period == "month":
            joined = CandleAggregator().aggregate(
                joined, SolarMonthPeriod(), as_of_ms=int(cache.get("last_sync_ms") or 0))
            starts = self.calendar.range(joined[0].metadata["startDate"], joined[-1].metadata["startDate"]) if joined else {}
            for candle in joined:
                ds = candle.metadata["startDate"]
                candle.metadata.update({
                    "date": ds, "ganzhi_month": starts[ds]["ganzhi_month"],
                    "sourceAnomaly": bool(candle.metadata["sourceAnomalies"]),
                })
        groups = {}
        for i, candle in enumerate(joined):
            groups.setdefault(candle.metadata["ganzhi_month" if period == "month" else "ganzhi_day"], []).append((i, candle))
        return raw, cache, joined, groups

    def _exclusion(self, candle, cache, period):
        as_of = int(cache.get("last_sync_ms") or 0)
        end_ms = candle.close_time if period == "month" else candle.open_time + DAY_MS - 1
        if end_ms >= as_of:
            return "unclosed"
        if candle.metadata["sourceAnomaly"]:
            return "source_anomaly"
        if period == "month" and not candle.metadata["coverageComplete"]:
            return "incomplete_period"
        first = cache.get("first_available_date")
        ds = candle.metadata["date"]
        if first and ds <= first <= candle.metadata.get("endDate", ds):
            return "listing_day"
        return None

    def _summarize(self, ganzhi, prepared, *, start, end, basis, period):
        raw, cache, joined, groups = prepared
        as_of = int(cache.get("last_sync_ms") or 0)
        counts = {"up": 0, "down": 0, "flat": 0}
        excluded = dict.fromkeys(EXCLUSION_REASONS, 0)
        changes = []
        matches = []
        for i, candle in groups.get(ganzhi, []):
            ds = candle.metadata["date"]
            if (start and ds < str(start)) or (end and ds > str(end)):
                continue
            reason = self._exclusion(candle, cache, period)
            baseline = candle.open
            if reason is None and basis == "previous_close":
                previous = joined[i - 1] if i else None
                if previous is None or previous.metadata["sourceAnomaly"] or (
                    period == "month" and self._exclusion(previous, cache, period)
                ):
                    reason = "invalid_previous_close"
                else:
                    baseline = previous.close
            direction, change = None, None
            if reason:
                excluded[reason] += 1
            else:
                direction = "up" if candle.close > baseline else "down" if candle.close < baseline else "flat"
                change = (candle.close / baseline - 1) * 100
                counts[direction] += 1
                changes.append(change)
            matches.append({
                "date": ds, "endDate": candle.metadata.get("endDate", ds),
                "periodId": candle.period_id, "ganzhi": ganzhi,
                **{key: str(getattr(candle, key)) for key in ("open", "high", "low", "close", "volume")},
                "baseline": str(baseline) if reason is None else None,
                "direction": direction, "changePct": decimal_string(change),
                "included": reason is None, "excludedReason": reason,
            })

        sample_count = sum(counts.values())
        probabilities = {
            key: decimal_string(Decimal(count) / sample_count * 100) if sample_count else None
            for key, count in counts.items()
        }
        included_dates = [r["date"] for r in matches if r["included"]]
        return {
            "ganzhi": ganzhi, "symbol": "BTCUSDT", "timezone": "Asia/Shanghai", "period": period,
            "basis": basis, "start": str(start) if start else None, "end": str(end) if end else None,
            "asOf": as_of or None,
            "availableStart": raw[0].period_id if raw else None,
            "availableEnd": raw[-1].period_id if raw else None,
            "matchedCount": len(matches), "sampleCount": sample_count,
            "excludedCount": sum(excluded.values()), "excluded": excluded,
            "counts": counts, "probabilitiesPct": probabilities,
            "sampleStart": included_dates[0] if included_dates else None,
            "sampleEnd": included_dates[-1] if included_dates else None,
            "averageChangePct": decimal_string(sum(changes, Decimal(0)) / sample_count) if sample_count else None,
            "medianChangePct": decimal_string(median(changes)) if changes else None,
            "bestChangePct": decimal_string(max(changes)) if changes else None,
            "worstChangePct": decimal_string(min(changes)) if changes else None,
            "matches": list(reversed(matches)),
            "yearly": yearly_breakdown(matches) if period == "day" else [],
        }
