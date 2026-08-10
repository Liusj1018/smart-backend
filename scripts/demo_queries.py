"""S8 演示脚本：通过只读账号查询三个数据问题（模拟 MCP 直连数据库）。"""
import psycopg

DSN = "postgresql://sch_ro:sch_ro_password@localhost:5432/smart_commit"


def main() -> None:
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            print("=== Q1: 每个团队有多少成员？ ===")
            cur.execute(
                """
                SELECT t.name, COUNT(tm.id)
                FROM teams t
                LEFT JOIN team_members tm ON t.id = tm.team_id
                GROUP BY t.id, t.name
                ORDER BY t.name
                """
            )
            for name, cnt in cur.fetchall():
                print(f"  {name}: {cnt} 人")

            print("\n=== Q2: 谁的提交最多？（Top 5） ===")
            cur.execute(
                """
                SELECT u.name, u.github_username, COUNT(c.id) AS cnt
                FROM commits c
                JOIN users u ON c.user_id = u.id
                GROUP BY u.id, u.name, u.github_username
                ORDER BY cnt DESC
                LIMIT 5
                """
            )
            for name, gh, cnt in cur.fetchall():
                print(f"  {name} (@{gh}): {cnt} 条提交")

            print("\n=== Q3: 每个仓库有多少条提交？ ===")
            cur.execute(
                """
                SELECT r.name, COUNT(c.id) AS cnt
                FROM repos r
                LEFT JOIN commits c ON c.repo_id = r.id
                GROUP BY r.id, r.name
                ORDER BY r.name
                """
            )
            for name, cnt in cur.fetchall():
                print(f"  {name}: {cnt} 条提交")

    print("\n[OK] MCP read-only account query succeeded - all 3 questions answered.")


if __name__ == "__main__":
    main()