-- =====================================================================
-- Lampy payments database — schema (the "firewall database")
-- PostgreSQL 16 + TimescaleDB. Run as the migration owner (payments_owner)
-- AFTER creating the database and roles (see roles.sql).
--
--   createdb -h <host> -U postgres lampy_payments
--   psql -h <host> -U payments_owner -d lampy_payments -f schema.sql
--
-- WHAT THIS DATABASE STORES
--   * Customer identity needed to bill and support (email, name: encrypted)
--   * Provider-issued payment tokens (opaque references such as Stripe
--     customer / payment-method IDs), plus card brand, last4, expiry
--   * Payment records (amount, currency, status) and an immutable log of
--     provider webhook events (SHA-256 of payload, never the raw payload)
--
-- WHAT IT MUST NEVER STORE (enforced in code by guards.py, not just policy)
--   * PANs (full card numbers), CVV/CVC, PINs, magnetic-stripe data
-- Card data travels customer-browser -> payment provider only (hosted
-- checkout). Our servers never see it, so there is nothing to leak.
-- =====================================================================

-- ---------------------------------------------------------------- customers
-- PII columns are AES-256-GCM ciphertext (bytea). The key lives in the
-- Secure Vault and is injected as PAYMENTS_ENC_KEY at deploy time.
CREATE TABLE IF NOT EXISTS customers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_ref  TEXT UNIQUE,                       -- idempotency key from the app
    email_enc     BYTEA NOT NULL,                    -- encrypted
    name_enc      BYTEA,                             -- encrypted, nullable
    country       CHAR(2),                           -- ISO code, not sensitive
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ                        -- soft delete (erasure)
);
CREATE INDEX IF NOT EXISTS customers_created_idx ON customers (created_at);

-- PII-free projection for the read-only role and support tooling.
CREATE OR REPLACE VIEW customer_directory AS
    SELECT id, external_ref, country, created_at, deleted_at
      FROM customers;

-- ------------------------------------------------------- payment methods
-- provider_token is an OPAQUE provider reference (e.g. pm_..., cus_...).
-- It must never be a card number: attach_payment_method() in store.py
-- runs it through the PAN guard first and refuses anything card-like.
CREATE TABLE IF NOT EXISTS payment_methods (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    provider        TEXT NOT NULL,                   -- e.g. 'stripe'
    provider_token  TEXT NOT NULL,                   -- opaque, never a PAN
    brand           TEXT,                            -- 'visa', 'mastercard', ...
    last4           CHAR(4),                         -- last four digits ONLY
    exp_month       SMALLINT CHECK (exp_month BETWEEN 1 AND 12),
    exp_year        SMALLINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at      TIMESTAMPTZ,
    UNIQUE (provider, provider_token),
    CONSTRAINT last4_format CHECK (last4 ~ '^[0-9]{4}$')
);
CREATE INDEX IF NOT EXISTS payment_methods_customer_idx
    ON payment_methods (customer_id);

-- --------------------------------------------------------------- payments
CREATE TABLE IF NOT EXISTS payments (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id      UUID NOT NULL REFERENCES customers(id),
    idempotency_key  TEXT NOT NULL UNIQUE,           -- client-generated
    purpose          TEXT NOT NULL
                     CHECK (purpose IN ('donation', 'membership', 'other')),
    amount_cents     INTEGER NOT NULL CHECK (amount_cents > 0),
    currency         CHAR(3) NOT NULL,               -- ISO 4217
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'requires_action',
                                       'succeeded', 'failed',
                                       'refunded', 'disputed')),
    provider         TEXT NOT NULL,
    provider_charge_id TEXT,                        -- opaque provider ref
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS payments_customer_idx ON payments (customer_id);
CREATE INDEX IF NOT EXISTS payments_status_idx ON payments (status);
CREATE INDEX IF NOT EXISTS payments_charge_idx ON payments (provider_charge_id);

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS payments_touch ON payments;
CREATE TRIGGER payments_touch
    BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- -------------------------------------------------------- webhook events
-- Immutable, idempotent log of provider callbacks. We store a SHA-256 of
-- the raw payload — never the payload itself — so card data cannot end up
-- here even if a provider ever echoes it back.
CREATE TABLE IF NOT EXISTS payment_events (
    id            BIGSERIAL PRIMARY KEY,
    payment_id    UUID REFERENCES payments(id),
    provider      TEXT NOT NULL,
    event_id      TEXT NOT NULL,                     -- provider's event id
    event_type    TEXT NOT NULL,                     -- e.g. 'charge.succeeded'
    payload_hash  TEXT NOT NULL,                     -- sha256 hex, 64 chars
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, event_id),                     -- duplicate delivery safe
    CONSTRAINT payload_hash_format CHECK (payload_hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS payment_events_payment_idx
    ON payment_events (payment_id);

-- ------------------------------------------------------------ access audit
-- Append-only: the app role may INSERT but never UPDATE/DELETE (see grants).
CREATE TABLE IF NOT EXISTS payment_access_audit (
    id         BIGSERIAL PRIMARY KEY,
    actor      TEXT NOT NULL,        -- service account or admin username
    action     TEXT NOT NULL,        -- read_customer | refund | ...
    target_id  UUID,
    detail     TEXT,                 -- free text, must not contain PII/secrets
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS payment_access_audit_actor_idx
    ON payment_access_audit (actor, at);

-- =====================================================================
-- Privileges: least privilege, append-only audit.
-- The migration owner (payments_owner) runs this file, so it owns all
-- objects. PUBLIC gets nothing.
-- =====================================================================
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO payments_app, payments_readonly;

GRANT SELECT, INSERT, UPDATE ON customers TO payments_app;
GRANT SELECT, INSERT, UPDATE ON payment_methods TO payments_app;
GRANT SELECT, INSERT, UPDATE ON payments TO payments_app;
GRANT SELECT, INSERT ON payment_events TO payments_app;      -- append-only
GRANT INSERT ON payment_access_audit TO payments_app;       -- append-only
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO payments_app;

GRANT SELECT ON payments, payment_events TO payments_readonly;
GRANT SELECT ON customer_directory, payment_methods TO payments_readonly;
-- NOTE: payments_readonly is deliberately NOT granted on customers or
-- payment_access_audit (encrypted PII and audit trail stay restricted).

ALTER DEFAULT PRIVILEGES FOR ROLE payments_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO payments_app;
ALTER DEFAULT PRIVILEGES FOR ROLE payments_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO payments_app;
ALTER DEFAULT PRIVILEGES FOR ROLE payments_owner IN SCHEMA public
    REVOKE UPDATE, DELETE ON TABLES FROM payments_app;
