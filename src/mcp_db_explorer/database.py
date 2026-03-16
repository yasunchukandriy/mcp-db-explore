"""Database access layer: SQL validation and async query execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import asyncpg

# Pattern matching DML/DDL keywords at word boundaries
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)

_VALID_TABLE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_ALLOWED_PREFIXES = ("SELECT", "EXPLAIN", "WITH")


def validate_sql(sql: str) -> None:
    """Validate that SQL is a read-only query. Raises ValueError if not."""
    stripped = sql.strip()

    if not stripped:
        raise ValueError("Empty SQL query")

    if ";" in stripped:
        raise ValueError("Multiple statements are not allowed")

    match = _FORBIDDEN_KEYWORDS.search(stripped)
    if match:
        raise ValueError(f"Forbidden keyword: {match.group(0).upper()}")

    upper = stripped.upper()
    if not any(upper.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
        raise ValueError("Only SELECT, EXPLAIN, and WITH queries are allowed")


def validate_table_name(name: str) -> None:
    """Validate a table name against SQL injection. Raises ValueError if invalid."""
    if not _VALID_TABLE_NAME.match(name):
        raise ValueError(f"Invalid table name: {name!r}")


@dataclass
class DatabaseManager:
    """Async database operations backed by an asyncpg connection pool."""

    pool: asyncpg.Pool

    async def list_tables(self) -> list[dict[str, Any]]:
        """List all user tables with approximate row counts."""
        query = """
            SELECT
                t.table_name,
                COALESCE(s.n_live_tup, 0) AS approx_rows
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s ON s.relname = t.table_name
            WHERE t.table_schema = 'public'
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """
        rows = await self.pool.fetch(query)
        return [dict(r) for r in rows]

    async def describe_table(self, table_name: str) -> dict[str, Any]:
        """Get column definitions, constraints, and indexes for a table."""
        validate_table_name(table_name)

        columns_query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
        """

        constraints_query = """
            SELECT
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public' AND tc.table_name = $1
            ORDER BY tc.constraint_type, kcu.column_name
        """

        indexes_query = """
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = $1
            ORDER BY indexname
        """

        columns = await self.pool.fetch(columns_query, table_name)
        constraints = await self.pool.fetch(constraints_query, table_name)
        indexes = await self.pool.fetch(indexes_query, table_name)

        return {
            "table_name": table_name,
            "columns": [dict(r) for r in columns],
            "constraints": [dict(r) for r in constraints],
            "indexes": [dict(r) for r in indexes],
        }

    async def get_sample_data(self, table_name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get sample rows from a table."""
        validate_table_name(table_name)
        query = f"SELECT * FROM {table_name} LIMIT {int(limit)}"
        rows = await self.pool.fetch(query)
        return [dict(r) for r in rows]

    async def execute_sql(self, sql: str, timeout: float | None = None) -> list[dict[str, Any]]:
        """Validate and execute a read-only SQL query."""
        validate_sql(sql)
        rows = await self.pool.fetch(sql, timeout=timeout)
        return [dict(r) for r in rows]

    async def get_schema_text(self) -> str:
        """Get full database schema as formatted text."""
        tables = await self.list_tables()
        parts: list[str] = []

        for table in tables:
            name = table["table_name"]
            parts.append(await self.get_table_schema_text(name))
            parts.append("")

        return "\n".join(parts)

    async def get_table_schema_text(self, table_name: str) -> str:
        """Get single table schema as formatted text."""
        info = await self.describe_table(table_name)
        lines: list[str] = [f"Table: {info['table_name']}"]

        lines.append("  Columns:")
        for col in info["columns"]:
            nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
            default = f" DEFAULT {col['column_default']}" if col["column_default"] else ""
            lines.append(f"    - {col['column_name']}: {col['data_type']} {nullable}{default}")

        if info["constraints"]:
            lines.append("  Constraints:")
            for con in info["constraints"]:
                lines.append(
                    f"    - {con['constraint_name']}: "
                    f"{con['constraint_type']} ({con['column_name']})"
                )

        if info["indexes"]:
            lines.append("  Indexes:")
            for idx in info["indexes"]:
                lines.append(f"    - {idx['indexname']}: {idx['indexdef']}")

        return "\n".join(lines)
