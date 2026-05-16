# dataengineeringproject

End-to-end local data engineering playground with:

- `Shop-App`: customer-facing storefront and checkout flow
- `Company-App`: operations UI for procurement, production, and fulfillment
- PostgreSQL as system of record
- Debezium CDC through Kafka Connect
- Redpanda as Kafka-compatible broker
- Spark Structured Streaming notebook for downstream processing

## Architecture

`Shop-App / Company-App -> PostgreSQL WAL -> Debezium -> Kafka topics -> Spark Structured Streaming`

CDC topics emitted by Debezium:

- `opsdb.public.sales_order`
- `opsdb.public.purchase_order`
- `opsdb.public.production`

## Prerequisites

- Docker Desktop
- Python 3.11+ (3.10 also works)
- Optional for notebook: local Spark/PySpark environment

## 1) Start Infrastructure

From repository root:

```powershell
docker compose up -d
```

This starts:

- PostgreSQL (`localhost:5433`)
- Redpanda Kafka endpoint (`localhost:19092`)
- Kafka Connect REST (`localhost:8083`)

Database defaults:

- Host: `localhost`
- Port: `5433`
- Database: `dataengineeringproject`
- User: `postgres`
- Password: `postgres`

## 2) Run the Flask Apps

### Shop-App

```powershell
cd Shop-App
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open: `http://localhost:5001`

### Company-App

```powershell
cd Company-App
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open: `http://localhost:5002`

Notes:

- tables are auto-created on app startup
- sample operational data is seeded automatically
- both apps share the same `users` table

## 3) Enable CDC Connector (Debezium)

Run once after containers are up:

```powershell
cd kafka-pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python register_connector.py
```

What this does:

- registers or updates connector `orders-cdc` at Kafka Connect
- sets `REPLICA IDENTITY FULL` on tracked tables
- enables CDC capture for:
  - `public.sales_order`
  - `public.purchase_order`
  - `public.production`

## 4) Validate Kafka Events Quickly

```powershell
cd kafka-pipeline
.\.venv\Scripts\Activate.ps1
python print_events.py --bootstrap-servers localhost:19092
```

Expected output pattern:

```text
[2026-05-13T18:22:01.112000+00:00] sales_order#14 created status=Pending
[2026-05-13T18:22:06.451000+00:00] sales_order#14 status changed Pending -> Picking
[2026-05-13T18:22:11.904000+00:00] purchase_order#7 status changed Ordered -> In Transit
```

## 5) Generate Operational Traffic

You can generate events from UI interactions or simulator.

### Manual

- create checkouts in Shop-App
- advance statuses in Company-App

### Simulator (recommended)

```powershell
cd Company-App
.\.venv\Scripts\Activate.ps1
python simulate_ops.py --ticks 60 --sleep 5 --day-minutes 2
```

Alias entry point is also available:

```powershell
python ops_sim.py --ticks 60 --sleep 5 --day-minutes 2
```

Useful options:

- `--ticks`: number of cycles
- `--sleep`: seconds between cycles
- `--day-minutes`: real minutes mapped to one simulated day
- `--seed`: deterministic random seed

## 6) Run Spark Processing Notebook

Notebook path:

- `Databricks/ProcessKafkaEvents.ipynb`

### Local Spark runtime (recommended for this repo)

- use `KAFKA_BOOTSTRAP=localhost:19092`
- run notebook in VS Code/Jupyter with local PySpark

### Databricks runtime

Databricks cannot directly access your local Docker endpoints (`localhost:*`) by default.
You need one of the following:

- routable broker endpoint reachable by Databricks
- private network connectivity (VPN/VNet)
- explicit tunneling/proxy setup

If no network path exists, execute the notebook locally.

## 7) Suggested End-to-End Test Flow

1. `docker compose up -d`
2. Start both Flask apps
3. Register connector via `register_connector.py`
4. Start `print_events.py` and keep it running
5. Run `simulate_ops.py` (or `ops_sim.py`) for 2-5 minutes
6. Run notebook streaming cells and verify parquet output and status aggregations

If step 4 shows events and the notebook writes output files, the full pipeline is working.