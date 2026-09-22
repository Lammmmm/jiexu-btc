from datetime import date
from decimal import Decimal
import pytest
from backend.config import ROOT
from backend.calendar.repository import CalendarRepository
from backend.calendar.service import CalendarService
from backend.models import Candle
from backend.timeutils import DAY_MS, day_start, dates_between

@pytest.fixture(scope="session")
def calendar():
    return CalendarRepository(ROOT / "data/calendar.db")

@pytest.fixture
def daily_factory(calendar):
    def make(start, end):
        rows = []
        for i, d in enumerate(dates_between(date.fromisoformat(start), date.fromisoformat(end))):
            base = Decimal("100.00000001") + i
            rows.append(Candle(day_start(d), day_start(d) + DAY_MS - 1, base, base + 5, base - 2,
                               base + 3, Decimal("0.00000003") + i, str(d)))
        return CalendarService(calendar).join(rows)
    return make
