"""Tests for MCP server: registration, tools, resources, prompts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_db_explorer.server import (
    _get_app_from_module,
    analyze_data,
    describe_table,
    execute_sql,
    generate_report,
    get_sample_data,
    list_tables,
    mcp,
    query,
    schema_resource,
    table_resource,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_ctx(app: object) -> MagicMock:
    """Create a mock MCP Context that returns app from lifespan_context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = app
    return ctx


def _make_app(
    *,
    tables: list | None = None,
    schema_text: str = "",
    table_schema_text: str = "",
    sample_data: list | None = None,
    execute_result: list | None = None,
    translate_result: str = "SELECT 1",
) -> MagicMock:
    """Create a mock AppContext with db and translator."""
    app = MagicMock()
    app.db.list_tables = AsyncMock(return_value=tables or [])
    app.db.get_schema_text = AsyncMock(return_value=schema_text)
    app.db.get_table_schema_text = AsyncMock(return_value=table_schema_text)
    app.db.get_sample_data = AsyncMock(return_value=sample_data or [])
    app.db.execute_sql = AsyncMock(return_value=execute_result or [])
    app.translator.translate = AsyncMock(return_value=translate_result)
    return app


# ── Registration smoke tests ────────────────────────────────────────────────


class TestToolRegistration:
    """Verify all tools are registered."""

    def test_has_expected_tools(self) -> None:
        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        expected = {"list_tables", "describe_table", "query", "execute_sql", "get_sample_data"}
        assert expected == tool_names

    def test_tool_count(self) -> None:
        assert len(mcp._tool_manager.list_tools()) == 5


class TestResourceRegistration:
    """Verify resources and templates are registered."""

    def test_has_schema_resource(self) -> None:
        resource_uris = {str(r.uri) for r in mcp._resource_manager.list_resources()}
        assert "db://schema" in resource_uris

    def test_has_table_template(self) -> None:
        template_uris = {t.uri_template for t in mcp._resource_manager.list_templates()}
        assert "db://tables/{table_name}" in template_uris


class TestPromptRegistration:
    """Verify prompts are registered."""

    def test_has_expected_prompts(self) -> None:
        prompt_names = {p.name for p in mcp._prompt_manager.list_prompts()}
        expected = {"analyze_data", "generate_report"}
        assert expected == prompt_names


# ── _get_app_from_module ─────────────────────────────────────────────────────


class TestGetAppFromModule:
    """Tests for _get_app_from_module()."""

    def test_raises_when_not_initialized(self) -> None:
        with (
            patch("mcp_db_explorer.server._app_context", None),
            pytest.raises(RuntimeError, match="Server not initialized"),
        ):
            _get_app_from_module()

    def test_returns_app_when_set(self) -> None:
        sentinel = object()
        with patch("mcp_db_explorer.server._app_context", sentinel):
            assert _get_app_from_module() is sentinel


# ── list_tables tool ─────────────────────────────────────────────────────────


class TestListTablesTool:
    """Tests for list_tables() tool function."""

    async def test_empty_tables(self) -> None:
        app = _make_app(tables=[])
        ctx = _make_ctx(app)
        result = await list_tables(ctx)
        assert result == "No tables found."

    async def test_formats_table_list(self) -> None:
        app = _make_app(
            tables=[
                {"table_name": "customers", "approx_rows": 10},
                {"table_name": "orders", "approx_rows": 5},
            ]
        )
        ctx = _make_ctx(app)
        result = await list_tables(ctx)
        assert "customers" in result
        assert "orders" in result
        assert "10" in result
        assert "5" in result

    async def test_output_has_header(self) -> None:
        app = _make_app(tables=[{"table_name": "t", "approx_rows": 0}])
        ctx = _make_ctx(app)
        result = await list_tables(ctx)
        assert "Table" in result
        assert "Rows" in result


# ── describe_table tool ──────────────────────────────────────────────────────


class TestDescribeTableTool:
    """Tests for describe_table() tool function."""

    async def test_returns_schema_text(self) -> None:
        app = _make_app(table_schema_text="Table: customers\n  Columns:\n    - id: integer")
        ctx = _make_ctx(app)
        result = await describe_table("customers", ctx)
        assert "Table: customers" in result
        app.db.get_table_schema_text.assert_called_once_with("customers")


# ── query tool ───────────────────────────────────────────────────────────────


class TestQueryTool:
    """Tests for query() tool function."""

    async def test_no_results(self) -> None:
        app = _make_app(
            schema_text="schema",
            translate_result="SELECT * FROM customers WHERE id = 999",
            execute_result=[],
        )
        ctx = _make_ctx(app)
        result = await query("find customer 999", ctx)
        assert "No results." in result
        assert "SQL:" in result

    async def test_with_results(self) -> None:
        app = _make_app(
            schema_text="schema",
            translate_result="SELECT id, name FROM customers",
            execute_result=[
                {"id": 1, "name": "Hans"},
                {"id": 2, "name": "Anna"},
            ],
        )
        ctx = _make_ctx(app)
        result = await query("list customers", ctx)
        assert "SQL:" in result
        assert "SELECT id, name FROM customers" in result
        assert "Hans" in result
        assert "Anna" in result

    async def test_calls_translator_with_schema(self) -> None:
        app = _make_app(schema_text="my_schema", translate_result="SELECT 1")
        ctx = _make_ctx(app)
        await query("test question", ctx)
        app.translator.translate.assert_called_once_with("test question", "my_schema")

    async def test_validates_generated_sql(self) -> None:
        app = _make_app(
            schema_text="schema",
            translate_result="DROP TABLE customers",
        )
        ctx = _make_ctx(app)
        with pytest.raises(ValueError, match="Forbidden keyword"):
            await query("delete everything", ctx)


