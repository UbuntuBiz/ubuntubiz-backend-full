"""Add persistent sale idempotency and token revocation version."""

from alembic import op
import sqlalchemy as sa

revision = "0002_idempotency_and_token_version"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

TENANT_POLICIES = {
    "audit_log": ("business_id = current_setting('app.business_id', true)",),
    "products": ("business_id = current_setting('app.business_id', true)",),
    "product_aliases": (
        "business_id IS NULL OR business_id = current_setting('app.business_id', true)",
        "business_id = current_setting('app.business_id', true)",
    ),
    "inventory_events": ("business_id = current_setting('app.business_id', true)",),
    "stock_levels": ("business_id = current_setting('app.business_id', true)",),
    "sales": ("business_id = current_setting('app.business_id', true)",),
    "sale_items": (
        "EXISTS (SELECT 1 FROM sales WHERE sales.id = sale_items.sale_id "
        "AND sales.business_id = current_setting('app.business_id', true))",
    ),
    "expenses": ("business_id = current_setting('app.business_id', true)",),
    "daily_metrics": ("business_id = current_setting('app.business_id', true)",),
    "alerts": ("business_id = current_setting('app.business_id', true)",),
    "agent_tasks": ("business_id = current_setting('app.business_id', true)",),
    "agent_tool_calls": (
        "EXISTS (SELECT 1 FROM agent_tasks WHERE agent_tasks.id = agent_tool_calls.task_id "
        "AND agent_tasks.business_id = current_setting('app.business_id', true))",
    ),
    "approvals": ("business_id = current_setting('app.business_id', true)",),
    "knowledge_chunks": (
        "scope = 'global' OR business_id = current_setting('app.business_id', true)",
        "scope != 'global' AND business_id = current_setting('app.business_id', true)",
    ),
    "messages": ("business_id = current_setting('app.business_id', true)",),
    "blockchain_transactions": (
        "related_business_id = current_setting('app.business_id', true)",
    ),
    "blockchain_events": (
        "related_business_id IS NULL OR related_business_id = current_setting('app.business_id', true)",
    ),
}


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    return column_name in {
        column["name"] for column in sa.inspect(bind).get_columns(table_name)
    }


def _constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    return any(
        constraint.get("name") == constraint_name
        for constraint in sa.inspect(bind).get_unique_constraints(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, "sales", "idempotency_key"):
        op.add_column("sales", sa.Column("idempotency_key", sa.String(length=128), nullable=True))

    if not _constraint_exists(bind, "sales", "uq_sales_business_idempotency"):
        with op.batch_alter_table("sales") as batch_op:
            batch_op.create_unique_constraint(
                "uq_sales_business_idempotency",
                ["business_id", "idempotency_key"],
            )

    if not _column_exists(bind, "users", "token_version"):
        op.add_column(
            "users",
            sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
        )

    if not _column_exists(bind, "sale_items", "unit_cost"):
        op.add_column("sale_items", sa.Column("unit_cost", sa.Integer(), nullable=True))

    if not _column_exists(bind, "knowledge_chunks", "chunk_index"):
        op.add_column("knowledge_chunks", sa.Column("chunk_index", sa.Integer(), nullable=True))
    if not _constraint_exists(bind, "knowledge_chunks", "uq_knowledge_source_chunk"):
        with op.batch_alter_table("knowledge_chunks") as batch_op:
            batch_op.create_unique_constraint(
                "uq_knowledge_source_chunk",
                ["business_id", "source", "chunk_index"],
            )

    if bind.dialect.name == "postgresql":
        for table_name, expressions in TENANT_POLICIES.items():
            policy_name = f"tenant_guard_{table_name}"
            using_expression = expressions[0]
            check_expression = expressions[1] if len(expressions) > 1 else using_expression
            op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
            op.execute(f'DROP POLICY IF EXISTS "{policy_name}" ON "{table_name}"')
            op.execute(
                f'CREATE POLICY "{policy_name}" ON "{table_name}" '
                f"USING ({using_expression}) WITH CHECK ({check_expression})"
            )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        for table_name in TENANT_POLICIES:
            policy_name = f"tenant_guard_{table_name}"
            op.execute(f'DROP POLICY IF EXISTS "{policy_name}" ON "{table_name}"')
            op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')

    if _constraint_exists(bind, "sales", "uq_sales_business_idempotency"):
        with op.batch_alter_table("sales") as batch_op:
            batch_op.drop_constraint("uq_sales_business_idempotency", type_="unique")

    if _column_exists(bind, "sales", "idempotency_key"):
        op.drop_column("sales", "idempotency_key")

    if _column_exists(bind, "users", "token_version"):
        op.drop_column("users", "token_version")

    if _column_exists(bind, "sale_items", "unit_cost"):
        op.drop_column("sale_items", "unit_cost")

    if _constraint_exists(bind, "knowledge_chunks", "uq_knowledge_source_chunk"):
        with op.batch_alter_table("knowledge_chunks") as batch_op:
            batch_op.drop_constraint("uq_knowledge_source_chunk", type_="unique")
    if _column_exists(bind, "knowledge_chunks", "chunk_index"):
        op.drop_column("knowledge_chunks", "chunk_index")
