# volcamp/mcp

A public streamable-HTTP MCP server, written with the MCP Python SDK v2
(`mcp>=2`, `MCPServer`), that serves `volcamp/mcp/orders.csv` through DuckDB.

At startup the CSV is loaded into a DuckDB file, which is then reopened
read-only with `enable_external_access = false` and a locked configuration.
Clients can query the data but cannot drop it, write files, or read other
files on the host.

## Tools

| Tool             | Arguments                        | Returns                                                     |
| ---------------- | -------------------------------- | ----------------------------------------------------------- |
| `get_table_info` | `table` (default `orders`)    | columns and types, row count, 5 sample rows                 |
| `execute_sql`    | `sql`, `limit` (default 100, no cap)   | `columns`, `rows`, `row_count`, `truncated`, or `error` |

Both return JSON strings.

## Run locally

```bash
uv sync                                   # installs duckdb + mcp
uv run python -m volcamp.mcp              # http://0.0.0.0:7432/mcp
```

Environment variables: `HOST` (default `0.0.0.0`), `PORT` (default `7432`),
`ORDERS_CSV` (default `volcamp/mcp/orders.csv`, next to `server.py`).

The transport is stateless streamable HTTP with JSON responses, so it works
behind any proxy or serverless platform without sticky sessions.

## Make it public

Any tunnel or host works since there is no auth and no session affinity:

```bash
ngrok http 7432            # then use https://<id>.ngrok-free.app/mcp
```

Or as a container, from the repo root:

```bash
docker build -f volcamp/mcp/Dockerfile -t volcamp-mcp .
docker run --rm -p 7432:7432 volcamp-mcp
```

## Use it from the workshop agents

```python
mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "https://<your-host>/mcp"}}}
async with MCPAdapter(mcp_config) as adapter:
    tools = await adapter.list_tools()   # execute_sql, get_table_info
```
