"""One-time offline build. Production backend NEVER imports lunar_python."""
import argparse
import hashlib
import json
import sqlite3
from bisect import bisect_right
from datetime import date, timedelta
from importlib.metadata import distribution, version
from pathlib import Path

from lunar_python import Solar, Lunar
from lunar_python.util import LunarUtil
from backend.config import ROOT
from backend.timeutils import dates_between

SOURCE_VERSION = "1.4.8"
MONTH_NAMES = ("立春", "惊蛰", "清明", "立夏", "芒种", "小暑", "立秋", "白露", "寒露", "立冬", "大雪", "小寒")
MONTH_SLUGS = ("lichun", "jingzhe", "qingming", "lixia", "mangzhong", "xiaoshu", "liqiu", "bailu", "hanlu", "lidong", "daxue", "xiaohan")
ALIASES = dict(zip(("DA_XUE", "DONG_ZHI", "XIAO_HAN", "DA_HAN", "LI_CHUN", "YU_SHUI", "JING_ZHE"),
                   ("大雪", "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰")))

def generate(path, start=date(1900, 1, 1), end=date(2100, 12, 31)):
    if version("lunar_python") != SOURCE_VERSION:
        raise RuntimeError(f"Requires lunar_python=={SOURCE_VERSION}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".building.db")
    if tmp.exists():
        tmp.unlink()
    # Adjacent years supply true boundaries for January 1900 and December 2100.
    terms = {}
    for year in range(start.year - 1, end.year + 2):
        table = Solar.fromYmd(year, 7, 1).getLunar().getJieQiTable()
        for key, solar in table.items():
            name = ALIASES.get(key, key)
            terms[solar.toYmd()] = {
                "name": name, "exact": solar.toYmdHms().replace(" ", "T") + "+08:00",
                "index": Lunar.JIE_QI.index(name),
            }
    month_starts = sorted(d for d, t in terms.items() if t["name"] in MONTH_NAMES)
    year_starts = sorted(d for d, t in terms.items() if t["name"] == "立春")
    periods = []
    month_by_start = {}
    for i, begin in enumerate(month_starts[:-1]):
        name = terms[begin]["name"]
        index = MONTH_NAMES.index(name)
        solar_year = int(begin[:4]) - (1 if name == "小寒" else 0)
        pid = f"{solar_year}-{MONTH_SLUGS[index]}"
        finish = str(date.fromisoformat(month_starts[i + 1]) - timedelta(days=1))
        month_by_start[begin] = (pid, name, index + 1, solar_year)
        periods.append((pid, "month", name + "月", begin, finish))
    for i, begin in enumerate(year_starts[:-1]):
        finish = str(date.fromisoformat(year_starts[i + 1]) - timedelta(days=1))
        periods.append((begin[:4], "year", begin[:4] + " 立春年", begin, finish))

    conn = sqlite3.connect(tmp)
    conn.executescript("""
        CREATE TABLE calendar_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE calendar_periods (
            period_id TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL,
            start_date TEXT NOT NULL, end_date TEXT NOT NULL, PRIMARY KEY (period_id,kind));
        CREATE TABLE calendar_days (
            date TEXT PRIMARY KEY, ganzhi_day TEXT NOT NULL, heavenly_stem TEXT NOT NULL,
            earthly_branch TEXT NOT NULL, ganzhi_index INTEGER NOT NULL,
            solar_term TEXT, solar_term_index INTEGER, solar_term_date TEXT, solar_term_exact_time TEXT,
            solar_month TEXT NOT NULL, solar_month_id TEXT NOT NULL, month_index INTEGER NOT NULL,
            solar_year_id INTEGER NOT NULL, ganzhi_month TEXT NOT NULL, ganzhi_year TEXT NOT NULL);
        CREATE INDEX calendar_month ON calendar_days(solar_month_id);
        CREATE INDEX calendar_year ON calendar_days(solar_year_id);
    """)
    meta = {
        "schema_version": "2", "source": "https://github.com/6tail/lunar-python",
        "source_version": SOURCE_VERSION, "license": "MIT",
        "start_date": str(start), "end_date": str(end), "timezone": "Asia/Shanghai",
        "term_time_convention": "library Beijing standard time, fixed +08:00; not historical DST",
        "boundary_rule": "solar term Gregorian date at 00:00 +08:00",
        "ganzhi_rule": "getDayInGanZhi at Gregorian midnight; no 23:00 rollover",
        "ganzhi_month_rule": "getMonthInGanZhi; switch on Jie date at midnight",
        "ganzhi_year_rule": "getYearInGanZhiByLiChun; switch on Lichun date at midnight",
    }
    conn.executemany("INSERT INTO calendar_metadata VALUES (?,?)", meta.items())
    conn.executemany("INSERT INTO calendar_periods VALUES (?,?,?,?,?)", periods)
    rows = []
    for d in dates_between(start, end):
        ds = str(d)
        lunar = Solar.fromYmd(d.year, d.month, d.day).getLunar()
        gz = lunar.getDayInGanZhi()
        term = terms.get(ds, {})
        begin = month_starts[bisect_right(month_starts, ds) - 1]
        pid, name, index, solar_year = month_by_start[begin]
        rows.append((ds, gz, lunar.getDayGan(), lunar.getDayZhi(), LunarUtil.getJiaZiIndex(gz),
                     term.get("name"), term.get("index"), ds if term else None, term.get("exact"),
                     name + "月", pid, index, solar_year, lunar.getMonthInGanZhi(), lunar.getYearInGanZhiByLiChun()))
        if len(rows) >= 1000:
            conn.executemany("INSERT INTO calendar_days VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            rows.clear()
        if d.month == 12 and d.day == 31 and d.year % 10 == 0:
            print(f"Generated through {d}", flush=True)
    conn.executemany("INSERT INTO calendar_days VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM calendar_days").fetchone()[0]
    assert count == (end - start).days + 1
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()
    tmp.replace(path)
    source_dir = path.parent / "calendar_source"
    source_dir.mkdir(exist_ok=True)
    dist = distribution("lunar_python")
    license_file = next(p for p in dist.files if str(p).endswith("licenses/LICENSE"))
    (source_dir / "LICENSE.lunar-python").write_text(dist.locate_file(license_file).read_text(encoding="utf-8"), encoding="utf-8")
    meta.update({"row_count": count, "database_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (source_dir / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2), flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data/calendar.db")
    args = parser.parse_args()
    generate(args.output)
