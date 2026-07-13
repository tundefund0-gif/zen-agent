# Zen Agent

AI agent with **23,790+ tools** via Composio, powered by OpenCode AI.

## Features

- **AI Agent** — Streaming chat with reasoning, tool calling, and code execution
- **23,790+ Tools** — GitHub, Gmail, Slack, Notion, Google Sheets, Linear, Jira, and more
- **Web Dashboard** — Beautiful chat UI with dark/light theme, mobile responsive
- **CLI Mode** — Interactive terminal chat with streaming support
- **REST API + WebSocket** — Full API for programmatic access
- **Code Sandbox** — Execute Python code remotely via Composio
- **Multi-turn Tool Calls** — Automatic tool call loops with retry

## Quick Start

### Prerequisites
- Python 3.10+
- OpenCode API key
- Composio API key

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Set API Keys
```bash
export OPENGATE_API_KEY="your-key"
export COMPOSIO_API_KEY="your-composio-key"
# Or copy .env.example to .env
cp .env.example .env
```

### 3. Run Web Dashboard
```bash
./start.sh
# OR: python3 -m uvicorn server.main:app
# Open http://localhost:8000
```

### 4. Run CLI
```bash
# Interactive
python3 -m cli.main

# Streaming mode
python3 -m cli.main --stream

# One-shot
python3 -m cli.main --oneshot "What can you do?"
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/chat` | POST | Send a message |
| `/api/session/{user_id}` | GET | Get session info |
| `/api/session/{user_id}/reset` | POST | Reset conversation |
| `/api/tools/list` | GET | List Composio tools |
| `/api/tools/search` | GET | Search tools |
| `/ws/chat/{user_id}` | WS | Streaming chat |
| `/` | GET | Dashboard UI |

## Testing

```bash
# Run all tests
python3 -m pytest tests/ -v

# Stress test
python3 tests/stress_test.py
```

## Project Structure

```
zen-agent/
├── core/                  # Core engine
│   ├── agent.py           # AI agent orchestration (multi-turn tool calls)
│   ├── llm_client.py      # OpenCode API client (retry, pooling)
│   └── composio_client.py # Composio REST API wrapper (retry, pooling)
├── cli/main.py            # Typer-based CLI with streaming
├── server/main.py         # FastAPI app (REST + WebSocket)
├── server/static/         # Dashboard (single-file SPA)
├── tests/                 # Test suite
├── .github/workflows/     # CI/CD
├── config.py              # Environment-based configuration
├── Dockerfile             # Container build
├── start.sh               # Launcher
└── run.py                 # Unified launcher
```

## Configuration

All via environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `OPENGATE_API_KEY` | — | OpenCode API key |
| `OPENGATE_BASE_URL` | https://opencode.ai/zen/v1 | API endpoint |
| `OPENGATE_MODEL` | deepseek-v4-flash-free | Model name |
| `OPENGATE_MAX_TOKENS` | 131000 | Max tokens |
| `OPENGATE_TIMEOUT` | 180 | HTTP timeout (s) |
| `COMPOSIO_API_KEY` | — | Composio API key |
| `COMPOSIO_BASE_URL` | https://backend.composio.dev | Composio endpoint |
| `COMPOSIO_TIMEOUT` | 60 | HTTP timeout (s) |
| `HOST` | 0.0.0.0 | Server host |
| `PORT` | 8000 | Server port |
| `LOG_LEVEL` | info | Logging level |
| `MAX_TOOL_ROUNDS` | 10 | Max tool call iterations |
| `MAX_HISTORY` | 100 | Max conversation pairs |
| `ENABLE_SANDBOX` | true | Enable code sandbox |

## Docker

```bash
docker build -t zen-agent .
docker run -e OPENGATE_API_KEY=xxx -e COMPOSIO_API_KEY=xxx -p 8000:8000 zen-agent
```
