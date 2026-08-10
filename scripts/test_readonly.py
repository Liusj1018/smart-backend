"""Verify that the read-only account cannot perform writes."""
import psycopg

try:
    conn = psycopg.connect(
        "postgresql://sch_ro:sch_ro_password@localhost:5432/smart_commit"
    )
    cur = conn.cursor()
    cur.execute("INSERT INTO teams (id, name) VALUES (gen_random_uuid(), 'hacker_team')")
    conn.commit()
    print("FAIL: write was allowed!")
except psycopg.errors.InsufficientPrivilege:
    print("[OK] INSERT blocked: insufficient privilege")
except Exception as e:
    print(f"[OK] Write blocked: {type(e).__name__}: {e}")