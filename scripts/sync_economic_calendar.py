"""Refresh the local official CPI / nonfarm publication calendar."""
import argparse
from backend.config import ROOT
from backend.economic.bls import BlsClient
from backend.economic.service import EconomicCalendar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true", help="Refresh the shipped verified snapshot")
    args = parser.parse_args()
    path = ROOT / "data/us-economic-events.json"
    if args.seed:
        client = BlsClient()
        try:
            payload = client.fetch()
        finally:
            client.close()
        import json
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {len(payload['events'])} verified/scheduled BLS events to {path}")
    else:
        calendar = EconomicCalendar(path, ROOT / "data/us-economic-events.cache.json")
        if not calendar.refresh():
            raise SystemExit(calendar.error)
        print(f"Updated {len(calendar.snapshot()['events'])} BLS events")


if __name__ == "__main__":
    main()
