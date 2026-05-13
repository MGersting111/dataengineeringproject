# dataengineeringproject

Two simple but fully functional Flask applications were created from the concept model:

- `Shop-App`: customer-facing shop for browsing products, account creation, cart, checkout, and order history.
- `Company-App`: internal operations page for supplier orders, warehouse inventory, BOM, production planning, and sales-order fulfillment tracking.

Both apps use the same PostgreSQL database and share the `users` table.

## Realtime event pipeline with Kafka

There is now a Kafka-compatible CDC pipeline for orders and status changes:

- `postgres` stays the system of record.
- `redpanda` provides the Kafka broker API.
- `kafka-connect` runs Debezium and streams DB changes from PostgreSQL.
- Topics emitted by Debezium:
	- `opsdb.public.sales_order`
	- `opsdb.public.purchase_order`
	- `opsdb.public.production`

## Tech stack

- Flask
- Flask-SQLAlchemy
- Flask-Login
- PostgreSQL (Docker)
- Redpanda (Kafka-compatible broker)
- Debezium / Kafka Connect
- Tailwind CSS (CDN)

## 1) Start PostgreSQL in Docker

From the project root:

```bash
docker compose up -d
```

This now starts PostgreSQL, Redpanda, and Kafka Connect.

Database defaults:

- Host: `localhost`
- Port: `5433`
- Database: `dataengineeringproject`
- User: `postgres`
- Password: `postgres`

## 2) Run Shop-App

```bash
cd Shop-App
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open: `http://localhost:5001`

## 3) Run Company-App

```bash
cd Company-App
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open: `http://localhost:5002`

## Notes

- `db.create_all()` is called automatically on app startup.
- Initial sample data is seeded for a workwear company (products, materials, suppliers, BOM, warehouse).
- If you register a user in one app, the same credentials work in the other app because both use the shared `users` table.

## Operational workflows

- Purchase Orders: `Ordered -> In Transit -> Received`
- Sales Orders: `Pending -> Picking -> Shipped -> Delivered`
- Production: `Planned -> In Progress -> Completed`
- BOM visibility: open `BOM` for grouped per-product requirements and click into product detail pages for full material breakdown.

When a purchase order reaches `Received`, material stock is added automatically.
When production reaches `Completed`, BOM materials are consumed across warehouses and finished product stock increases at the production site.
When a shop checkout is created, product stock is reduced immediately.

Warehouse logic is active:

- Materials are stored per warehouse (`material_stock`), not only globally.
- Products are stored per warehouse (`product_stock`) and aggregated for the shop.
- Purchase orders target a specific destination warehouse.
- Production can be supplied by multiple warehouses (preferred own site first, then fallback warehouses).
- Supplier and warehouse coordinates are seeded for future map visualization.

In Company-App, open `Warehouses` to inspect stock by location.

## Optional event simulator job

You can run a throttled simulator that creates and advances realistic events over time.
It is designed to avoid flooding the database and creates only a small number of events per tick.

```bash
cd Company-App
source .venv/bin/activate
python simulate_ops.py --ticks 60 --sleep 5 --day-minutes 2
```

Useful options:

- `--ticks`: number of cycles
- `--sleep`: seconds between cycles
- `--day-minutes`: real minutes that represent one simulated day (default `2`)
- `--seed`: deterministic random seed for reproducible runs

## Enable CDC connector

After the containers are up, register the Debezium connector once:

```bash
cd kafka-pipeline
python3 register_connector.py
```

The bootstrap script also configures `REPLICA IDENTITY FULL` on the tracked tables so update events include the previous status.

That connector forwards inserts and updates for:

- `sales_order`
- `purchase_order`
- `production`

## Test consumer for Kafka events

Install the small test dependency and start the printer:

```bash
cd kafka-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python print_events.py
```

The script consumes these topics from `localhost:19092` and prints events such as:

```text
[2026-05-13T18:22:01.112000+00:00] sales_order#14 created status=Pending
[2026-05-13T18:22:06.451000+00:00] sales_order#14 status changed Pending -> Picking
[2026-05-13T18:22:11.904000+00:00] purchase_order#7 status changed Ordered -> In Transit
```

To generate traffic, use the shop checkout flow, the Company-App status actions, or the optional simulator.