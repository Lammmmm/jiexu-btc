"""Settings are independent of UI and calendar algorithms."""
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    market_db: Path = ROOT / "data/market.db"
    calendar_db: Path = ROOT / "data/calendar.db"
    binance_url: str = "https://data-api.binance.vision"
    custom_week_anchor: date | None = None
    debug_mode: bool = False
    auto_sync: bool = True
    sync_seconds: int = 60

    @classmethod
    def from_env(cls):
        anchor = os.getenv("CUSTOM_WEEK_ANCHOR", "").strip()
        return cls(
            market_db=Path(os.getenv("MARKET_DB", str(ROOT / "data/market.db"))),
            calendar_db=Path(os.getenv("CALENDAR_DB", str(ROOT / "data/calendar.db"))),
            binance_url=os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision").rstrip("/"),
            custom_week_anchor=date.fromisoformat(anchor) if anchor else None,
            debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
            auto_sync=os.getenv("AUTO_SYNC", "true").lower() == "true",
            sync_seconds=max(30, int(os.getenv("SYNC_SECONDS", "60"))),
        )
