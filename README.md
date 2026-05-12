# dataengineeringproject

Two simple but fully functional Flask applications were created from the concept model:

- `Shop-App`: customer-facing shop for browsing products, account creation, cart, checkout, and order history.
- `Company-App`: internal operations page for supplier orders, material management, BOM, and production planning.

Both apps use the same PostgreSQL database and share the `users` table.

## Tech stack

- Flask
- Flask-SQLAlchemy
- Flask-Login
- PostgreSQL (Docker)
- Tailwind CSS (CDN)

## 1) Start PostgreSQL in Docker

From the project root:

```bash
docker compose up -d
```

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
- Initial sample data is seeded for products/materials/suppliers/warehouse.
- If you register a user in one app, the same credentials work in the other app because both use the shared `users` table.