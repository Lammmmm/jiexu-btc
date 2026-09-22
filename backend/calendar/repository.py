import sqlite3
from contextlib import closing
from pathlib import Path

class CalendarRepository:
    def __init__(self, path):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise RuntimeError("Calendar database missing. Run: python -m scripts.generate_calendar")
        with closing(self.connect()) as conn:
            self.metadata = dict(conn.execute("SELECT key,value FROM calendar_metadata").fetchall())
        if self.metadata.get("schema_version") != "2":
            raise RuntimeError("Unsupported calendar schema")

    def connect(self):
        conn = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def range(self, start, end):
        with closing(self.connect()) as conn:
            rows = conn.execute("""
                SELECT d.*, m.start_date AS month_start, m.end_date AS month_end,
                       y.start_date AS year_start, y.end_date AS year_end
                FROM calendar_days d
                JOIN calendar_periods m ON d.solar_month_id=m.period_id AND m.kind='month'
                JOIN calendar_periods y ON CAST(d.solar_year_id AS TEXT)=y.period_id AND y.kind='year'
                WHERE d.date BETWEEN ? AND ? ORDER BY d.date
            """, (str(start), str(end))).fetchall()
        return {r["date"]: dict(r) for r in rows}

    def get(self, day):
        result = self.range(day, day)
        if str(day) not in result:
            raise ValueError(f"Date outside calendar coverage: {day}")
        return result[str(day)]
