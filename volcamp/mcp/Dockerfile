# Public MCP server over orders.csv (DuckDB). Build from the repo root:
#
#   docker build -f volcamp/mcp/Dockerfile -t volcamp-mcp .
#   docker run --rm -p 7432:7432 volcamp-mcp
#
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock README.md ./
COPY volcamp ./volcamp
RUN uv sync --frozen --no-dev


ENV HOST=0.0.0.0 PORT=7432
EXPOSE 7432
CMD ["uv", "run", "--no-sync", "python", "-m", "volcamp.mcp"]
