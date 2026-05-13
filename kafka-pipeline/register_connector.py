import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import psycopg


CONNECT_URL = "http://localhost:8083"
CONNECTOR_NAME = "orders-cdc"
CONFIG_PATH = Path(__file__).with_name("connector_config.json")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/dataengineeringproject",
)
TRACKED_TABLES = ("sales_order", "purchase_order", "production")


def wait_for_connect(timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{CONNECT_URL}/connectors", timeout=5) as response:
                if response.status == 200:
                    return
        except urllib.error.URLError:
            time.sleep(2)
    raise RuntimeError("Kafka Connect did not become ready in time.")


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_replica_identity() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        with connection.cursor() as cursor:
            for table_name in TRACKED_TABLES:
                cursor.execute(f"ALTER TABLE public.{table_name} REPLICA IDENTITY FULL")


def upsert_connector(config: dict) -> dict:
    payload = json.dumps(config["config"]).encode("utf-8")
    request = urllib.request.Request(
        f"{CONNECT_URL}/connectors/{CONNECTOR_NAME}/config",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    ensure_replica_identity()
    wait_for_connect()
    config = load_config()
    connector_info = upsert_connector(config)
    print(f"Connector '{connector_info['name']}' is ready.")
    print(f"Topics prefix: {config['config']['topic.prefix']}")
    print("Tracked tables: public.sales_order, public.purchase_order, public.production")
    print("Replica identity is set to FULL for tracked tables.")


if __name__ == "__main__":
    main()