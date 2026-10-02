# deepagents + OpenSandbox workshop

Build an agent that queries sales data, manages large tool results, runs code
inside a container, uses a reusable skill, and produces a presentation.

Twelve pages progress from a minimal agent to a final two-slide sales deck.
Page 8 introduces the OpenSandbox SDK without an agent; page 9 implements the
backend imported by pages 10–12. Each exercise includes a goal, success criteria
and a short challenge. Complete the `# TODO` comments or use the matching solution.

| Folder | Contents |
| --- | --- |
| `exercices/` | Fill-in-the-blanks versions, success criteria and challenges |
| `solutions/` | Complete scripts |
| `volcamp/` | Output helpers and the orders MCP server |
| `skills/` | Skills uploaded into the sandbox on page 11 |
| `tests/` | Offline checks for live progress and the reference sales answers |

## Before the workshop

You should be comfortable with Python functions, imports, dictionaries and basic
SQL. Pages 3 onward use `async` / `await`; page 9 also uses inheritance. Bring
Python 3.11+, uv, Docker with a running daemon, and a funded DeepSeek API key.
Internet access is needed for model calls, image pulls and the final exercise's
`python-pptx` installation.

Allow roughly **2.5–3 hours**, including setup and discussion; this is a planning
estimate, not a measured runtime. For a shorter session, demonstrate page 9 and
let participants copy `solutions/09_opensandbox_backend.py` into `exercices/`.
The challenges are optional extensions.

```bash
uv sync --frozen
# Create .env (do not commit it) with:
#   DEEPSEEK_API_KEY=your-key
#   OPEN_SANDBOX_DOMAIN=http://localhost:7431
docker compose up --build -d
# Pull the sandbox image before the session rather than during page 8.
docker pull python:3.12-slim
```

Pages 3–7 and 12 use the MCP server at `http://localhost:7432/mcp`. It serves the
checked-in `volcamp/mcp/orders.csv` (100,000 rows) through DuckDB. Pages 8–12 need
the OpenSandbox server; the SDK reads its address from `OPEN_SANDBOX_DOMAIN` in `.env`
(`http://localhost:7431` with the Compose setup), so run those pages with `--env-file .env`.

Run these smoke checks before starting the exercises:

```bash
# Credentials and model access
uv run --env-file .env python solutions/01_react_agent.py
# MCP discovery, SQL and model tool calls
uv run --env-file .env python solutions/03_react_agent_with_mcp.py
# Sandbox creation, execution, upload, download and cleanup; no model needed
uv run --env-file .env python solutions/08_opensandbox_hello.py
```

Page 8 intentionally runs `import nope`: that command should fail, and the script
should then download a sample and destroy the sandbox. If a service is not ready,
check `docker compose ps` and `docker compose logs --tail=100`, then retry the
smoke check. A model authentication/rate-limit error is separate from a Docker or
MCP connection failure. Save a successful terminal trace before the session as
a fallback for participants who encounter network problems.

## Workshop route

Run the pages in numeric order. The final presentation follows the smaller
execution and skills exercises so participants first learn each part separately.

| Page | Lesson | Evidence of success |
| --- | --- | --- |
| 1 | Minimal agent | A final AI greeting |
| 2 | Python tools | An actual `add(1, 10)` call returns 11 |
| 3 | MCP / SQL | Paris has the highest total: **13,986,204.84** |
| 4 | Conversation memory | Same thread recalls the question; a new thread does not |
| 5 | Oversized tool result | Full-table result is visible in the trace; a context rejection may follow |
| 6 | Offloading / selective retrieval | A file reference and targeted lookup find order 99999 |
| 7 | Deep-agent harness | Same lookup; compare model calls, elapsed time and token usage |
| 8 | Sandbox SDK | 1,001 CSV lines including header; sample downloaded; container destroyed |
| 9 | Backend adapter | Page 10 can execute through the completed backend |
| 10 | Compute near the data | Code processes 50,000 rows, returning only a small summary |
| 11 | Reusable skills | Agent reads `csv-report`, runs its script and produces the expected report |
| 12 | Final presentation | A downloaded, readable two-slide deck with a native chart and verified numbers |

Pages 5–7 deliberately request all rows **before looking up one order**. In a
real application, use `WHERE id = 99999`. This artificial restriction isolates
the context-management lesson:

- A raw tool result can exceed a model's context window; page 5's outcome depends
  on the model and its limits. Only a confirmed context rejection demonstrates
  this failure. Other errors retain their traceback and a failing exit status.
- Offloading lets the model search a large result and read just the relevant
  part. It does not make exhaustive reading or mental arithmetic reliable.
- Compute totals in SQL (as on pages 3 and 12), or run code over files in the
  sandbox (page 10). More agent tools do not automatically improve a simple task.

Reference answers from the checked-in CSV:

- Order **99999**: **2025-01-21, Lyon, webcam, 47.24**.
- Row count: **100,000**; overall sales: **32,898,506.88**.
- Highest-sales city: **Paris**, totaling **13,986,204.84**.

The generated country CSVs on pages 8, 10 and 11 are separate datasets. A fixed
seed in a model-written generator does not guarantee identical data unless the
generation algorithm is also identical; verify their results by running code.

## Running a page

```bash
uv run --env-file .env python exercices/01_react_agent.py
uv run --env-file .env python solutions/01_react_agent.py
```

Every agent invocation prints live model/tool start and completion events, with
short tool arguments. It ends with elapsed time, call counts and provider-reported
token totals, including when the invocation fails. Missing usage is identified
explicitly. These events work with both `invoke` and `ainvoke`:

```python
from volcamp.progress import LiveProgress

with LiveProgress() as progress:
    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Your task"}]},
        config={"callbacks": [progress]},
    )
```

After a successful invocation, `print_messages(response)` prints the detailed
conversation: prompt, tool calls, results and final answer. Character counts and
approximate token counts describe the displayed message; they are not substitutes
for provider usage. Offloaded results appear as a reference/preview, not the
original full payload.

```python
from volcamp.pretty import print_messages

print_messages(response)
print_messages(response, max_chars=300)       # clip long results in the terminal
print_messages(response, show_reasoning=True) # show provider reasoning if present
print_messages(response, skip=n)              # skip earlier turns in a saved thread
```

Clipping printed output does not reduce the model's context. On page 4 each
invocation gets a fresh progress counter while retaining the same thread id.

## Checks and cleanup

```bash
# No API key, network or Docker required
uv run --frozen python -m unittest discover -s tests -v

# After the workshop
docker compose down
```

The sandbox examples destroy their containers in `finally` blocks. If a process
is forcibly stopped, its sandbox may remain until the lifetime timeout.
Page 12 downloads `sales_analysis.pptx` into the repository root. Open it and
verify both slides, chart labels and numbers against the SQL trace; existence
alone is not an artifact-quality check.
