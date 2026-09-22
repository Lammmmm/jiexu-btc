from dataclasses import dataclass, field
from decimal import Decimal

@dataclass(frozen=True)
class Candle:
    open_time: int
    close_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    period_id: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        # Preserve exact analytical values; only convert to float at chart boundary.
        return {
            "openTime": self.open_time, "closeTime": self.close_time,
            **{k: str(getattr(self, k)) for k in ("open", "high", "low", "close", "volume")},
            "periodId": self.period_id, "metadata": self.metadata,
        }
