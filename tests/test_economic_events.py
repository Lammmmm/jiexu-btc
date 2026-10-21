import json
from datetime import date, datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import ROOT, Settings
from backend.economic.bls import BlsClient, ET, FEED, combine, event, parse_archive, parse_schedule
from backend.economic.service import EconomicCalendar, validate_snapshot


def feed(events):
    blocks = "\n".join(
        f"BEGIN:VEVENT\nUID:{i}\nDTSTART;TZID=America/New_York:{stamp}\nSUMMARY:{title}\n{extra}END:VEVENT"
        for i, (stamp, title, extra) in enumerate(events)
    )
    return "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Bureau of Labor Statistics//EN\n" + blocks + "\nEND:VCALENDAR"


def payload(events):
    return {"schemaVersion": 1, "timezone": "Asia/Shanghai",
            "capturedAt": "2026-10-14T01:00:00+00:00", "events": events}


def test_archive_uses_publication_filename_and_handles_dst():
    text = """
    <a href="/news.release/archives/cpi_01132026.htm">December 2025 CPI</a>
    <a href="https://www.bls.gov/news.release/archives/cpi_07142026.htm">June 2026 CPI</a>
    <a href="/news.release/archives/cpi_07142026.htm">duplicate</a>
    October 2025 CPI - Not published
    <a href="/news.release/archives/empsit_07022026.htm">other report</a>
    <a href="/news.release/archives/cpi_01152016.htm">too early</a>
    """
    rows = parse_archive(text, "cpi")
    assert [row["date"] for row in rows] == ["2026-01-13", "2026-07-14"]
    assert rows[0]["releaseAtShanghai"] == "2026-01-13T21:30:00+08:00"
    assert rows[1]["releaseAtShanghai"] == "2026-07-14T20:30:00+08:00"
    assert all(row["status"] == "released" for row in rows)
    assert "01132026" in rows[0]["sourceUrl"]


def test_icalendar_filters_us_reports_and_cancellations():
    text = feed([
        ("20260113T083000", "Consumer Price Index", ""),
        ("20260702T083000", "Employment Situation", ""),
        ("20260714T083000", "Consumer Price Index", "STATUS:CANCELLED\n"),
        ("20260714T083000", "Producer Price Index", ""),
        ("20260714T083000", "Consumer Price Index - Regional", ""),
    ])
    rows = parse_schedule("Title:\nURL Source: " + FEED + "\nMarkdown Content:\n" + text)
    assert [(row["kind"], row["date"]) for row in rows] == [("cpi", "2026-01-13"), ("nfp", "2026-07-02")]
    assert rows[0]["releaseAt"] == "2026-01-13T13:30:00+00:00"
    assert rows[1]["releaseAt"] == "2026-07-02T12:30:00+00:00"


def test_passed_or_delayed_schedule_is_not_proof_of_publication():
    published = parse_archive("/news.release/archives/empsit_11202025.htm", "nfp")
    scheduled = parse_schedule(feed([
        ("20251003T083000", "Employment Situation", ""),
        ("20251107T083000", "Employment Situation", ""),
        ("20261106T083000", "Employment Situation", ""),
    ]))
    rows = combine(published, scheduled, today=date(2026, 10, 14))
    assert [(row["date"], row["status"]) for row in rows] == [
        ("2025-11-20", "released"), ("2026-11-06", "scheduled")]


def test_publication_overrides_schedule_and_date_maps_to_utc8():
    publication = event("cpi", datetime(2026, 10, 14, 8, 30, tzinfo=ET), "released", FEED)
    scheduled = {**publication, "status": "scheduled"}
    assert combine([publication], [scheduled], today=date(2026, 10, 14))[0]["status"] == "released"
    utc = event("cpi", datetime(2026, 10, 14, 22, tzinfo=timezone.utc), "scheduled", FEED)
    assert utc["date"] == "2026-10-15"


def test_http_fallback_checks_original_source():
    def handler(request):
        if request.url.host == "www.bls.gov":
            return httpx.Response(403)
        return httpx.Response(200, text="URL Source: https://example.com/\nBEGIN:VCALENDAR")
    client = BlsClient(httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError, match="does not match"):
        client.read(FEED)
    client.close()


