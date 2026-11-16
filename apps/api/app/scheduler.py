"""Three independent APScheduler jobs sharing the API process's one long-lived
MCP session:
  - detection sweep: a plain (non-LLM) diagnostics_detect_anomaly (+ twin_predict_failure
    when something is found) call per asset, so asset status, risk and the issue list stay
    current even without an LLM key or when the LLM quota is exhausted
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
from common.store import COLLECTIONS, get_store
from common.schemas import IssueState

logger = logging.getLogger("scheduler")

DIAGNOSTIC_SWEEP_SECONDS = int(os.environ.get("DIAGNOSTIC_SWEEP_SECONDS", "180"))
DETECTION_SWEEP_SECONDS = int(os.environ.get("DETECTION_SWEEP_SECONDS", "30"))
RESOLUTION_SWEEP_SECONDS = int(os.environ.get("RESOLUTION_SWEEP_SECONDS", "20"))


def start_scheduler(session: ClientSession) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def detection_sweep() -> None:
        db = get_store()
        for doc in db.collection(COLLECTIONS.ASSETS).stream():
            try:
                detected = await call_mcp_tool(session, "diagnostics_detect_anomaly", {"asset_id": doc.id})
                if detected.get("findings"):
                    await call_mcp_tool(session, "twin_predict_failure", {"asset_id": doc.id})
            except Exception:
                logger.exception("detection sweep failed for asset %s", doc.id)

    async def diagnostic_sweep() -> None:
        if not os.environ.get("COHERE_API_KEY"):
            logger.warning("COHERE_API_KEY not set - skipping the LLM diagnostic sweep (detection still runs)")
            return
        db = get_store()
        for doc in db.collection(COLLECTIONS.ASSETS).stream():
            try:
                await run_diagnostic_pipeline(session, doc.id)
            except Exception:
                logger.exception("diagnostic pipeline failed for asset %s", doc.id)

    async def resolution_sweep() -> None:
        db = get_store()
        query = db.collection(COLLECTIONS.ISSUES).where(
            "state", "in", [IssueState.OPEN.value, IssueState.MONITORING.value]
        )
        for doc in query.stream():
            try:
                await call_mcp_tool(session, "diagnostics_resolve_if_recovered", {"issue_id": doc.id})
            except Exception:
                logger.exception("resolve check failed for issue %s", doc.id)

    scheduler.add_job(detection_sweep, "interval", seconds=DETECTION_SWEEP_SECONDS, id="detection_sweep")
    scheduler.add_job(diagnostic_sweep, "interval", seconds=DIAGNOSTIC_SWEEP_SECONDS, id="diagnostic_sweep")
    scheduler.add_job(resolution_sweep, "interval", seconds=RESOLUTION_SWEEP_SECONDS, id="resolution_sweep")
    scheduler.start()
    return scheduler
