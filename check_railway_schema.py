import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:SnZrOUcDZCPxIaJCwbIPNNUDhBlNZVIo@shortline.proxy.rlwy.net:56591/railway"

from sqlalchemy import text
from app.db.session import engine

async def main():
    async with engine.connect() as conn:
        print("=== users table columns ===")
        result = await conn.execute(text(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position"
        ))
        for row in result:
            print(f"  {row[0]:20s} {row[1]:20s} nullable={row[2]:3s} default={row[3]}")

        print("\n=== teams table columns ===")
        result = await conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'teams' ORDER BY ordinal_position"
        ))
        for row in result:
            print(f"  {row[0]:20s} {row[1]}")

        print("\n=== team_members columns ===")
        result = await conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'team_members' ORDER BY ordinal_position"
        ))
        for row in result:
            print(f"  {row[0]:20s} {row[1]}")

        print("\n=== existing users ===")
        result = await conn.execute(text("SELECT id, email FROM users"))
        for row in result:
            print(f"  {row[0]}  {row[1]}")

        print("\n=== existing teams ===")
        result = await conn.execute(text("SELECT id, name FROM teams"))
        for row in result:
            print(f"  {row[0]}  {row[1]}")

    await engine.dispose()

asyncio.run(main())