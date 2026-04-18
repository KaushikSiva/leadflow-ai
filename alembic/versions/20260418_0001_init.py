"""Initial LeadFlow schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260418_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("raw_prompt", sa.Text(), nullable=False),
        sa.Column("canonical_brief_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("discovered_count", sa.Integer(), nullable=False),
        sa.Column("scored_count", sa.Integer(), nullable=False),
        sa.Column("enriched_count", sa.Integer(), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "prospects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("profile_url", sa.String(length=512), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("company_domain", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("source_actor", sa.String(length=255), nullable=True),
        sa.Column("source_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("profile_url"),
    )
    op.create_index("ix_prospects_profile_url", "prospects", ["profile_url"], unique=True)

    op.create_table(
        "prompt_prospects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("prompt_id", sa.String(length=36), nullable=False),
        sa.Column("prospect_id", sa.String(length=36), nullable=False),
        sa.Column("source_rank", sa.Integer(), nullable=False),
        sa.Column("ai_decision", sa.String(length=24), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("score_reason", sa.Text(), nullable=True),
        sa.Column("enrichment_status", sa.String(length=24), nullable=False),
        sa.Column("best_phone_e164", sa.String(length=32), nullable=True),
        sa.Column("phones_json", sa.JSON(), nullable=False),
        sa.Column("voicecall_call_id", sa.String(length=64), nullable=True),
        sa.Column("last_called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospect_id"], ["prospects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("prompt_id", "prospect_id", name="uq_prompt_prospect"),
    )
    op.create_index("ix_prompt_prospects_prompt_id", "prompt_prospects", ["prompt_id"], unique=False)
    op.create_index("ix_prompt_prospects_prospect_id", "prompt_prospects", ["prospect_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_prompt_prospects_prospect_id", table_name="prompt_prospects")
    op.drop_index("ix_prompt_prospects_prompt_id", table_name="prompt_prospects")
    op.drop_table("prompt_prospects")
    op.drop_index("ix_prospects_profile_url", table_name="prospects")
    op.drop_table("prospects")
    op.drop_table("prompts")
