"""The diagnostic pipeline StateGraph: diagnose -> predict -> recommend -> (if
severe) self_heal. This is the graph the periodic diagnostic sweep runs per
asset; the separate OPEN -> MONITORING -> RESOLVED/ESCALATED recheck is a plain
(non-LLM) tool call from the auto-resolution scheduler job, not part of this
graph - that state transition is a deterministic comparison, not something that
benefits from LLM reasoning, so it isn't worth an inference call every tick.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from mcp import ClientSession

from agents.graph.nodes.diagnostic import build_diagnose_node
from agents.graph.nodes.predictive import build_predict_node
from agents.graph.nodes.recommend import build_recommend_node
from agents.graph.nodes.self_healing import build_self_heal_node
from agents.graph.state import GraphState

_HIGH_SEVERITY_AUTO_HEAL = {"high"}
_SELF_HEAL_RETRY_BUDGET = 3  # keep in sync with diagnostics.SELF_HEAL_ATTEMPT_BUDGET


def _route_after_diagnose(state: GraphState) -> str:
    if state.get("outcome") != "anomaly_found":
        return END

    issue = state.get("issue") or {}
    # Already fully diagnosed on a prior sweep (has a recommendation) and unchanged:
    # skip the expensive predict+recommend re-run and go straight to a self-heal
    # decision, so an unchanged open issue doesn't cost a full 3-call chain every tick.
    if issue.get("recommendation"):
        return _route_after_recommend(state)
    return "predict"


def _route_after_recommend(state: GraphState) -> str:
    issue = state.get("issue") or {}
    if issue.get("severity") not in _HIGH_SEVERITY_AUTO_HEAL:
        return END
    if issue.get("self_heal_attempts", 0) >= _SELF_HEAL_RETRY_BUDGET:
        return END  # budget exhausted; the resolution sweep will escalate it
    return "self_heal"


def build_diagnostic_graph(session: ClientSession):
    graph = StateGraph(GraphState)

    graph.add_node("diagnose", build_diagnose_node(session))
    graph.add_node("predict", build_predict_node(session))
    graph.add_node("recommend", build_recommend_node(session))
    graph.add_node("self_heal", build_self_heal_node(session))

    graph.add_edge(START, "diagnose")
    graph.add_conditional_edges(
        "diagnose", _route_after_diagnose, {"predict": "predict", "self_heal": "self_heal", END: END}
    )
    graph.add_edge("predict", "recommend")
    graph.add_conditional_edges("recommend", _route_after_recommend, {"self_heal": "self_heal", END: END})
    graph.add_edge("self_heal", END)

    return graph.compile()


async def run_diagnostic_pipeline(session: ClientSession, asset_id: str) -> GraphState:
    graph = build_diagnostic_graph(session)
    result = await graph.ainvoke({"asset_id": asset_id, "tool_calls": []})
    return result
