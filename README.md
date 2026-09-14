# Arena Onsale

World Cup-scale ticket onsale for a fictional **Cup26** final. The point of this repo is not a CRUD form — it is a working booking path that stays correct when a million people arrive and only tens of thousands of seats exist.

## What it proves

- The site stays up because most fans sit in a **waiting room**, not on the database.
- **Assigned seats** are held with a Redis `SET NX` lock plus a short `SELECT … FOR UPDATE`, then a 10-minute `HELD` TTL — never an open transaction during payment.
- **General admission** uses an optimistic version counter with jittered retries.
- Payments are **idempotent**. Abandoned holds expire. Confirming a sale is an optimistic `HELD → SOLD` write. Oversell and double-charge are treated as product bugs.

## Run locally

```bash
cp .env.example .env
make up          # Postgres, PgBouncer, Redis
uv sync
make run         # API on :8000
```

Probes:

- `GET /health/live` — process is up
- `GET /health/ready` — Postgres + Redis + in-process pool stats
- `GET /metrics` — Prometheus gauges for the app connection pool

```bash
make test
make lint
```

Application traffic goes through **PgBouncer** (`localhost:6432`, transaction pooling). Alembic talks to Postgres on `localhost:5432` so migrations can use prepared statements.

```bash
make migrate
make seed          # Cup26 Final, small layout (88 assigned + 40 GA)
```

Catalog (display-only map — booking will not trust it):

- `GET /matches`
- `GET /matches/{id}`
- `GET /matches/{id}/map`  (Redis cache, 3s TTL)

Assigned-seat holds (pessimistic: Redis `SET NX` then a short `SELECT … FOR UPDATE`; 10-minute TTL, no lock held during payment):

- `POST /matches/{id}/holds` with header `Idempotency-Key`
- `GET /holds/{id}`

General admission (optimistic `version` counter, 3 attempts, 50–200ms jitter):

- `POST /matches/{id}/ga-reservations` with header `Idempotency-Key`
- `GET /ga-reservations/{id}`



## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the hybrid locking model this codebase implements.

## Layout

```
src/arena_onsale/     domain + API
tests/                unit + integration
deploy compose        Postgres 16, PgBouncer, Redis 7
```
