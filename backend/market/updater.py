import logging
from datetime import date, timedelta
from backend.timeutils import DAY_MS, dates_between, day_start, local_date
from .validation import DataIntegrityError, validate_daily

logger = logging.getLogger(__name__)
# Discovery before the Spot exchange launch; actual first candle comes from API.
DISCOVERY_START = date(2017, 1, 1)

class MarketDataService:
    def __init__(self, client, repository):
        self.client = client
        self.repository = repository

    def _download(self, start, end):
        count = 0
        for page in self.client.daily(start, end):
            if self.repository.get_meta("first_available_date") is None:
                self.repository.set_meta("first_available_date", str(local_date(page[0].open_time)))
            self.repository.upsert(page)
            count += len(page)
            logger.info("Cached %s through %s (%s daily candles)", page[0].period_id, page[-1].period_id, len(page))
        return count

    def sync(self):
        now = self.client.server_time()
        today = local_date(now)
        candles = self.repository.all()
        validate_daily(candles, require_contiguous=False)
        count = 0
        if not candles:
            count += self._download(day_start(DISCOVERY_START), now)
        else:
            first = date.fromisoformat(self.repository.get_meta("first_available_date") or candles[0].period_id)
            present = {c.period_id for c in candles}
            missing = [d for d in dates_between(first, local_date(candles[-1].open_time)) if str(d) not in present]
            ranges = []
            for d in missing:
                if ranges and d == ranges[-1][1] + timedelta(days=1):
                    ranges[-1] = (ranges[-1][0], d)
                else:
                    ranges.append((d, d))
            for start, end in ranges:
                logger.warning("Missing daily candles: %s through %s; repairing", start, end)
                count += self._download(day_start(start), day_start(end) + DAY_MS - 1)
            # Refresh yesterday too: its previous cached snapshot may still be unclosed.
            refresh_start = max(day_start(first), candles[-1].open_time - DAY_MS)
            count += self._download(refresh_start, now)
        result = self.repository.all()
        validate_daily(result)
        if not result or result[-1].period_id != str(today):
            raise DataIntegrityError(f"Missing daily candle: {today}; sync incomplete")
        if result[0].period_id != self.repository.get_meta("first_available_date"):
            raise DataIntegrityError("Missing daily candle at cache start")
        self.repository.set_meta("last_sync_ms", now)
        return {"downloaded": count, "total": len(result), "firstDate": result[0].period_id,
                "lastDate": result[-1].period_id, "serverTime": now}