def test_bad_source_or_time_cache_rejected():
    item = event("cpi", datetime(2026, 10, 14, 8, 30, tzinfo=ET), "released", FEED)
    with pytest.raises(ValueError, match="source"):
        validate_snapshot(payload([{**item, "sourceUrl": "https://example.com/"}]))
    with pytest.raises(ValueError, match="mismatch"):
        validate_snapshot(payload([{**item, "date": "2026-10-13"}]))


def test_offline_cache_survives_failure_and_clears_expired_plans(tmp_path):
    release = event("nfp", datetime(2026, 10, 2, 8, 30, tzinfo=ET), "released", FEED)
    plan = event("cpi", datetime(2026, 10, 14, 8, 30, tzinfo=ET), "scheduled", FEED)
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps(payload([release, plan])))
    class Failing:
        def fetch(self): raise RuntimeError("offline")
        def close(self): pass
    service = EconomicCalendar(seed, tmp_path / "cache.json", client_factory=Failing)
    before = service.snapshot(today=date(2026, 10, 14))["events"]
    assert not service.refresh()
    assert service.snapshot(today=date(2026, 10, 14))["events"] == before
    assert service.snapshot(today=date(2026, 10, 15))["events"] == [release]
    assert service.error == "offline" and not service.busy
    assert not (tmp_path / "cache.json").exists()


def test_successful_refresh_replaces_future_schedule_and_keeps_history(tmp_path):
    old = event("nfp", datetime(2026, 10, 2, 8, 30, tzinfo=ET), "released", FEED)
    cancelled = event("nfp", datetime(2026, 11, 6, 8, 30, tzinfo=ET), "scheduled", FEED)
    delayed = event("nfp", datetime(2026, 11, 10, 8, 30, tzinfo=ET), "scheduled", FEED)
    seed = tmp_path / "seed.json"; seed.write_text(json.dumps(payload([old, cancelled])))
    class Fresh:
        def fetch(self): return {**payload([delayed]), "capturedAt": "2026-10-14T02:00:00+00:00"}
        def close(self): pass
    cache = tmp_path / "cache.json"
    service = EconomicCalendar(seed, cache, client_factory=Fresh)
    assert service.refresh()
    assert service.snapshot(today=date(2026, 10, 14))["events"] == [old, delayed]
    assert EconomicCalendar(seed, cache).snapshot(today=date(2026, 10, 14))["events"] == [old, delayed]


def test_bundled_data_and_api_coverage(tmp_path):
    with TestClient(create_app(Settings(market_db=tmp_path / "market.db", auto_sync=False))) as client:
        response = client.get("/api/economic-events")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) >= 230
        assert data["timezone"] == "Asia/Shanghai"
        events = {(row["kind"], row["date"]): row for row in data["events"]}
        assert events[("cpi", "2022-09-13")]["status"] == "released"
        assert events[("nfp", "2026-07-02")]["status"] == "released"  # Thursday, not first Friday.
        assert ("nfp", "2026-07-03") not in events
        assert events[("nfp", "2026-02-11")]["status"] == "released"  # Delayed release.
        assert ("nfp", "2026-02-06") not in events
        assert events[("cpi", "2025-10-24")]["status"] == "released"
        assert events[("nfp", "2025-11-20")]["status"] == "released"
        assert ("cpi", "2025-10-15") not in events
        assert ("nfp", "2025-10-03") not in events
        assert client.get("/api/status").json()["economicCalendarVersion"] == data["version"]


def test_cache_freshness_compares_instants_across_timezone_offsets(tmp_path):
    old = event("nfp", datetime(2026, 10, 2, 8, 30, tzinfo=ET), "released", FEED)
    new = event("cpi", datetime(2026, 10, 14, 8, 30, tzinfo=ET), "scheduled", FEED)
    seed = tmp_path / "seed.json"; cache = tmp_path / "cache.json"
    seed.write_text(json.dumps({**payload([old]), "capturedAt": "2026-10-14T10:00:00+08:00"}))
    cache.write_text(json.dumps({**payload([old, new]), "capturedAt": "2026-10-14T03:00:00+00:00"}))
    assert EconomicCalendar(seed, cache).snapshot(today=date(2026, 10, 14))["events"] == [old, new]
    cache.write_text("[]")
    assert EconomicCalendar(seed, cache).snapshot(today=date(2026, 10, 14))["events"] == [old]
