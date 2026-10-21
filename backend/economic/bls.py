"""Verified BLS publication dates and official ICS schedules; no date guessing."""
import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import httpx
from icalendar import Calendar

ET = ZoneInfo("America/New_York")
SHANGHAI = ZoneInfo("Asia/Shanghai")
ARCHIVES = {
    "cpi": "https://www.bls.gov/bls/news-release/cpi.htm",
    "nfp": "https://www.bls.gov/bls/news-release/empsit.htm",
}
FEED = "https://www.bls.gov/schedule/news_release/bls.ics"
LABELS = {"cpi": "CPI", "nfp": "非农"}
SUMMARIES = {"Consumer Price Index": "cpi", "Employment Situation": "nfp"}


def event(kind, dt, status, source):
    if dt.tzinfo is None:
        raise ValueError("BLS release time must include a timezone")
    return {
        "id": f"{kind}:{dt.astimezone(SHANGHAI).date()}",
        "kind": kind, "label": LABELS[kind],
        "date": str(dt.astimezone(SHANGHAI).date()),
        "releaseAt": dt.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "releaseAtEt": dt.astimezone(ET).isoformat(timespec="seconds"),
        "releaseAtShanghai": dt.astimezone(SHANGHAI).isoformat(timespec="seconds"),
        "status": status, "sourceUrl": source,
    }


def parse_archive(text, kind, *, start_year=2017):
    """Archive filenames contain publication dates, not reference months."""
    code = "cpi" if kind == "cpi" else "empsit"
    expression = r'(?:https://www\.bls\.gov)?/news\.release/archives/' + code + r'_(\d{8})\.htm'
    releases = {}
    for match in re.finditer(expression, text):
        ds = datetime.strptime(match[1], "%m%d%Y").date()
        if ds.year < start_year:
            continue
        # Both BLS monthly national releases use 08:30 Eastern. ZoneInfo
        # converts summer/winter releases to 20:30/21:30 in Shanghai.
        dt = datetime.combine(ds, time(8, 30), ET)
        source = f"https://www.bls.gov/news.release/archives/{code}_{match[1]}.htm"
        releases[str(ds)] = event(kind, dt, "released", source)
    if not releases:
        raise ValueError(f"No {kind} publication dates found in BLS archive")
    return sorted(releases.values(), key=lambda row: row["releaseAt"])


def parse_schedule(text):
    # A public text-reader fallback wraps the original ICS with a small header.
    begin, end = text.find("BEGIN:VCALENDAR"), text.find("END:VCALENDAR")
    if begin < 0 or end < begin:
        raise ValueError("Invalid BLS iCalendar response")
    calendar = Calendar.from_ical(text[begin:end + len("END:VCALENDAR")])
    if "Bureau of Labor Statistics" not in str(calendar.get("PRODID", "")):
        raise ValueError("Unexpected economic calendar publisher")
    releases = {}
    for component in calendar.walk("VEVENT"):
        kind = SUMMARIES.get(str(component.get("SUMMARY", "")))
        if not kind or str(component.get("STATUS", "")).upper() == "CANCELLED":
            continue
        dt = component.decoded("DTSTART")
        if not isinstance(dt, datetime):
            raise ValueError("BLS calendar event is missing a release time")
        item = event(kind, dt, "scheduled", FEED)
        releases[item["id"]] = item
    if not releases:
        raise ValueError("No CPI or Employment Situation events in BLS calendar")
    return sorted(releases.values(), key=lambda row: (row["date"], row["kind"]))


def combine(archives, scheduled, *, today):
    releases = {row["id"]: row for row in archives if row["date"] <= str(today)}
    # Passed schedules never prove publication: cancelled/delayed dates must
    # not leak back into the historical chart. Archives take precedence.
    for row in scheduled:
        if row["date"] >= str(today) and row["id"] not in releases:
            releases[row["id"]] = row
    return sorted(releases.values(), key=lambda row: (row["date"], row["kind"]))


class BlsClient:
    def __init__(self, client=None):
        self.client = client or httpx.Client(timeout=15, follow_redirects=True)
        self.transports = {}

    def read(self, url):
        try:
            response = self.client.get(url)
            response.raise_for_status()
            text = response.text
            transport = "direct"
        except httpx.HTTPError:
            # BLS blocks many machine clients with HTTP 403. This optional,
            # public, unauthenticated reader exposes that same official page.
            response = self.client.get("https://r.jina.ai/" + url)
            response.raise_for_status()
            text = response.text
            if f"URL Source: {url}" not in text:
                raise ValueError("Text-reader response does not match the BLS source")
            transport = "public-text-reader"
        self.transports[url] = transport
        return text

    def fetch(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        today = now.astimezone(SHANGHAI).date()
        archives = []
        for kind, url in ARCHIVES.items():
            rows = parse_archive(self.read(url), kind)
            counts = {}
            for row in rows:
                year = int(row["date"][:4])
                counts[year] = counts.get(year, 0) + 1
            for year in range(2017, today.year):
                if not 10 <= counts.get(year, 0) <= 14:
                    raise ValueError(f"Incomplete BLS {kind} archive for {year}")
            archives.extend(rows)
        scheduled = parse_schedule(self.read(FEED))
        return {
            "schemaVersion": 1, "publisher": "U.S. Bureau of Labor Statistics",
            "timezone": "Asia/Shanghai",
            "capturedAt": now.isoformat(timespec="seconds"),
            "sources": [*ARCHIVES.values(), FEED],
            "transports": dict(self.transports),
            "events": combine(archives, scheduled, today=today),
        }

    def close(self):
        self.client.close()
