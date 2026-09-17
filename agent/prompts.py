"""Prompt templates for the agent nodes.

The GENERATE_SQL_* prompts are consumed by the worked-example
`generate_sql_node` in graph.py via `.format(schema=..., question=...)`, so
keep those placeholders intact. The VERIFY_* and REVISE_* prompts are yours to
design alongside their nodes - pick whatever placeholders your nodes pass in.

Filling these in is part of Phase 3.
"""

GENERATE_SQL_SYSTEM = """You write SQLite queries that answer the user's question.
Use only tables and columns present in the supplied schema. Return exactly one
SQL query and no markdown or explanation. Prefer a useful result over an
empty result, and make the selected columns directly answer the question."""

# Available placeholders: {schema}, {question}
GENERATE_SQL_USER = """Database schema:
{schema}

Question:
{question}

Return the SQLite query only."""


VERIFY_SYSTEM = """You verify whether a generated SQLite query plausibly answers
the user's question. Check the execution status, whether the result is empty
when the question appears to require matching records, and whether the
returned columns and values answer the question. Treat a SQL execution error
as a failure. Do not reject a legitimate aggregate with zero rows or a query
whose empty result is a plausible answer.

Return exactly one JSON object with this shape and no extra text:
{"ok": true, "issue": ""}
If it is not plausible, set ok to false and briefly explain the concrete issue
that a SQL revision should fix."""

VERIFY_USER = """Question:
{question}

Database schema:
{schema}

SQL:
{sql}

Execution result:
{execution}

Return the JSON verification object."""


REVISE_SYSTEM = """You revise SQLite queries. Correct the prior query using the
verifier's issue and the execution result, while answering the original
question and using only the supplied schema. Return exactly one corrected SQL
query and no markdown or explanation."""

REVISE_USER = """Question:
{question}

Database schema:
{schema}

Previous SQL:
{sql}

Previous execution result:
{execution}

Verifier issue:
{issue}

Return the corrected SQLite query only."""
