"""One shared MCP client session, connecting to the single MCP server
(mcp_server/server.py) over stdio. Every LangGraph node in a given graph run
calls tools through the same session rather than each opening its own.
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@asynccontextmanager
async def mcp_session():
    # env is passed through explicitly: the SDK otherwise gives the child only a minimal
    # allow-list, which would drop TWIN_SERVICE_URL / DIAGNOSTICS_DB_PATH / COHERE_API_KEY.
    # Run as `-m mcp_server.server` (not a bare script path) so the subprocess's
    # sys.path includes the repo root and `mcp_server.tools.*` imports resolve.
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(_REPO_ROOT), env={**os.environ})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
