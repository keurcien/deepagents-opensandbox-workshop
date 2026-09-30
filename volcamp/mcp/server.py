"""Public HTTP MCP server (MCP Python SDK v2) over orders.csv, backed by DuckDB.

At startup the CSV is loaded once into a DuckDB database that is then reopened
read-only with external file access disabled, so `execute_sql` can only read
the `orders` table: no DROP, no COPY TO, no read_csv('/etc/passwd').

Tools:
    execute_sql(sql, limit=100)      run a read-only DuckDB query, rows as JSON (no cap on limit)
    get_table_info(table="orders") columns, types, row count, sample rows

Run (binds to 0.0.0.0, no auth, stateless streamable HTTP at /mcp):
    uv run python -m volcamp.mcp
    ORDERS_CSV=/path/to/orders.csv PORT=7432 uv run python -m volcamp.mcp

Expose it publicly with e.g. `ngrok http 7432`, then point a client at
https://<your-host>/mcp.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
import duckdb
from mcp.server.mcpserver import Context, MCPServer

HERE = Path(__file__).resolve().parent
CSV_PATH = Path(os.getenv("ORDERS_CSV", HERE / "orders.csv"))
TABLE = "orders"


@dataclass
class AppState:
    db: duckdb.DuckDBPyConnection


def build_database(csv_path: Path, db_path: Path) -> None:
    """Load the CSV into a fresh DuckDB file (one table named `orders`)."""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Point ORDERS_CSV at an existing CSV."
        )
    if db_path.exists():
        db_path.unlink()
    with duckdb.connect(str(db_path)) as db:
        db.execute(f"CREATE TABLE {TABLE} AS SELECT * FROM read_csv_auto(?)", [str(csv_path)])
        (count,) = db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()
    print(f"Loaded {count:,} rows from {csv_path} into {db_path}", flush=True)


def open_readonly(db_path: Path) -> duckdb.DuckDBPyConnection:
    db = duckdb.connect(str(db_path), read_only=True)
    db.execute("SET enable_external_access = false")
    db.execute("SET lock_configuration = true")
    return db


@asynccontextmanager
async def lifespan(_: MCPServer) -> AsyncIterator[AppState]:
    tmpdir = tempfile.mkdtemp(prefix="volcamp_mcp_")
    db_path = Path(tmpdir) / f"{TABLE}.duckdb"
    await anyio.to_thread.run_sync(build_database, CSV_PATH, db_path)
    db = open_readonly(db_path)
    try:
        yield AppState(db=db)
    finally:
        db.close()


mcp = MCPServer(
    name="volcamp_mcp",
    instructions=(
        f"SQL access to a DuckDB table named `{TABLE}` (100 000 sales rows: id, date, city, "
        "product, amount). Call get_table_info first, then execute_sql with DuckDB SQL. "
        "The database is read-only."
    ),
    lifespan=lifespan,
)


def _state(ctx: Context) -> AppState:
    return ctx.request_context.lifespan_context


def _run_query(db: duckdb.DuckDBPyConnection, sql: str, limit: int) -> dict[str, Any]:
    # A cursor is a per-call connection: safe to use from any thread.
    cur = db.cursor()
    try:
        result = cur.execute(sql)
        columns = [name for name, *_ in result.description] if result.description else []
        rows = result.fetchmany(limit + 1) if columns else []
    finally:
        cur.close()
    truncated = len(rows) > limit
    rows = rows[:limit]
    return {
        "columns": columns,
        "row_count": len(rows),
        "truncated": truncated,
        "rows": [list(row) for row in rows],
    }


def _dump_result(payload: dict[str, Any]) -> str:
    """JSON with one row per line, so a large result can be read back in line chunks."""
    head = {key: value for key, value in payload.items() if key != "rows"}
    lines = [json.dumps(row, default=str) for row in payload["rows"]]
    return json.dumps(head, default=str)[:-1] + ', "rows": [\n' + ",\n".join(lines) + "\n]}"


@mcp.tool()
async def execute_sql(sql: str, ctx: Context, limit: int = 100) -> str:
    """Run a read-only DuckDB SQL query against the `orders` table.

    Returns JSON with `columns`, `rows` (at most `limit` rows, default 100; there is no
    upper bound, so limit=100000 returns the whole table) and `truncated` (true when more
    rows were available). Prefer aggregations (GROUP BY, count, sum, avg) over raw rows.
    """
    limit = max(1, int(limit))
    try:
        payload = await anyio.to_thread.run_sync(_run_query, _state(ctx).db, sql, limit)
    except duckdb.Error as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    return _dump_result(payload)


def _table_info(db: duckdb.DuckDBPyConnection, table: str) -> dict[str, Any]:
    cur = db.cursor()
    try:
        tables = [name for (name,) in cur.execute("SELECT table_name FROM information_schema.tables").fetchall()]
        if table not in tables:
            return {"error": f"Unknown table {table!r}. Available tables: {tables}"}
        columns = cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table],
        ).fetchall()
        (row_count,) = cur.execute(f'SELECT count(*) FROM "{table}"').fetchone()
        sample = cur.execute(f'SELECT * FROM "{table}" LIMIT 5').fetchall()
    finally:
        cur.close()
    return {
        "table": table,
        "row_count": row_count,
        "columns": [{"name": name, "type": dtype} for name, dtype in columns],
        "sample_rows": [list(row) for row in sample],
    }


@mcp.tool()
async def get_table_info(ctx: Context, table: str = TABLE) -> str:
    """Describe a table: its columns and DuckDB types, the row count, and 5 sample rows.

    Defaults to `orders`, the only table on this server.
    """
    payload = await anyio.to_thread.run_sync(_table_info, _state(ctx).db, table)
    return json.dumps(payload, default=str)


def main() -> None:
    mcp.run(
        "streamable-http",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "7432")),
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
