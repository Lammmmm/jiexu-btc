from dataclasses import replace
from backend.timeutils import DAY_MS
from backend.market.validation import DataIntegrityError

class CalendarService:
    def __init__(self, repository):
        self.repository = repository

    def join(self, candles):
        if not candles:
            return []
        calendar = self.repository.range(candles[0].period_id, candles[-1].period_id)
        result = []
        for c in candles:
            if c.period_id not in calendar:
                raise DataIntegrityError(f"Missing calendar date: {c.period_id}")
            row = calendar[c.period_id]
            result.append(replace(c, metadata={
                **row, "sourceCloseTime": c.close_time,
                "sourceAnomaly": c.close_time != c.open_time + DAY_MS - 1,
            }))
        return result

    def get_ganzhi_day(self, day):
        return self.repository.get(day)["ganzhi_day"]

    def get_solar_month(self, day):
        return self.repository.get(day)["solar_month_id"]

    def get_solar_year(self, day):
        return self.repository.get(day)["solar_year_id"]

    def get_solar_term(self, day):
        return self.repository.get(day)["solar_term"]
