# Lampy payments — the "firewall database"

Customer and payment records live in a **separate PostgreSQL database**
(`lampy_payments`) with its own roles, its own credentials, and firewall
rules that only let the app service reach it. It is "secured like the
vault": secrets (DB passwords, the PII encryption key, webhook secrets)
live in the Secure Vault and are injected as environment variables at
deploy time — never in the repo, never in chat, never in logs.

## What is stored

| Data | Where / how |
|---|---|
| Customer email, name | AES-256-GCM encrypted (`*_enc` BYTEA columns); key from `PAYMENTS_ENC_KEY` |
| Country, timestamps | Plaintext (not sensitive) |
| Payment method | Opaque **provider token** + brand + last4 + expiry only |
| Payments | amount, currency, purpose (`donation`/`membership`/`other`), status |
| Webhook events | Immutable log; stores **SHA-256 of payload**, never the payload |
| Access audit | Append-only; every PII read and money movement is logged |

## What is NEVER stored

Full card numbers (PANs), CVV/CVC, PINs, magnetic-stripe data. There is
no column for them, and `guards.py` rejects anything card-like (Luhn
check) before it can be written to *any* field. Card data travels
**customer browser → payment provider** via hosted checkout; our servers
never see it, so there is nothing to leak.

## Layout

- `schema.sql` — tables, indexes, least-privilege grants (run as `payments_owner`)
- `roles.sql` — one-time role creation; passwords injected from the Secure Vault
- `crypto.py` — AES-256-GCM envelope for PII columns
- `guards.py` — PAN/CVV detection, fail-closed rejection
- `store.py` — `PaymentsStore`: parameterized queries, idempotent creates,
  audited reads, legal-only status transitions
- `webhooks.py` — signature verification → idempotent event log → mapped
  status transitions. **Disabled by default**: refuses to run without a
  configured provider and webhook secret.
- `tests/` — unit tests, no live DB needed

## Firewall rules (applied at Windows bring-up, ~Sept 23)

1. **Separate database**: `lampy_payments` on the TimescaleDB host, not the
   forum database. A compromise of the forum app role yields nothing here.
2. **pg_hba**: only the app container's user on the internal Docker network
   may connect as `payments_app`; `payments_owner` only from the admin host.
3. **Docker**: the database port is NOT published to the host; the payments
   DB is reachable only on the internal backend network.
4. **Roles**: `payments_app` can SELECT/INSERT/UPDATE business tables and
   only INSERT into `payment_events` / `payment_access_audit` (append-only).
   `payments_readonly` sees payments and the PII-free `customer_directory`
   view — never the encrypted `customers` table.
5. **Secrets**: DB passwords, `PAYMENTS_ENC_KEY`, webhook secret all come
   from the Secure Vault at deploy. `roles.sql` takes them as psql
   variables so they never touch disk.

## Deploy checklist

- [ ] `createdb lampy_payments`; run `roles.sql` (vault-supplied passwords), then `schema.sql`
- [ ] Apply pg_hba + Docker network rules above
- [ ] Generate the PII key (`crypto.generate_key_b64()`), store in Secure Vault, set `PAYMENTS_ENC_KEY`
- [ ] Choose provider (donations vs memberships still open); configure hosted checkout + webhook secret
- [ ] Point the webhook URL at the app; confirm signature verification rejects a forged callback
- [ ] Key rotation: generate new key, `crypto.rotate()` each `*_enc` value, update vault, keep old key 30 days

## Retention / erasure

`customers.deleted_at` soft-deletes; a purge job hard-deletes rows (and
their payments/events, which carry no PII) after the retention window.
Payment records themselves are kept for accounting/tax as required by law.

## Status (2026-09-20)

- Unit tests: 26 tests, all passing (crypto, PAN guards, idempotent
  payments, transitions, webhook verify/dedupe) — no live DB needed.
- **Not yet tested against live PostgreSQL** (no DB reachable from this
  VM); live schema apply + integration tests queued for Windows bring-up.
- No provider chosen yet, so no real charges can be taken; the module is
  provider-agnostic and supports both one-time donations and memberships.
- Console login (`db-console/auth.py`) reuses the forum `users` table;
  payment customer records are separate and contain no passwords.
