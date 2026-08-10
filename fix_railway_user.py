import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:SnZrOUcDZCPxIaJCwbIPNNUDhBlNZVIo@shortline.proxy.rlwy.net:56591/railway"

import logging
logging.disable(logging.INFO)

from sqlalchemy import text
from app.db.session import engine
from app.core.security import hash_password

DEMO_EMAIL = "demo@smartdashboard.dev"
DEMO_PASSWORD = "demo-password-123"
DEMO_NAME = "Demo User"

async def main():
    h = hash_password(DEMO_PASSWORD)
    print(f"Generated bcrypt hash: {h[:20]}...")

    async with engine.begin() as conn:
        # Check if demo user exists
        result = await conn.execute(
            text("SELECT id, email, password_hash FROM users WHERE email = :email"),
            {"email": DEMO_EMAIL},
        )
        row = result.fetchone()

        if row:
            print(f"User exists: id={row[0]}, updating password...")
            await conn.execute(
                text("UPDATE users SET password_hash = :h, name = :name WHERE id = :id"),
                {"h": h, "name": DEMO_NAME, "id": row[0]},
            )
            user_id = row[0]
        else:
            print("User not found, creating...")
            result = await conn.execute(
                text(
                    "INSERT INTO users (id, email, name, password_hash) "
                    "VALUES (gen_random_uuid(), :email, :name, :h) RETURNING id"
                ),
                {"email": DEMO_EMAIL, "name": DEMO_NAME, "h": h},
            )
            user_id = result.fetchone()[0]
            print(f"Created user: id={user_id}")

        # Get first team
        result = await conn.execute(text("SELECT id, name FROM teams ORDER BY name LIMIT 1"))
        team = result.fetchone()
        print(f"Using team: id={team[0]}, name={team[1]}")

        # Check team membership
        result = await conn.execute(
            text("SELECT id FROM team_members WHERE team_id = :tid AND user_id = :uid"),
            {"tid": team[0], "uid": user_id},
        )
        if not result.fetchone():
            print("Adding team membership...")
            await conn.execute(
                text(
                    "INSERT INTO team_members (team_id, user_id, role) VALUES (:tid, :uid, 'admin')"
                ),
                {"tid": team[0], "uid": user_id},
            )
        else:
            print("Team membership already exists")

    print("\nDone! Verifying...")
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT u.email, u.name, tm.role, t.name FROM users u JOIN team_members tm ON tm.user_id = u.id JOIN teams t ON t.id = tm.team_id WHERE u.email = :email"),
            {"email": DEMO_EMAIL},
        )
        row = result.fetchone()
        if row:
            print(f"  email: {row[0]}")
            print(f"  name: {row[1]}")
            print(f"  team_role: {row[2]}")
            print(f"  team: {row[3]}")

    await engine.dispose()

asyncio.run(main())