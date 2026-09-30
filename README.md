# deepagents + OpenSandbox workshop

Twelve pages, from a one-line react agent to a deep agent running skills inside
a container. Page 8 uses the OpenSandbox SDK on its own, without any agent, and
page 9 is the backend module that pages 10 to 12 import.

| Folder       | Contents                                                              |
| ------------ | --------------------------------------------------------------------- |
| `exercices/` | Fill-in-the-blanks versions. Look for the `# TODO` comments.          |
| `solutions/` | The complete scripts.                                                 |
| `volcamp/`   | `pretty.py`, a rich-based printer, and `mcp/`, the orders MCP server. |
| `skills/`    | The skills library uploaded into the sandbox on page 12.              |

## Setup

```bash
uv sync
echo "DEEPSEEK_API_KEY=..." > .env
```

Pages 3 to 7 and 10 use the workshop's own MCP server, `volcamp/mcp`, which
serves `volcamp/mcp/orders.csv` (100 000 rows, checked in)
through DuckDB. Pages 8 to 12 need the OpenSandbox server. Both run with docker
compose:

```bash
docker compose up --build -d     # OpenSandbox on :7431, MCP on :7432/mcp
docker compose logs -f
docker compose down
```

## Running a page

```bash
uv run --env-file .env python exercices/01_react_agent.py
uv run --env-file .env python solutions/01_react_agent.py
```

## Reading the output

Every script ends with `print_messages(response)`, which prints one panel per
message: the prompt, each tool call with its arguments, each tool result with
its size in characters and tokens, and the final answer.

```python
from volcamp.pretty import print_messages

print_messages(response)                      # the dict returned by agent.invoke
print_messages(response, max_chars=300)       # truncate long tool results
print_messages(response, show_reasoning=True) # DeepSeek's reasoning blocks
print_messages(response, skip=n)              # multi-turn: skip already printed messages
```
