"""Tests for translator module: extract_sql, build_user_prompt, Translator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from anthropic.types import TextBlock, ToolUseBlock

from mcp_db_explorer.translator import (
    SYSTEM_PROMPT,
    Translator,
    build_user_prompt,
    extract_sql,
)

# ── extract_sql ──────────────────────────────────────────────────────────────


class TestExtractSql:
    """Tests for extract_sql()."""

    def test_plain_sql(self) -> None:
        assert extract_sql("SELECT * FROM customers") == "SELECT * FROM customers"

    def test_strips_code_fences(self) -> None:
        text = "```sql\nSELECT * FROM customers\n```"
        assert extract_sql(text) == "SELECT * FROM customers"

    def test_strips_generic_fences(self) -> None:
        text = "```\nSELECT 1\n```"
        assert extract_sql(text) == "SELECT 1"

    def test_strips_whitespace(self) -> None:
        assert extract_sql("  SELECT 1  ") == "SELECT 1"

    def test_code_fence_with_surrounding_text(self) -> None:
        text = "Here is the query:\n```sql\nSELECT id FROM orders\n```\nDone."
        assert extract_sql(text) == "SELECT id FROM orders"

    def test_multiline_sql_in_fences(self) -> None:
        text = "```sql\nSELECT\n  id,\n  name\nFROM customers\n```"
        assert extract_sql(text) == "SELECT\n  id,\n  name\nFROM customers"

    def test_empty_string(self) -> None:
        assert extract_sql("") == ""


# ── build_user_prompt ────────────────────────────────────────────────────────


class TestBuildUserPrompt:
    """Tests for build_user_prompt()."""

    def test_includes_schema(self) -> None:
        result = build_user_prompt("How many customers?", "Table: customers\n  id: int")
        assert "Table: customers" in result

    def test_includes_question(self) -> None:
        result = build_user_prompt("How many customers?", "schema text")
        assert "How many customers?" in result

    def test_format_structure(self) -> None:
        result = build_user_prompt("Q?", "S")
        assert result.startswith("Database schema:")
        assert "Question: Q?" in result

    def test_schema_before_question(self) -> None:
        result = build_user_prompt("Q?", "SCHEMA_BLOCK")
        schema_pos = result.index("SCHEMA_BLOCK")
        question_pos = result.index("Q?")
        assert schema_pos < question_pos


# ── Translator ───────────────────────────────────────────────────────────────


class TestTranslator:
    """Tests for Translator.translate()."""

    async def test_calls_anthropic(
        self, translator: Translator, mock_anthropic_client: AsyncMock
    ) -> None:
        result = await translator.translate("How many?", "schema")
        assert result == "SELECT * FROM customers"
        mock_anthropic_client.messages.create.assert_called_once()

    async def test_uses_system_prompt(
        self, translator: Translator, mock_anthropic_client: AsyncMock
    ) -> None:
        await translator.translate("Test?", "schema")
        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == SYSTEM_PROMPT

    async def test_uses_configured_model(
        self, translator: Translator, mock_anthropic_client: AsyncMock
    ) -> None:
        await translator.translate("Test?", "schema")
        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "test-model"

    async def test_passes_max_tokens(
        self, translator: Translator, mock_anthropic_client: AsyncMock
    ) -> None:
        await translator.translate("Test?", "schema")
        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1024

    async def test_passes_user_message(
        self, translator: Translator, mock_anthropic_client: AsyncMock
    ) -> None:
        await translator.translate("How many orders?", "my_schema")
        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "How many orders?" in messages[0]["content"]
        assert "my_schema" in messages[0]["content"]

    async def test_strips_code_fences_from_response(self) -> None:
        client = AsyncMock()
        content_block = TextBlock(type="text", text="```sql\nSELECT count(*) FROM orders\n```")
        response = MagicMock()
        response.content = [content_block]
        client.messages.create = AsyncMock(return_value=response)

        translator = Translator(client=client, model="test")
        result = await translator.translate("count orders", "schema")
        assert result == "SELECT count(*) FROM orders"

    async def test_raises_on_non_text_block(self) -> None:
        client = AsyncMock()
        tool_block = ToolUseBlock(type="tool_use", id="t1", name="test", input={})
        response = MagicMock()
        response.content = [tool_block]
        client.messages.create = AsyncMock(return_value=response)

        translator = Translator(client=client, model="test")
        with pytest.raises(ValueError, match="Expected TextBlock"):
            await translator.translate("test", "schema")
