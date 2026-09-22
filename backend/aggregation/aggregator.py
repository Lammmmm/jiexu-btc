from decimal import Decimal
from itertools import groupby
from backend.models import Candle
from backend.timeutils import DAY_MS, day_start
from backend.market.validation import validate_daily

class CandleAggregator:
    def aggregate(self, candles, resolver, *, as_of_ms):
        validate_daily(candles)
        result = []
        keyed = [(resolver.resolve(c), c) for c in candles]
        for period, group in groupby(keyed, key=lambda x: x[0]):
            items = [c for _, c in group]
            first, last = items[0], items[-1]
            expected = (period.end - period.start).days + 1
            end_ms = day_start(period.end) + DAY_MS - 1
            anomalies = [c.metadata["date"] for c in items if c.metadata.get("sourceAnomaly")]
            coverage = len(items) == expected and first.metadata["date"] == str(period.start) and last.metadata["date"] == str(period.end)
            closed = as_of_ms > end_ms
            warnings = []
            if not coverage:
                warnings.append("周期数据尚未覆盖完整日期范围")
            if not closed:
                warnings.append("该周期尚未收盘（按最近成功同步时刻）")
            if anomalies:
                warnings.append("交易所提前收盘时间异常：" + "、".join(anomalies))
            metadata = dict(first.metadata) if period.start == period.end else {}
            metadata.update({
                "name": period.name, "startDate": str(period.start), "endDate": str(period.end),
                "observedStart": first.metadata["date"], "observedEnd": last.metadata["date"],
                "dayCount": len(items), "expectedDays": expected, "coverageComplete": coverage,
                "isClosed": closed, "isComplete": coverage and closed and not anomalies,
                "sourceAnomalies": anomalies, "warnings": warnings,
            })
            result.append(Candle(
                day_start(period.start), end_ms,
                first.open, max(c.high for c in items), min(c.low for c in items),
                last.close, sum((c.volume for c in items), Decimal(0)), period.id, metadata,
            ))
        return result
