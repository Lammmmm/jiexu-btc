import logging
from functools import lru_cache
from datetime import timedelta
from backend.timeutils import DAY_MS, day_start, local_date

logger = logging.getLogger(__name__)

@lru_cache(maxsize=2048)
def warn_early_close(open_time, close_time):
    # Preserve source anomalies and UI flags; only deduplicate repeated log lines.
    logger.warning("Early source close time: %s (%s); preserved verbatim", local_date(open_time), close_time)


class DataIntegrityError(ValueError):
    pass

def validate_daily(candles, *, require_contiguous=True):
    """Fail visibly before persistence/aggregation; never fabricate missing prices."""
    seen = set()
    previous = None
    for c in candles:
        d = local_date(c.open_time)
        error = None
        values = (c.open, c.high, c.low, c.close, c.volume)
        if c.open_time in seen:
            error = f"Duplicate daily candle: {d}"
        elif c.open_time != day_start(d) or not c.open_time <= c.close_time <= c.open_time + DAY_MS - 1:
            error = f"Invalid UTC+8 day boundary: {d}"
        elif not all(v.is_finite() for v in values):
            error = f"Non-finite OHLC/volume: {d}"
        elif min(c.open, c.high, c.low, c.close) <= 0 or c.volume < 0 or not (
            c.low <= min(c.open, c.close) <= max(c.open, c.close) <= c.high
        ):
            error = f"Invalid OHLC/volume: {d}"
        elif previous is not None and c.open_time < previous.open_time:
            error = f"Out-of-order daily candle: {d}"
        elif require_contiguous and previous and c.open_time != previous.open_time + DAY_MS:
            error = f"Missing daily candle: {local_date(previous.open_time) + timedelta(days=1)}"
        if error:
            logger.error(error)
            raise DataIntegrityError(error)
        if c.close_time != c.open_time + DAY_MS - 1:
            warn_early_close(c.open_time, c.close_time)
        seen.add(c.open_time)
        previous = c
