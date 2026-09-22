import time
from decimal import Decimal, InvalidOperation
import httpx
from backend.models import Candle
from backend.timeutils import DAY_MS, local_date
from .validation import DataIntegrityError, validate_daily

class BinanceError(RuntimeError):
    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after

class BinanceClient:
    def __init__(self, base_url="https://data-api.binance.vision", client=None, sleep=time.sleep):
        self.http = client or httpx.Client(base_url=base_url, timeout=20)
        self.sleep = sleep

    def close(self):
        self.http.close()

    def _get(self, path, params=None):
        for attempt in range(3):
            try:
                response = self.http.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise BinanceError(f"Binance connection failed: {exc}") from exc
                self.sleep(2 ** attempt)
                continue
            if response.status_code in (418, 429):
                retry = response.headers.get("Retry-After", "unknown")
                raise BinanceError(f"Binance rate limited ({response.status_code}); Retry-After={retry}",
                                   retry_after=int(retry) if retry.isdigit() else 120)
            if response.status_code >= 500 and attempt < 2:
                self.sleep(2 ** attempt)
                continue
            if response.is_error:
                raise BinanceError(f"Binance HTTP {response.status_code}: {response.text[:300]}")
            try:
                return response.json()
            except ValueError as exc:
                raise BinanceError("Binance returned invalid JSON") from exc

    def server_time(self):
        return int(self._get("/api/v3/time")["serverTime"])

    def daily(self, start_ms, end_ms):
        """Official Spot klines; timeZone=8, timestamps always UTC milliseconds."""
        cursor = start_ms
        while cursor <= end_ms:
            rows = self._get("/api/v3/klines", {
                "symbol": "BTCUSDT", "interval": "1d", "timeZone": "8",
                "startTime": cursor, "endTime": end_ms, "limit": 1000,
            })
            if not isinstance(rows, list):
                raise BinanceError(f"Unexpected kline response: {rows}")
            if not rows:
                break
            try:
                candles = [Candle(int(r[0]), int(r[6]), *(Decimal(str(r[i])) for i in range(1, 6)),
                                  str(local_date(int(r[0])))) for r in rows]
            except (ValueError, TypeError, IndexError, InvalidOperation) as exc:
                raise DataIntegrityError("Malformed Binance candle") from exc
            validate_daily(candles)
            if candles[0].open_time < cursor or candles[-1].open_time > end_ms:
                raise DataIntegrityError("Binance returned candles outside requested window")
            yield candles
            cursor = candles[-1].open_time + DAY_MS
            if len(rows) < 1000:
                break
