# Architecture

Arena Onsale is a modular monolith. One codebase, several processes later (API, workers, mock PSP). Postgres is the source of truth. Redis is the hot path. PgBouncer stands in front of Postgres so Python workers cannot open unbounded connections.

This file is the spec for locking. Features land against it, not against a generic CRUD template.

## Capacity shape

A Cup26 final has on the order of 80,000 seats and a million people at the door. Almost nobody is allowed to open a booking transaction. A waiting room admits a bounded cohort; checkout concurrency is capped so `FOR UPDATE` cannot exhaust the pool.

Default knobs (env-overridable):

- Hold TTL: **10 minutes**
- GA optimistic retries: **3** with **50–200ms** jitter
- Waiting-room admit rate: **50,000 / minute** (traffic shaping, not inventory)
- Concurrent checkout bulkhead: **3,000**

## Hybrid locking (the rulebook)

| Step | Strategy | Why |
| --- | --- | --- |
| Enter the site | Waiting room / rate limit | Survive the herd before any lock exists |
| Browse the map | Short-TTL cache | Approximate “seats left” is display-only |
| Reserve assigned seat A12 | Redis `SET NX EX` then short `SELECT … FOR UPDATE` | One physical seat; loser fails in ~1ms |
| Hold while the fan pays | `HELD` row + Redis TTL | No database lock is held during payment I/O |
| Buy GA (no seat number) | Optimistic `version` counter + jittered retry | Contention is spread across a pool |
| Update a fan profile | Optimistic `version` | Single-user row, conflict is rare |
| Charge the card | Idempotency key | Double-click / retry must not double-charge |
| Mark `SOLD` | Optimistic `WHERE status = 'HELD' AND version = n` | Hold already serialised the seat |
| Abandon checkout | TTL + worker | Seat returns to `AVAILABLE` |
| Email / QR | Outbox after commit | Retries without blocking checkout |

## Golden rules

1. Shrink the crowd before locking anything.
2. Lock only what is scarce (a specific seat, not the stadium table).
3. Database locks last milliseconds. Business holds last minutes, with TTL.
4. Never hold a database lock during payment.
5. Cache is for display. Booking always re-checks Postgres.
6. Payments are idempotent. Holds and confirms are idempotent too.
7. If optimistic finalise fails after a successful capture, refund and alert. Never oversell.

## Connection pooling

Each uvicorn worker owns a small SQLAlchemy/asyncpg pool (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`). PgBouncer multiplexes those onto Postgres in **transaction** mode. The app disables asyncpg’s prepared-statement cache (`statement_cache_size=0`) so statements cannot leak across borrowed connections.

`/health/ready` and `/metrics` expose in-process pool occupancy. That is how we show pool starvation in load tests: admit too many shoppers on purpose, then tighten the waiting room.

## Load harness

- `python -m arena_onsale.load.flood` reserves a score range with `INCRBY` on `waiting:onsale:seq`, then `ZADD NX` in batches of 5,000. HTTP join is the slow path; the flooder is how a million fans appear in the room without a million HTTP connections.
- Locust (`loadtests/locustfile.py`, optional `[dependency-groups] load`) is the shopper mix: mostly queue polling, a thin admitted browse. Caption a run as **1 million in the room, N admitted, zero oversell** — never as a million concurrent users at checkout.

## What comes next

The booking path, waiting room, and load harness are in. Optional later: a lottery admit strategy, a real CDN in front of the room, Kafka instead of outbox + Redis, k8s, a seat-map UI.
