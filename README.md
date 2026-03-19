# MCP DB Explorer

[![CI](https://github.com/yasunchukandriy/mcp-db-explore/actions/workflows/ci.yml/badge.svg)](https://github.com/yasunchukandriy/mcp-db-explore/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Model Context Protocol (MCP) server that lets you explore a PostgreSQL database using natural language. Ask a question in English or German, and Claude translates it to SQL, executes it safely, and returns the results.

## Quick Start

```bash
# Clone and start services
git clone https://github.com/yasunchukandriy/mcp-db-explorer.git
cd mcp-db-explorer
cp .env.example .env
# Edit .env with your Anthropic API key

docker compose up -d
```

## Claude Desktop Configuration

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "db-explorer": {
      "command": "docker",
      "args": ["compose", "run", "--rm", "-i", "mcp-server"],
      "cwd": "/path/to/mcp-db-explorer"
    }
  }
}
```

Or run directly with Python:

```json
{
  "mcpServers": {
    "db-explorer": {
      "command": "mcp-db-explorer",
      "env": {
        "MCP_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/explorer",
        "MCP_ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables with approximate row counts |
| `describe_table` | Show columns, constraints, and indexes for a table |
| `query` | Ask a natural language question — translated to SQL automatically |
| `execute_sql` | Run a raw SELECT query directly |
| `get_sample_data` | Preview sample rows from a table |

## Resources

| URI | Description |
|-----|-------------|
| `db://schema` | Full database schema as text |
| `db://tables/{table_name}` | Schema for a specific table |

## Prompts

| Prompt | Description |
|--------|-------------|
| `analyze_data` | Data analysis workflow template |
| `generate_report` | Report generation template |

## Architecture

```
Natural Language Question
        │
        ▼
  ┌─────────────┐     ┌──────────────┐     ┌────────────┐
  │  MCP Server  │────▶│  Translator  │────▶│ Claude API │
  │  (FastMCP)   │◀────│  (asyncio)   │◀────│            │
  └──────┬───────┘     └──────────────┘     └────────────┘
         │
         ▼
  ┌──────────────┐
  │  Database    │
  │  Manager     │──▶ PostgreSQL
  │  (asyncpg)   │
  └──────────────┘
```

## Safety

- Only `SELECT`, `EXPLAIN`, and `WITH` queries are allowed
- DML/DDL keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.) are blocked
- Multiple statements (`;`) are rejected
- Table names are validated against SQL injection
- Query timeout prevents long-running queries
- Row limits cap result sizes

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/

# Start PostgreSQL for integration tests
docker compose up -d postgres
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/explorer` | PostgreSQL connection string |
| `MCP_ANTHROPIC_API_KEY` | | Anthropic API key |
| `MCP_ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model to use |
| `MCP_QUERY_TIMEOUT_SECONDS` | `10` | Query execution timeout |
| `MCP_MAX_ROWS` | `100` | Maximum rows returned per query |

## License

MIT
