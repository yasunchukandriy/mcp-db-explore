"""Shared test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from anthropic.types import TextBlock

from mcp_db_explorer.database import DatabaseManager
from mcp_db_explorer.translator import Translator


@pytest.fixture
def mock_pool() -> AsyncMock:
    """Create a mock asyncpg pool."""
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    return pool


@pytest.fixture
def db(mock_pool: AsyncMock) -> DatabaseManager:
    """Create a DatabaseManager with a mock pool."""
    return DatabaseManager(pool=mock_pool)


@pytest.fixture
def mock_anthropic_client() -> AsyncMock:
    """Create a mock Anthropic client with a pre-configured response."""
    client = AsyncMock()
    content_block = TextBlock(type="text", text="SELECT * FROM customers")
    response = MagicMock()
    response.content = [content_block]
    client.messages.create = AsyncMock(return_value=response)
    return client


@pytest.fixture
def translator(mock_anthropic_client: AsyncMock) -> Translator:
    """Create a Translator with a mock Anthropic client."""
    return Translator(client=mock_anthropic_client, model="test-model")
