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
make worker        # expire holds + admit the waiting room
```

Waiting room (no inventory lock — this is the 1M-user valve):

- `POST /waiting-room/join` `{ "visitor_id": "..." }`
- `GET /waiting-room/status/{visitor_id}`
- `GET /waiting-room/stats` — queued vs admitted vs bulkhead

Catalog, holds, GA, and checkout require header `Admission-Token` from a successful join.

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

Checkout saga (charge **outside** any DB lock; optimistic `HELD → SOLD`; refund if that write loses):

- `POST /checkout` with `hold_id` or `ga_reservation_id` and `Idempotency-Key`
- `GET /orders/{id}`
- `uv run python -m arena_onsale.worker` expires abandoned holds (`FOR UPDATE SKIP LOCKED`)

## Load (1 million in the room)

This is not “one million concurrent checkouts”. It is one million arrivals sitting in Redis, a few thousand admitted, and **zero oversell**.

```bash
make flood         # batched ZADD into the waiting-room queue
make worker        # admit at 50k/min into the 3,000 shopper bulkhead
```

Shopper traffic (optional Locust, not required for CI):

```bash
uv sync --group load
uv run locust -f loadtests/locustfile.py --host http://127.0.0.1:8000
```

Most Locust users only join and poll. A small cohort browses `/matches` after they get an `Admission-Token`.


## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the hybrid locking model this codebase implements.

## Layout

```
src/arena_onsale/     domain + API
tests/                unit + integration
deploy compose        Postgres 16, PgBouncer, Redis 7
```
