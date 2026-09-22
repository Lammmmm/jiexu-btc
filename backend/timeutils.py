from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
DAY_MS = 86_400_000

def day_start(day: date) -> int:
    return int(datetime.combine(day, time.min, SHANGHAI).timestamp() * 1000)

def local_date(timestamp: int) -> date:
    return datetime.fromtimestamp(timestamp / 1000, SHANGHAI).date()

def dates_between(start: date, end: date):
    while start <= end:
        yield start
        start += timedelta(days=1)
