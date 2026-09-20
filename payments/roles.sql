-- =====================================================================
-- Lampy payments database — roles (the "firewall database")
-- Run ONCE as a superuser (postgres) BEFORE schema.sql.
--
-- Passwords come from the Secure Vault at deploy time. Use psql variable
-- substitution so no secret ever lands in a file or in shell history:
--
--   psql -h <host> -U postgres -d lampy_payments \
--        -v owner_pw="$(vault_read payments_owner)" \
--        -v app_pw="$(vault_read payments_app)" \
--        -v ro_pw="$(vault_read payments_readonly)" \
--        -f roles.sql
--
-- ("vault_read" is a placeholder for whatever the deploy environment uses
-- to fetch from the Secure Vault; the point is the value never touches disk.)
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'payments_owner') THEN
        CREATE ROLE payments_owner LOGIN PASSWORD :'owner_pw';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'payments_app') THEN
        CREATE ROLE payments_app LOGIN PASSWORD :'app_pw';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'payments_readonly') THEN
        CREATE ROLE payments_readonly LOGIN PASSWORD :'ro_pw';
    END IF;
END
$$;

-- The migration owner administers the payments database.
GRANT ALL PRIVILEGES ON DATABASE lampy_payments TO payments_owner;
-- The app and read-only roles only need to connect; table rights are
-- granted precisely in schema.sql.
GRANT CONNECT ON DATABASE lampy_payments TO payments_app, payments_readonly;
