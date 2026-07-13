#!/usr/bin/env python3
"""Zen Agent — Unified launcher (CLI or Web)."""
from __future__ import annotations

import os
import sys

REQUIRED_KEYS = {
    "OPENGATE_API_KEY": "OpenCode/OpenAI API key",
    "COMPOSIO_API_KEY": "Composio API key",
}


def main():
    for key, desc in REQUIRED_KEYS.items():
        if not os.environ.get(key):
            print(f"Warning: {key} ({desc}) not set.", file=sys.stderr)

    mode = sys.argv[1] if len(sys.argv) > 1 else "web"
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if mode in ("cli", "chat"):
        from cli.main import app as typer_app
        typer_app()
    elif mode in ("web", "server"):
        import uvicorn
        from config import config
        print(f"Zen Agent — http://localhost:{config.port}")
        uvicorn.run(
            "server.main:app",
            host=config.host,
            port=config.port,
            log_level=config.log_level,
            ws_ping_interval=30,
            ws_ping_timeout=10,
        )
    else:
        print(f"Usage: {sys.argv[0]} [web|cli] [args]")
        sys.exit(1)


if __name__ == "__main__":
    main()
