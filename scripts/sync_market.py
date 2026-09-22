import json
import logging
from backend.config import Settings
from backend.market.binance_client import BinanceClient
from backend.market.repository import MarketRepository
from backend.market.updater import MarketDataService

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    client = BinanceClient(settings.binance_url)
    try:
        print(json.dumps(MarketDataService(client, MarketRepository(settings.market_db)).sync(), indent=2))
    finally:
        client.close()

if __name__ == "__main__":
    main()
