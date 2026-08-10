-- Create a read-only PostgreSQL account for MCP server access.
-- Run as a superuser against the smart_commit database:
--   psql -U postgres -d smart_commit -f scripts/create_readonly_user.sql

-- Create the role (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sch_ro') THEN
        CREATE ROLE sch_ro LOGIN PASSWORD 'sch_ro_password';
    END IF;
END
$$;

-- Grant connect to the database
GRANT CONNECT ON DATABASE smart_commit TO sch_ro;

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO sch_ro;

-- Grant read-only access to all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sch_ro;

-- Set default privileges so future tables are also readable
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sch_ro;

-- Revoke write permissions (defense in depth)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM sch_ro;
REVOKE CREATE ON SCHEMA public FROM sch_ro;