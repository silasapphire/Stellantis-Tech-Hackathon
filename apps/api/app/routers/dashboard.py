"""Read-only endpoints the dashboard polls (replaces the old Firestore realtime listeners)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
from agents.graph.mcp_tools import call_mcp_tool
from common.store import COLLECTIONS, get_store
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(tags=["dashboard"])

_async_http = httpx.AsyncClient(timeout=2.0, trust_env=False)

TWIN_SERVICE_URL = os.environ.get("TWIN_SERVICE_URL", "http://127.0.0.1:8100")
SIMULATOR_URL = os.environ.get("SIMULATOR_URL", "http://127.0.0.1:8200")
_UNRESOLVED = ("NEW", "OPEN", "MONITORING", "ESCALATED")
# LangGraph node name -> pipeline step shown in the UI
_PIPELINE_STEPS = [("diagnostic", "Diagnose"), ("predictive", "Predict"), ("recommend", "Recommend"), ("self_healing", "Self-Heal")]


def _docs(collection, where: tuple | None = None, order: str | None = None, limit: int = 100) -> list[dict]:
    query = get_store().collection(collection)
    if where:
        query = query.where(*where)
    if order:
        query = query.order_by(order, direction="DESCENDING")
    return [{"id": d.id, **d.to_dict()} for d in query.limit(limit).stream()]


@router.get("/issues")
def list_issues(asset_id: str | None = None, limit: int = Query(default=100, le=500)) -> list[dict]:
    return _docs(COLLECTIONS.ISSUES, ("asset_id", "==", asset_id) if asset_id else None, "detected_at", limit)


@router.get("/notifications")
def list_notifications(asset_id: str | None = None, limit: int = Query(default=50, le=500)) -> list[dict]:
    return _docs(COLLECTIONS.NOTIFICATIONS, ("asset_id", "==", asset_id) if asset_id else None, "created_at", limit)


@router.get("/activity")
def list_activity(asset_id: str | None = None, limit: int = Query(default=40, le=500)) -> list[dict]:
    return _docs(COLLECTIONS.AGENT_ACTIVITY, ("asset_id", "==", asset_id) if asset_id else None, "timestamp", limit)


@router.get("/pipeline/{asset_id}")
def pipeline_status(asset_id: str) -> dict:
    """Where the LangGraph diagnostic pipeline is for an asset, derived from its real tool-call log."""
    events = _docs(COLLECTIONS.AGENT_ACTIVITY, ("asset_id", "==", asset_id), "timestamp", 60)
    pipeline_events = [e for e in events if e["agent"] in dict(_PIPELINE_STEPS)]
    latest_run: list[dict] = []
    for e in pipeline_events:  # newest first; stop at the start of the latest run
        latest_run.append(e)
        if e["agent"] == "diagnostic":
            break
    seen = {e["agent"] for e in latest_run}
    last = pipeline_events[0] if pipeline_events else None
    steps = [{"key": k, "label": label, "status": "done" if k in seen else "pending"} for k, label in _PIPELINE_STEPS]
    age = None
    if last:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last["timestamp"])).total_seconds()
    return {"steps": steps, "last_event": last, "seconds_since_last_event": age}


@router.get("/stats")
def stats() -> dict:
    assets = _docs(COLLECTIONS.ASSETS)
    issues = _docs(COLLECTIONS.ISSUES, order="detected_at", limit=2000)
    activity = _docs(COLLECTIONS.AGENT_ACTIVITY, order="timestamp", limit=5000)
    hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    active = [i for i in issues if i["state"] in _UNRESOLVED]
    detect = [a for a in activity if a["tool"] == "diagnostics_detect_anomaly"]
    heals = [a for a in activity if a["tool"] == "actions_trigger_self_heal"]
    effective = [a for a in heals if "effective=True" in a.get("summary", "")]
    at_risk = [a for a in assets if a.get("risk_score") in ("medium", "high")]

    return {
        "fleet": {
            "total": len(assets),
            "ev": sum(a["vehicle_type"] == "EV" for a in assets),
            "ice": sum(a["vehicle_type"] == "ICE" for a in assets),
        },
        "active_alerts": {"count": len(active), "new_last_hour": sum(i["detected_at"] >= hour_ago for i in active)},
        "diagnostics_run": {"count": len(detect), "last_hour": sum(a["timestamp"] >= hour_ago for a in detect)},
        "predictions": {"at_risk": len(at_risk), "high_risk": sum(a.get("risk_score") == "high" for a in assets)},
        "self_heals": {
            "executed": len(heals),
            "success_pct": round(100 * len(effective) / len(heals)) if heals else None,
        },
    }


@router.get("/kb/search")
async def kb_search(request: Request, q: str, vehicle_type: str = "", top_k: int = 3) -> list[dict]:
    """RAG retrieval, executed through the MCP server's kb_search_repair_docs tool."""
    try:
        return await call_mcp_tool(
            request.app.state.mcp_session, "kb_search_repair_docs",
            {"query": q, "top_k": top_k, "vehicle_type": vehicle_type},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/kb/stats")
async def kb_stats(request: Request) -> dict:
    return await call_mcp_tool(request.app.state.mcp_session, "kb_stats", {})


@router.get("/mcp/tools")
async def mcp_tools(request: Request) -> list[dict]:
    result = await request.app.state.mcp_session.list_tools()
    usage: dict[str, int] = {}
    for a in _docs(COLLECTIONS.AGENT_ACTIVITY, order="timestamp", limit=5000):
        usage[a["tool"]] = usage.get(a["tool"], 0) + 1
    return [{"name": t.name, "description": t.description or "", "calls": usage.get(t.name, 0)} for t in result.tools]


@router.get("/system/health")
async def system_health(request: Request) -> list[dict]:
    async def ping(name: str, url: str | None) -> dict:
        if url is None:
            return {"name": name, "status": "running"}
        try:
            r = await _async_http.get(url)
            return {"name": name, "status": "running" if r.status_code == 200 else "degraded"}
        except httpx.HTTPError:
            return {"name": name, "status": "down"}

    try:
        await request.app.state.mcp_session.list_tools()
        mcp_status = "running"
    except Exception:
        mcp_status = "down"
    scheduler = getattr(request.app.state, "scheduler", None)
    return [
        await ping("Simulator (replay)", f"{SIMULATOR_URL}/health"),
        {"name": "FastAPI (API + Scheduler)", "status": "running" if scheduler and scheduler.running else "degraded"},
        {"name": "MCP Server", "status": mcp_status},
        await ping("Twin Service", f"{TWIN_SERVICE_URL}/health"),
        await ping("Document store (SQLite)", None),
    ]
