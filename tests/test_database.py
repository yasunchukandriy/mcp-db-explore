"""Tests for database module: SQL validation and DatabaseManager."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mcp_db_explorer.database import DatabaseManager, validate_sql, validate_table_name

# ── validate_sql ─────────────────────────────────────────────────────────────


class TestValidateSql:
    """Tests for validate_sql()."""

    def test_allows_select(self) -> None:
        validate_sql("SELECT * FROM customers")

    def test_allows_select_lowercase(self) -> None:
        validate_sql("select id, name from products")

    def test_allows_explain(self) -> None:
        validate_sql("EXPLAIN SELECT * FROM orders")

    def test_allows_with_cte(self) -> None:
        validate_sql("WITH totals AS (SELECT sum(total) FROM orders) SELECT * FROM totals")

    def test_allows_select_with_leading_whitespace(self) -> None:
        validate_sql("  SELECT 1")

    def test_blocks_insert(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("INSERT INTO customers (email) VALUES ('x')")

    def test_blocks_update(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("UPDATE customers SET email = 'x'")

    def test_blocks_delete(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("DELETE FROM customers")

    def test_blocks_drop(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("DROP TABLE customers")

    def test_blocks_alter(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("ALTER TABLE customers ADD COLUMN age INT")

    def test_blocks_truncate(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("TRUNCATE customers")

    def test_blocks_create(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("CREATE TABLE evil (id INT)")

    def test_blocks_grant(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("GRANT ALL ON customers TO evil")

    def test_blocks_revoke(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("REVOKE ALL ON customers FROM evil")

    def test_blocks_copy(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("COPY customers TO '/tmp/dump.csv'")

    def test_blocks_case_insensitive(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("dRoP tAbLe customers")

    def test_blocks_forbidden_inside_select(self) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            validate_sql("SELECT * FROM customers WHERE DELETE = 1")

    def test_blocks_multiple_statements(self) -> None:
        with pytest.raises(ValueError, match="Multiple statements"):
            validate_sql("SELECT 1; SELECT 2")

    def test_blocks_non_select_start(self) -> None:
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_sql("SHOW TABLES")

    def test_blocks_empty(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            validate_sql("")

    def test_blocks_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            validate_sql("   ")


# ── validate_table_name ──────────────────────────────────────────────────────


class TestValidateTableName:
    """Tests for validate_table_name()."""

    def test_allows_simple_name(self) -> None:
        validate_table_name("customers")

    def test_allows_underscore(self) -> None:
        validate_table_name("order_items")

    def test_allows_leading_underscore(self) -> None:
        validate_table_name("_internal")

    def test_allows_uppercase(self) -> None:
        validate_table_name("MyTable")

    def test_allows_digits_after_first(self) -> None:
        validate_table_name("table123")

    def test_blocks_sql_injection(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("customers; DROP TABLE users")

    def test_blocks_spaces(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("my table")

    def test_blocks_special_chars(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("table-name")

    def test_blocks_empty(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("")

    def test_blocks_leading_digit(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("1table")

    def test_blocks_dot(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("schema.table")


# ── DatabaseManager ──────────────────────────────────────────────────────────


def _make_record(data: dict) -> dict:
    """Helper: asyncpg Record is dict-like, we use dicts in mocks."""
    return data


class TestDatabaseManagerListTables:
    """Tests for DatabaseManager.list_tables()."""

    async def test_calls_pool(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        await db.list_tables()
        mock_pool.fetch.assert_called_once()

    async def test_returns_list_of_dicts(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = [
            {"table_name": "customers", "approx_rows": 10},
            {"table_name": "orders", "approx_rows": 5},
        ]
        result = await db.list_tables()
        assert len(result) == 2
        assert result[0]["table_name"] == "customers"
        assert result[1]["approx_rows"] == 5

    async def test_returns_empty_list(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = []
        result = await db.list_tables()
        assert result == []


class TestDatabaseManagerDescribeTable:
    """Tests for DatabaseManager.describe_table()."""

    async def test_validates_table_name(self, db: DatabaseManager) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            await db.describe_table("x; DROP TABLE y")

    async def test_calls_pool_three_times(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = []
        await db.describe_table("customers")
        assert mock_pool.fetch.call_count == 3

    async def test_returns_structured_result(
        self, db: DatabaseManager, mock_pool: AsyncMock
    ) -> None:
        col = {
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
            "column_default": "nextval('customers_id_seq')",
            "character_maximum_length": None,
        }
        constraint = {
            "constraint_name": "customers_pkey",
            "constraint_type": "PRIMARY KEY",
            "column_name": "id",
        }
        index = {
            "indexname": "customers_pkey",
            "indexdef": "CREATE UNIQUE INDEX customers_pkey ON customers USING btree (id)",
        }
        mock_pool.fetch.side_effect = [[col], [constraint], [index]]

        result = await db.describe_table("customers")
        assert result["table_name"] == "customers"
        assert len(result["columns"]) == 1
        assert result["columns"][0]["column_name"] == "id"
        assert len(result["constraints"]) == 1
        assert len(result["indexes"]) == 1


class TestDatabaseManagerGetSampleData:
    """Tests for DatabaseManager.get_sample_data()."""

    async def test_validates_table_name(self, db: DatabaseManager) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            await db.get_sample_data("invalid table!")

    async def test_calls_pool_with_limit(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = []
        await db.get_sample_data("customers", 10)
        call_args = mock_pool.fetch.call_args[0][0]
        assert "LIMIT 10" in call_args
        assert "customers" in call_args

    async def test_returns_list_of_dicts(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = [
            {"id": 1, "name": "Hans"},
            {"id": 2, "name": "Anna"},
        ]
        result = await db.get_sample_data("customers")
        assert len(result) == 2
        assert result[0]["name"] == "Hans"


class TestDatabaseManagerExecuteSql:
    """Tests for DatabaseManager.execute_sql()."""

    async def test_validates_before_executing(self, db: DatabaseManager) -> None:
        with pytest.raises(ValueError, match="Forbidden keyword"):
            await db.execute_sql("DROP TABLE customers")

    async def test_passes_timeout(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        await db.execute_sql("SELECT 1", timeout=5.0)
        mock_pool.fetch.assert_called_once_with("SELECT 1", timeout=5.0)

    async def test_returns_results(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = [{"count": 42}]
        result = await db.execute_sql("SELECT count(*) as count FROM customers")
        assert result == [{"count": 42}]

    async def test_no_timeout_by_default(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        await db.execute_sql("SELECT 1")
        mock_pool.fetch.assert_called_once_with("SELECT 1", timeout=None)


class TestDatabaseManagerGetSchemaText:
    """Tests for DatabaseManager.get_schema_text()."""

    async def test_empty_database(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        mock_pool.fetch.return_value = []
        result = await db.get_schema_text()
        assert result == ""

    async def test_formats_multiple_tables(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        # First call: list_tables
        tables = [
            {"table_name": "customers", "approx_rows": 10},
            {"table_name": "orders", "approx_rows": 5},
        ]
        # Subsequent calls: describe_table for each (3 calls per table)
        col_customers = {
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
            "column_default": None,
            "character_maximum_length": None,
        }
        col_orders = {
            "column_name": "total",
            "data_type": "numeric",
            "is_nullable": "NO",
            "column_default": None,
            "character_maximum_length": None,
        }
        mock_pool.fetch.side_effect = [
            tables,  # list_tables
            [col_customers],
            [],
            [],  # describe customers
            [col_orders],
            [],
            [],  # describe orders
        ]
        result = await db.get_schema_text()
        assert "Table: customers" in result
        assert "Table: orders" in result
        assert "id: integer NOT NULL" in result
        assert "total: numeric NOT NULL" in result


class TestDatabaseManagerGetTableSchemaText:
    """Tests for DatabaseManager.get_table_schema_text()."""

    async def test_basic_output(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        col = {
            "column_name": "email",
            "data_type": "character varying",
            "is_nullable": "YES",
            "column_default": None,
            "character_maximum_length": 255,
        }
        mock_pool.fetch.side_effect = [[col], [], []]
        result = await db.get_table_schema_text("customers")
        assert "Table: customers" in result
        assert "email: character varying NULL" in result

    async def test_includes_default(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        col = {
            "column_name": "country",
            "data_type": "character varying",
            "is_nullable": "NO",
            "column_default": "'DE'::character varying",
            "character_maximum_length": 2,
        }
        mock_pool.fetch.side_effect = [[col], [], []]
        result = await db.get_table_schema_text("customers")
        assert "DEFAULT 'DE'::character varying" in result

    async def test_includes_constraints(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        col = {
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
            "column_default": None,
            "character_maximum_length": None,
        }
        constraint = {
            "constraint_name": "customers_pkey",
            "constraint_type": "PRIMARY KEY",
            "column_name": "id",
        }
        mock_pool.fetch.side_effect = [[col], [constraint], []]
        result = await db.get_table_schema_text("customers")
        assert "Constraints:" in result
        assert "customers_pkey: PRIMARY KEY (id)" in result

    async def test_includes_indexes(self, db: DatabaseManager, mock_pool: AsyncMock) -> None:
        col = {
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
            "column_default": None,
            "character_maximum_length": None,
        }
        index = {
            "indexname": "idx_orders_status",
            "indexdef": "CREATE INDEX idx_orders_status ON orders USING btree (status)",
        }
        mock_pool.fetch.side_effect = [[col], [], [index]]
        result = await db.get_table_schema_text("orders")
        assert "Indexes:" in result
        assert "idx_orders_status" in result

    async def test_no_constraints_no_indexes(
        self, db: DatabaseManager, mock_pool: AsyncMock
    ) -> None:
        col = {
            "column_name": "name",
            "data_type": "text",
            "is_nullable": "YES",
            "column_default": None,
            "character_maximum_length": None,
        }
        mock_pool.fetch.side_effect = [[col], [], []]
        result = await db.get_table_schema_text("simple")
        assert "Constraints:" not in result
        assert "Indexes:" not in result
