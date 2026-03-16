"""MCP server: tools, resources, and prompts for database exploration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Optional

import asyncpg
from anthropic import AsyncAnthropic
from mcp.server.fastmcp import Context, FastMCP

from mcp_db_explorer.config import settings
from mcp_db_explorer.database import DatabaseManager, validate_sql
from mcp_db_explorer.translator import Translator


@dataclass
class AppContext:
    """Application context holding shared resources."""

    db: DatabaseManager
    translator: Translator


# Module-level reference set during lifespan, used by resources
_app_context: Optional[AppContext] = None


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage database pool and API client lifecycle."""
    global _app_context
    pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
    )
    assert pool is not None
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    app = AppContext(
        db=DatabaseManager(pool=pool),
        translator=Translator(client=client, model=settings.anthropic_model),
    )
    _app_context = app
    try:
        yield app
    finally:
        _app_context = None
        await pool.close()


mcp = FastMCP("DB Explorer", lifespan=app_lifespan)


def _get_app(ctx: Context[Any, Any, Any]) -> AppContext:
    """Extract AppContext from MCP request context."""
    return ctx.request_context.lifespan_context  # type: ignore[no-any-return]


def _get_app_from_module() -> AppContext:
    """Get AppContext from module-level variable (for resources)."""
    if _app_context is None:
        raise RuntimeError("Server not initialized")
    return _app_context


# ── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
async def list_tables(ctx: Context[Any, Any, Any]) -> str:
    """List all database tables with approximate row counts."""
    app = _get_app(ctx)
    tables = await app.db.list_tables()
    if not tables:
        return "No tables found."

    lines = [f"{'Table':<25} {'Rows':>8}", "-" * 35]
    for t in tables:
        lines.append(f"{t['table_name']:<25} {t['approx_rows']:>8}")
    return "\n".join(lines)


@mcp.tool()
async def describe_table(table_name: str, ctx: Context[Any, Any, Any]) -> str:
    """Describe a table's columns, constraints, and indexes."""
    app = _get_app(ctx)
    return await app.db.get_table_schema_text(table_name)


@mcp.tool()
async def query(question: str, ctx: Context[Any, Any, Any]) -> str:
    """Ask a natural language question about the database and get results.

    Translates the question to SQL using Claude, validates the query,
    executes it, and returns the SQL along with formatted results.
    """
    app = _get_app(ctx)

    schema = await app.db.get_schema_text()
    sql = await app.translator.translate(question, schema)

    # Defense-in-depth: validate the generated SQL
    validate_sql(sql)

    rows = await app.db.execute_sql(sql, timeout=settings.query_timeout_seconds)

    # Format output
    parts = [f"SQL:\n{sql}\n"]
    if not rows:
        parts.append("No results.")
    else:
        limited = rows[: settings.max_rows]
        columns = list(limited[0].keys())
        parts.append(" | ".join(columns))
        parts.append("-" * (len(parts[-1])))
        for row in limited:
            parts.append(" | ".join(str(row[c]) for c in columns))
        if len(rows) > settings.max_rows:
            parts.append(f"\n... ({len(rows)} total rows, showing first {settings.max_rows})")
    return "\n".join(parts)


@mcp.tool()
async def execute_sql(sql: str, ctx: Context[Any, Any, Any]) -> str:
    """Execute a raw SQL SELECT query against the database."""
    app = _get_app(ctx)
    rows = await app.db.execute_sql(sql, timeout=settings.query_timeout_seconds)

    if not rows:
        return "No results."

    limited = rows[: settings.max_rows]
    columns = list(limited[0].keys())
    lines = [" | ".join(columns), "-" * 40]
    for row in limited:
        lines.append(" | ".join(str(row[c]) for c in columns))
    return "\n".join(lines)


@mcp.tool()
async def get_sample_data(table_name: str, ctx: Context[Any, Any, Any], limit: int = 5) -> str:
    """Get sample rows from a table."""
    app = _get_app(ctx)
    capped = min(limit, settings.max_rows)
    rows = await app.db.get_sample_data(table_name, capped)

    if not rows:
        return "No data in table."

    columns = list(rows[0].keys())
    lines = [" | ".join(columns), "-" * 40]
    for row in rows:
        lines.append(" | ".join(str(row[c]) for c in columns))
    return "\n".join(lines)


# ── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("db://schema")
async def schema_resource() -> str:
    """Full database schema as text."""
    app = _get_app_from_module()
    return await app.db.get_schema_text()


@mcp.resource("db://tables/{table_name}")
async def table_resource(table_name: str) -> str:
    """Schema for a specific table."""
    app = _get_app_from_module()
    return await app.db.get_table_schema_text(table_name)


# ── Prompts ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def analyze_data(topic: str) -> str:
    """Generate a data analysis workflow for a given topic."""
    return f"""\
Analyze the database to answer questions about: {topic}

Steps:
1. Use list_tables to see available tables
2. Use describe_table on relevant tables to understand the schema
3. Use query to ask specific questions about {topic}
4. Summarize findings with key metrics and insights"""


@mcp.prompt()
def generate_report(metric: str) -> str:
    """Generate a report for a specific business metric."""
    return f"""\
Generate a report on: {metric}

Steps:
1. Use list_tables to identify relevant data sources
2. Use get_sample_data to understand the data format
3. Use query to calculate {metric} with appropriate aggregations
4. Present results in a clear, structured format with totals and trends"""


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
