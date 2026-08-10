"""create initial tables - Revision ID: 001"""
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("teams",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
        sa.UniqueConstraint("slug", name=op.f("uq_teams_slug")))
    op.create_index(op.f("ix_teams_slug"), "teams", ["slug"], unique=True)

    op.create_table("users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table("team_members",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(50), server_default="member", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name=op.f("fk_team_members_team_id_teams")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_team_members_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_members")),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_id_user_id"))
    op.create_index(op.f("ix_team_members_team_id"), "team_members", ["team_id"])
    op.create_index(op.f("ix_team_members_user_id"), "team_members", ["user_id"])

    op.create_table("repos",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name=op.f("fk_repos_team_id_teams")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repos")))
    op.create_index(op.f("ix_repos_team_id"), "repos", ["team_id"])

    op.create_table("repo_members",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("repo_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(50), server_default="developer", nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"], name=op.f("fk_repo_members_repo_id_repos")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_repo_members_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repo_members")),
        sa.UniqueConstraint("repo_id", "user_id", name="uq_repo_members_repo_id_user_id"))
    op.create_index(op.f("ix_repo_members_repo_id"), "repo_members", ["repo_id"])
    op.create_index(op.f("ix_repo_members_user_id"), "repo_members", ["user_id"])

    op.create_table("commits",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("repo_id", sa.Uuid(), nullable=False),
        sa.Column("sha", sa.String(40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("additions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deletions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name=op.f("fk_commits_team_id_teams")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_commits_user_id_users")),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"], name=op.f("fk_commits_repo_id_repos")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commits")),
        sa.UniqueConstraint("sha", name=op.f("uq_commits_sha")))
    op.create_index(op.f("ix_commits_team_id"), "commits", ["team_id"])
    op.create_index(op.f("ix_commits_user_id"), "commits", ["user_id"])
    op.create_index(op.f("ix_commits_repo_id"), "commits", ["repo_id"])
    op.create_index(op.f("ix_commits_sha"), "commits", ["sha"], unique=True)

    op.create_table("audit_logs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name=op.f("fk_audit_logs_team_id_teams")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_audit_logs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")))
    op.create_index(op.f("ix_audit_logs_team_id"), "audit_logs", ["team_id"])
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_team_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_commits_sha"), table_name="commits")
    op.drop_index(op.f("ix_commits_repo_id"), table_name="commits")
    op.drop_index(op.f("ix_commits_user_id"), table_name="commits")
    op.drop_index(op.f("ix_commits_team_id"), table_name="commits")
    op.drop_table("commits")
    op.drop_index(op.f("ix_repo_members_user_id"), table_name="repo_members")
    op.drop_index(op.f("ix_repo_members_repo_id"), table_name="repo_members")
    op.drop_table("repo_members")
    op.drop_index(op.f("ix_repos_team_id"), table_name="repos")
    op.drop_table("repos")
    op.drop_index(op.f("ix_team_members_user_id"), table_name="team_members")
    op.drop_index(op.f("ix_team_members_team_id"), table_name="team_members")
    op.drop_table("team_members")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_teams_slug"), table_name="teams")
    op.drop_table("teams")
