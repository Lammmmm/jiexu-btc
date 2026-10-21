"""Local publication calendar cache; chart loading never waits for the network."""
import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .bls import BlsClient, SHANGHAI

logger = logging.getLogger(__name__)


def validate_snapshot(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid economic calendar cache")
    if payload.get("schemaVersion") != 1 or payload.get("timezone") != "Asia/Shanghai":
        raise ValueError("Unsupported economic calendar cache")
    events = payload.get("events", [])
    if not isinstance(events, list) or not events or not all(isinstance(row, dict) for row in events):
        raise ValueError("Invalid economic event list")
    if len({row["id"] for row in events}) != len(events):
        raise ValueError("Empty or duplicate economic calendar cache")
    if datetime.fromisoformat(payload["capturedAt"]).tzinfo is None:
        raise ValueError("Economic cache timestamp must include a timezone")
    for row in events:
        dt = datetime.fromisoformat(row["releaseAt"])
        if dt.tzinfo is None or str(dt.astimezone(SHANGHAI).date()) != row["date"] or row["id"] != f'{row["kind"]}:{row["date"]}':
            raise ValueError("Economic release date/time mismatch")
        if row["kind"] not in ("cpi", "nfp") or row["status"] not in ("released", "scheduled"):
            raise ValueError("Invalid economic event")
        if not row["sourceUrl"].startswith("https://www.bls.gov/"):
            raise ValueError("Unexpected economic event source")
    return payload


class EconomicCalendar:
    def __init__(self, seed_path, cache_path=None, client_factory=BlsClient):
        self.seed_path = Path(seed_path)
        self.cache_path = Path(cache_path) if cache_path else None
        self.client_factory = client_factory
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.error = None
        self.busy = False
        self.next_refresh = 0
        self.payload = validate_snapshot(json.loads(self.seed_path.read_text(encoding="utf-8")))
        if self.cache_path and self.cache_path.exists():
            try:
                cached = validate_snapshot(json.loads(self.cache_path.read_text(encoding="utf-8")))
                if datetime.fromisoformat(cached["capturedAt"]) > datetime.fromisoformat(self.payload["capturedAt"]):
                    self.payload = cached
            except (OSError, ValueError, KeyError):
                logger.warning("Economic calendar cache invalid; using bundled BLS dates")

    def snapshot(self, *, today=None):
        today = today or datetime.now(timezone.utc).astimezone(SHANGHAI).date()
        with self.lock:
            data = {**self.payload, "events": [row for row in self.payload["events"]
                    if row["status"] == "released" or row["date"] >= str(today)]}
            version = hashlib.sha256(json.dumps(data["events"], sort_keys=True).encode()).hexdigest()[:16]
            return {**data, "version": version, "error": self.error, "syncing": self.busy}

    def refresh(self):
        with self.lock:
            if self.busy:
                return False
            self.busy = True
        client = None
        try:
            client = self.client_factory()
            fresh = validate_snapshot(client.fetch())
            with self.lock:
                # Confirmed publications remain available even if the upstream
                # archive later shortens its visible history.
                confirmed = {row["id"]: row for row in self.payload["events"] if row["status"] == "released"}
                confirmed.update({row["id"]: row for row in fresh["events"]})
                fresh["events"] = sorted(confirmed.values(), key=lambda row: (row["date"], row["kind"]))
                if self.cache_path:
                    self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                    pending = self.cache_path.with_suffix(".tmp")
                    pending.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    pending.replace(self.cache_path)
                self.payload = fresh
                self.error = None
                self.next_refresh = time.time() + 6 * 3600
            return True
        except Exception as exc:
            with self.lock:
                self.error = str(exc)
                self.next_refresh = time.time() + 30 * 60
            logger.warning("Economic calendar refresh failed; retaining verified dates: %s", exc)
            return False
        finally:
            if client is not None:
                client.close()
            with self.lock:
                self.busy = False

    def loop(self):
        while not self.stop.is_set():
            self.refresh()
            self.stop.wait(max(1, self.next_refresh - time.time()))
