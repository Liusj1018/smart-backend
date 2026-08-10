"""Create/recreate the read-only role for MCP using psycopg."""
import psycopg

ADMIN_DSN = "postgresql://postgres:037875@localhost:5432/smart_commit"

SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sch_ro') THEN
        CREATE ROLE sch_ro LOGIN PASSWORD 'sch_ro_password';
    ELSE
        ALTER ROLE sch_ro WITH PASSWORD 'sch_ro_password';
    END IF;
END
$$;
GRANT CONNECT ON DATABASE smart_commit TO sch_ro;
GRANT USAGE ON SCHEMA public TO sch_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sch_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sch_ro;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM sch_ro;
REVOKE CREATE ON SCHEMA public FROM sch_ro;
"""


def main() -> None:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(SQL)
    print("[OK] sch_ro read-only role configured successfully.")


if __name__ == "__main__":
    main()