# ── execute_sql tool ─────────────────────────────────────────────────────────


class TestExecuteSqlTool:
    """Tests for execute_sql() tool function."""

    async def test_no_results(self) -> None:
        app = _make_app(execute_result=[])
        ctx = _make_ctx(app)
        result = await execute_sql("SELECT * FROM customers WHERE 1=0", ctx)
        assert result == "No results."

    async def test_with_results(self) -> None:
        app = _make_app(execute_result=[{"id": 1, "email": "test@x.de"}])
        ctx = _make_ctx(app)
        result = await execute_sql("SELECT id, email FROM customers LIMIT 1", ctx)
        assert "id" in result
        assert "email" in result
        assert "test@x.de" in result

    async def test_passes_timeout(self) -> None:
        app = _make_app(execute_result=[])
        ctx = _make_ctx(app)
        await execute_sql("SELECT 1", ctx)
        app.db.execute_sql.assert_called_once()


# ── get_sample_data tool ─────────────────────────────────────────────────────


class TestGetSampleDataTool:
    """Tests for get_sample_data() tool function."""

    async def test_empty_table(self) -> None:
        app = _make_app(sample_data=[])
        ctx = _make_ctx(app)
        result = await get_sample_data("customers", ctx)
        assert result == "No data in table."

    async def test_with_data(self) -> None:
        app = _make_app(sample_data=[{"id": 1, "city": "Berlin"}])
        ctx = _make_ctx(app)
        result = await get_sample_data("customers", ctx)
        assert "Berlin" in result
        assert "id" in result

    async def test_caps_limit(self) -> None:
        app = _make_app(sample_data=[])
        ctx = _make_ctx(app)
        await get_sample_data("customers", ctx, limit=9999)
        call_args = app.db.get_sample_data.call_args
        assert call_args[0][1] <= 100  # settings.max_rows


# ── Resources ────────────────────────────────────────────────────────────────


class TestSchemaResource:
    """Tests for schema_resource()."""

    async def test_returns_schema(self) -> None:
        app = _make_app(schema_text="Table: customers\n  id: int")
        with patch("mcp_db_explorer.server._app_context", app):
            result = await schema_resource()
        assert "Table: customers" in result

    async def test_raises_when_not_initialized(self) -> None:
        with (
            patch("mcp_db_explorer.server._app_context", None),
            pytest.raises(RuntimeError, match="Server not initialized"),
        ):
            await schema_resource()


class TestTableResource:
    """Tests for table_resource()."""

    async def test_returns_table_schema(self) -> None:
        app = _make_app(table_schema_text="Table: orders\n  Columns:\n    - id: integer")
        with patch("mcp_db_explorer.server._app_context", app):
            result = await table_resource("orders")
        assert "Table: orders" in result
        app.db.get_table_schema_text.assert_called_once_with("orders")


# ── Prompts ──────────────────────────────────────────────────────────────────


class TestQueryToolOverflow:
    """Tests for query() tool when results exceed max_rows."""

    async def test_truncates_at_max_rows(self) -> None:
        # Generate more rows than max_rows (100)
        many_rows = [{"id": i, "val": f"row_{i}"} for i in range(150)]
        app = _make_app(
            schema_text="schema",
            translate_result="SELECT id, val FROM big_table",
            execute_result=many_rows,
        )
        ctx = _make_ctx(app)
        result = await query("get everything", ctx)
        assert "150 total rows" in result
        assert "showing first 100" in result


class TestMainEntryPoint:
    """Tests for main() entry point."""

    def test_main_calls_mcp_run(self) -> None:
        from mcp_db_explorer.server import main

        with patch("mcp_db_explorer.server.mcp") as mock_mcp:
            main()
            mock_mcp.run.assert_called_once()


class TestPrompts:
    """Tests for prompt functions."""

    def test_analyze_data_includes_topic(self) -> None:
        result = analyze_data("sales trends")
        assert "sales trends" in result
        assert "list_tables" in result
        assert "describe_table" in result

    def test_generate_report_includes_metric(self) -> None:
        result = generate_report("monthly revenue")
        assert "monthly revenue" in result
        assert "get_sample_data" in result

    def test_analyze_data_has_steps(self) -> None:
        result = analyze_data("test")
        assert "1." in result
        assert "2." in result
        assert "3." in result
        assert "4." in result

    def test_generate_report_has_steps(self) -> None:
        result = generate_report("test")
        assert "1." in result
        assert "2." in result
        assert "3." in result
        assert "4." in result
