from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol
from backend.models import Candle

@dataclass(frozen=True)
class Period:
    id: str
    name: str
    start: date
    end: date

class PeriodResolver(Protocol):
    def resolve(self, candle: Candle) -> Period: ...

class DailyPeriod:
    def resolve(self, candle):
        day = date.fromisoformat(candle.metadata["date"])
        return Period(str(day), "UTC+8 日线", day, day)

class CustomWeekPeriod:
    def __init__(self, anchor: date):
        self.anchor = anchor

    def for_date(self, day):
        # Python // is floor division, including dates before the anchor.
        index = (day - self.anchor).days // 7
        start = self.anchor + timedelta(days=index * 7)
        return Period(f"week:{self.anchor}:{index}", f"自定义七日 · {index:+d}", start, start + timedelta(days=6))

    def resolve(self, candle):
        return self.for_date(date.fromisoformat(candle.metadata["date"]))

class SolarMonthPeriod:
    def resolve(self, candle):
        m = candle.metadata
        return Period(m["solar_month_id"], m["solar_month"],
                      date.fromisoformat(m["month_start"]), date.fromisoformat(m["month_end"]))

class SolarYearPeriod:
    def resolve(self, candle):
        m = candle.metadata
        return Period(str(m["solar_year_id"]), f'{m["solar_year_id"]} 立春年',
                      date.fromisoformat(m["year_start"]), date.fromisoformat(m["year_end"]))

def resolver_for(kind, anchor=None):
    if kind == "week":
        if anchor is None:
            raise ValueError("CUSTOM_WEEK_ANCHOR 未配置，请先输入周线起算锚点。")
        return CustomWeekPeriod(anchor)
    types = {"day": DailyPeriod, "month": SolarMonthPeriod, "year": SolarYearPeriod}
    if kind not in types:
        raise ValueError(f"Unknown period: {kind}")
    return types[kind]()
