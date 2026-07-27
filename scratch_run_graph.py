import asyncio
from dotenv import load_dotenv
load_dotenv()

from agents.graph.mcp_client import mcp_session
from agents.graph.graph import run_diagnostic_pipeline


async def main():
    async with mcp_session() as session:
        result = await run_diagnostic_pipeline(session, "ev-1")
        print("outcome:", result.get("outcome"))
        print("issue:", result.get("issue"))
        print("self_heal_action:", result.get("self_heal_action"))
        print("self_heal_effective:", result.get("self_heal_effective"))
        print("tool_calls:")
        for tc in result.get("tool_calls", []):
            print(" -", tc["node"], tc["tool"], tc["args"])


asyncio.run(main())
