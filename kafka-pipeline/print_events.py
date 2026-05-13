import argparse
import json
from datetime import datetime, timezone

from kafka import KafkaConsumer


TOPIC_TO_ENTITY = {
    "opsdb.public.sales_order": "sales_order",
    "opsdb.public.purchase_order": "purchase_order",
    "opsdb.public.production": "production",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print Debezium order events from Kafka.")
    parser.add_argument("--bootstrap-servers", default="localhost:19092")
    parser.add_argument(
        "--topics",
        nargs="+",
        default=list(TOPIC_TO_ENTITY.keys()),
        help="Kafka topics to consume.",
    )
    return parser.parse_args()


def format_timestamp(ts_ms: int | None) -> str:
    if not ts_ms:
        return "unknown-time"
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return dt.isoformat()


def decode_status(entity: str, payload: dict | None) -> str | None:
    if not payload:
        return None
    if entity == "sales_order":
        return payload.get("shipping_status")
    return payload.get("status")


def summarize_event(topic: str, message_value: dict) -> str:
    if message_value is None:
        return "[unknown-time] tombstone"

    envelope = message_value.get("payload", message_value)
    entity = TOPIC_TO_ENTITY.get(topic, topic)
    operation = envelope.get("op")
    before = envelope.get("before")
    after = envelope.get("after")
    event_time = format_timestamp(envelope.get("ts_ms"))
    current = after or before or {}
    entity_id = current.get("id", "?")

    if operation in {"c", "r"}:
        status = decode_status(entity, after)
        action = "snapshot" if operation == "r" else "created"
        return f"[{event_time}] {entity}#{entity_id} {action} status={status}"

    if operation == "u":
        previous_status = decode_status(entity, before)
        current_status = decode_status(entity, after)
        if previous_status != current_status:
            return (
                f"[{event_time}] {entity}#{entity_id} status changed "
                f"{previous_status} -> {current_status}"
            )
        return f"[{event_time}] {entity}#{entity_id} updated"

    if operation == "d":
        status = decode_status(entity, before)
        return f"[{event_time}] {entity}#{entity_id} deleted previous_status={status}"

    return f"[{event_time}] {entity}#{entity_id} op={operation}"


def main() -> None:
    args = parse_args()
    consumer = KafkaConsumer(
        *args.topics,
        bootstrap_servers=args.bootstrap_servers,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="orders-cdc-printer",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")) if value else None,
        key_deserializer=lambda value: value.decode("utf-8") if value else None,
    )

    print("Listening for Kafka CDC events...")
    print(f"Bootstrap servers: {args.bootstrap_servers}")
    print(f"Topics: {', '.join(args.topics)}")

    for message in consumer:
        print(summarize_event(message.topic, message.value), flush=True)


if __name__ == "__main__":
    main()