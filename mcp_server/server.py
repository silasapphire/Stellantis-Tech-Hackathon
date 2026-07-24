from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_server.tools import actions, diagnostics, knowledge_base, telemetry, twin  # noqa: E402

mcp = FastMCP("diagnostics-platform")

telemetry.register(mcp)  # telemetry_* tools
twin.register(mcp)  # twin_* tools
diagnostics.register(mcp)  # diagnostics_* tools
actions.register(mcp)  # actions_* tools
knowledge_base.register(mcp)  # kb_* tools

if __name__ == "__main__":
    mcp.run()
