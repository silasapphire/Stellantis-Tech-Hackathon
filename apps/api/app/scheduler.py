"""Two independent APScheduler jobs sharing the API process's one long-lived
MCP session:
  - diagnostic sweep: runs the LangGraph diagnostic pipeline per asset (LLM
    reasoning - detect/predict/recommend/self-heal)
  - resolution sweep: a plain (non-LLM) diagnostics_resolve_if_recovered call
    per open issue - a deterministic recurring state check, not worth an
    inference call every tick
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from mcp import ClientSession

from agents.graph.graph import run_diagnostic_pipeline
from agents.graph.mcp_tools import call_mcp_tool
from agents.graph.nodes.sustainability import build_sustainability_node
from common.firestore_client import COLLECTIONS, get_firestore_client
from common.schemas import IssueState

logger = logging.getLogger("scheduler")

DIAGNOSTIC_SWEEP_SECONDS = int(os.environ.get("DIAGNOSTIC_SWEEP_SECONDS", "90"))
RESOLUTION_SWEEP_SECONDS = int(os.environ.get("RESOLUTION_SWEEP_SECONDS", "20"))
SUSTAINABILITY_SWEEP_SECONDS = int(os.environ.get("SUSTAINABILITY_SWEEP_SECONDS", "300"))


def start_scheduler(session: ClientSession) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def diagnostic_sweep() -> None:
        db = get_firestore_client()
        for doc in db.collection(COLLECTIONS.ASSETS).stream():
            try:
                await run_diagnostic_pipeline(session, doc.id)
            except Exception:
                logger.exception("diagnostic pipeline failed for asset %s", doc.id)

    async def resolution_sweep() -> None:
        db = get_firestore_client()
        query = db.collection(COLLECTIONS.ISSUES).where(
            "state", "in", [IssueState.OPEN.value, IssueState.MONITORING.value]
        )
        for doc in query.stream():
            try:
                await call_mcp_tool(session, "diagnostics_resolve_if_recovered", {"issue_id": doc.id})
            except Exception:
                logger.exception("resolve check failed for issue %s", doc.id)

    async def sustainability_sweep() -> None:
        db = get_firestore_client()
        node = build_sustainability_node(session)
        for doc in db.collection(COLLECTIONS.ASSETS).stream():
            try:
                await node({"asset_id": doc.id, "tool_calls": []})
            except Exception:
                logger.exception("sustainability sweep failed for asset %s", doc.id)

    scheduler.add_job(diagnostic_sweep, "interval", seconds=DIAGNOSTIC_SWEEP_SECONDS, id="diagnostic_sweep")
    scheduler.add_job(resolution_sweep, "interval", seconds=RESOLUTION_SWEEP_SECONDS, id="resolution_sweep")
    scheduler.add_job(
        sustainability_sweep, "interval", seconds=SUSTAINABILITY_SWEEP_SECONDS, id="sustainability_sweep"
    )
    scheduler.start()
    return scheduler
