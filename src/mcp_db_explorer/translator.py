"""Natural language to SQL translation using Claude API."""

from __future__ import annotations

import re
from dataclasses import dataclass

from anthropic import AsyncAnthropic
from anthropic.types import TextBlock

SYSTEM_PROMPT = """\
You are a PostgreSQL SQL expert. Given a database schema and a natural language question, \
generate a single SELECT query that answers the question.

Rules:
- Output ONLY the SQL query, no explanations or markdown
- Only SELECT queries are allowed — never INSERT, UPDATE, DELETE, or DDL
- Use proper JOIN syntax, not implicit joins
- Use table and column aliases for readability
- Limit results to 100 rows unless the question specifies otherwise\
"""

_CODE_FENCE = re.compile(r"```(?:sql)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def build_user_prompt(question: str, schema: str) -> str:
    """Build the user prompt combining schema context and question."""
    return f"Database schema:\n\n{schema}\n\nQuestion: {question}"


def extract_sql(text: str) -> str:
    """Extract SQL from Claude's response, stripping code fences if present."""
    match = _CODE_FENCE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


@dataclass
class Translator:
    """Translates natural language questions to SQL using Claude."""

    client: AsyncAnthropic
    model: str

    async def translate(self, question: str, schema: str) -> str:
        """Translate a natural language question to a SQL query."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_prompt(question, schema)},
            ],
        )
        block = response.content[0]
        if not isinstance(block, TextBlock):
            raise ValueError(f"Expected TextBlock, got {type(block).__name__}")
        return extract_sql(block.text)
