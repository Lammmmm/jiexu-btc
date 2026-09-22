import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from backend.models import Candle
from backend.timeutils import local_date
from .validation import validate_daily

class MarketRepository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS daily_candles (
                    timestamp INTEGER PRIMARY KEY, close_time INTEGER NOT NULL,
                    date TEXT NOT NULL UNIQUE, open TEXT NOT NULL, high TEXT NOT NULL,
                    low TEXT NOT NULL, close TEXT NOT NULL, volume TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS market_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def upsert(self, candles):
        validate_daily(candles)
        with self.connection() as conn:
            conn.executemany("""INSERT INTO daily_candles VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(timestamp) DO UPDATE SET close_time=excluded.close_time,
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume""", [
                (c.open_time, c.close_time, str(local_date(c.open_time)),
                 *[str(getattr(c, k)) for k in ("open", "high", "low", "close", "volume")])
                for c in candles])

    def all(self):
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM daily_candles ORDER BY timestamp").fetchall()
        return [Candle(r["timestamp"], r["close_time"],
                       *(Decimal(r[k]) for k in ("open", "high", "low", "close", "volume")), r["date"])
                for r in rows]

    def set_meta(self, key, value):
        with self.connection() as conn:
            conn.execute("INSERT OR REPLACE INTO market_metadata VALUES (?,?)", (key, str(value)))

    def get_meta(self, key):
        with self.connection() as conn:
            row = conn.execute("SELECT value FROM market_metadata WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
