"""Run the LangGraph diagnostic pipeline once for an asset (needs COHERE_API_KEY).

    python scratch_run_graph.py [asset_id]     # default: ICE-KIA-SPORTAGE
"""
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from agents.graph.graph import run_diagnostic_pipeline
from agents.graph.mcp_client import mcp_session


async def main(asset_id: str):
    async with mcp_session() as session:
        result = await run_diagnostic_pipeline(session, asset_id)
        print("outcome:", result.get("outcome"))
        print("issue:", result.get("issue"))
        print("self_heal_action:", result.get("self_heal_action"))
        print("self_heal_effective:", result.get("self_heal_effective"))
        print("tool_calls:")
        for tc in result.get("tool_calls", []):
            print(" -", tc["node"], tc["tool"], tc["args"])


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "ICE-KIA-SPORTAGE"))
