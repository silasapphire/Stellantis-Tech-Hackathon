# MASTER BUILD PROMPT — Smart Connected Diagnostics Platform (Full Architecture, Python Backend)

Paste this whole document into your coding tool (Claude Code, Cursor, etc.) as the project brief. This is the full-depth build — a single, well-organized MCP server, a LangGraph-orchestrated multi-agent layer, and the complete digital twin layer, all on a Python backend. Build in the order given in Section 9.

---

## 0. Vision

A platform that turns telemetry from any connected vehicle asset — EV, ICE engine, mobile app, or simulator — into a living digital twin. An agentic AI layer, orchestrated with LangGraph and wired to the twin and the platform's tools via a single MCP (Model Context Protocol) server, continuously diagnoses, predicts, explains, and where possible self-heals issues, closing the loop from detection to auto-resolution.

The differentiator: the platform auto-selects a vehicle-specific digital twin (EV or Engine) based on the asset's declared or detected type, so diagnostic logic, fault models, and recommendations are actually relevant to what's being monitored — not generic threshold alerts.

---

## 1. Tech stack

- **Frontend**: Next.js 14 (App Router), Tailwind CSS, Recharts for telemetry charts, Firestore JS SDK for live listeners
- **Backend**: **Python, FastAPI** — the core REST/WebSocket API and orchestration host. Use `uvicorn` as the ASGI server, `pydantic` models for every request/response schema (telemetry payloads, issue objects, agent tool schemas — this pays off directly since MCP tool schemas are just pydantic models under the hood)
- **Background jobs**: `APScheduler` (in-process, simplest) for the auto-resolution loop and periodic diagnostic sweeps — no external job queue needed unless you want one
- **Database**: Firestore, accessed via the `google-cloud-firestore` Python client (or `firebase-admin`). Use Firestore's real-time listeners on the frontend (`onSnapshot` via the JS SDK) for live dashboard updates — the Python backend writes, the frontend listens directly, no custom WebSocket relay needed for basic state sync. Use a real Python WebSocket (FastAPI's built-in `WebSocket` support) only for the chat panel's streaming responses.
- **Time-series consideration**: if you want proper time-series-optimized storage rather than Firestore subcollections for raw telemetry, layer in TimescaleDB (via `asyncpg`/`SQLAlchemy`) for the `telemetry` stream specifically, keep Firestore for everything stateful (assets, issues, twin snapshots, chat). Legitimate architecture talking point — Firestore for real-time app state, time-series DB for high-volume sensor data.
- **AI**: Groq API via the `groq` Python SDK, as the LLM backing every agent
- **Agent orchestration**: **LangGraph** (`langgraph` Python package) for the multi-agent layer. Each agent (diagnostic, predictive, self-healing, sustainability, conversational) is a node in a `StateGraph`; a shared typed graph state (pydantic model or `TypedDict`) carries asset id, twin state, issue draft, and tool-call results between nodes. Conditional edges implement the routing logic (e.g. diagnostic → predictive → self-heal, or straight to escalation), so the issue state machine in Section 7 is literally encoded as graph edges, not scattered if/else branches. Use `langgraph.prebuilt.ToolNode` (or a thin custom node) so any agent node can call out to the MCP server's tools mid-graph.
- **Agent-tool protocol**: **one real MCP server**, built with the official `mcp` Python SDK (`mcp.server.fastmcp` — `FastMCP` makes this fast to stand up). All capability groups (telemetry, digital twin, diagnostics, actions, knowledge base) are registered as tools on that single server process, namespaced by prefix (`telemetry_*`, `twin_*`, `diagnostics_*`, `actions_*`, `kb_*`) — one process, one tool schema surface, exposing tools over the protocol rather than in-process function calls.
- **Simulator**: standalone Python script/service (can be a tiny FastAPI app itself, or just an `asyncio` loop with `httpx`) generating synthetic EV/ICE telemetry with injectable faults via its own control endpoint
- **Auth**: FastAPI + Firebase Auth (verify ID tokens server-side) if you want a real login flow
- **Deploy**: Vercel (frontend), Render/Railway/GCP Cloud Run for the FastAPI backend and the single MCP server container, managed Firestore

---

## 2. High-level architecture (5 layers)

1. **Connected assets** — real IoT device, mobile app, web app, or simulator emitting telemetry
2. **Telemetry ingestion & storage** — FastAPI streaming intake (WebSocket or REST) + time-series storage
3. **Digital twin layer** — vehicle-type-aware Python model (EV or Engine) turning raw telemetry into meaningful state
4. **Agentic AI orchestrator** — a LangGraph `StateGraph` of specialized agent nodes (Python, Groq-backed), calling tools on the single MCP server, reasoning over twin state to diagnose, predict, act, and converse
5. **Outputs** — dashboard, alerts/notifications, self-healing actions, conversational assistant

---

## 3. Firestore + time-series data model

```
assets/{assetId}
  - name: string
  - vehicle_type: "EV" | "ICE"
  - status: "healthy" | "warning" | "critical"
  - risk_score: "low" | "medium" | "high"
  - risk_score_numeric: number        // for charting risk trend over time
  - created_at, last_seen: timestamp

twin_snapshots/{assetId}/snapshots/{snapshotId}   // periodic materialized twin state
  - timestamp: timestamp
  - modeled_state: object             // full DigitalTwin.get_state() output
  - predicted_failure_horizon_days: number | null

telemetry (in TimescaleDB if used, else Firestore subcollection)
  telemetry/{assetId}/readings/{readingId}
  - timestamp: timestamp
  - EV fields: soc, soh, pack_voltage, cell_temp_spread, motor_temp, inverter_temp,
    coolant_temp, charge_rate, charge_cycles
  - ICE fields: rpm, oil_pressure, oil_temp, coolant_temp, vibration_index,
    fuel_rate, air_fuel_ratio_proxy, misfire_count

issues/{issueId}
  - asset_id: string
  - type: string
  - state: "NEW" | "OPEN" | "MONITORING" | "RESOLVED" | "ESCALATED"
  - severity: "low" | "medium" | "high"
  - detected_at, resolved_at: timestamp
  - explanation: string               // diagnostic agent output
  - recommendation: string            // grounded via kb_search_repair_docs MCP tool
  - self_heal_action: string | null
  - self_heal_attempts: number
  - history: array of {state, timestamp, note, agent: string}

notifications/{notifId}
  - asset_id, issue_id: string
  - message: string
  - type: "alert" | "resolved" | "self_heal" | "escalation" | "prediction"
  - created_at: timestamp

chat_sessions/{assetId}/messages/{messageId}
  - role: "user" | "assistant" | "tool"
  - content: string
  - tool_calls: array | null
  - timestamp: timestamp

sustainability/{assetId}/periods/{periodId}
  - period_start, period_end: timestamp
  - energy_or_fuel_used: number
  - estimated_co2: number
  - baseline_co2: number               // without AI optimization, for before/after comparison
```

---

## 4. Digital twin layer (Python package)

```
/twin_service
  /app
    main.py                # FastAPI app exposing internal twin endpoints
    twins/
      base.py               # DigitalTwin abstract base class (ABC): get_state(), check_thresholds(),
                             # predict_failure(), simulate()
      ev_twin.py             # EVTwin(DigitalTwin) implementation
      engine_twin.py          # EngineTwin(DigitalTwin) implementation
      factory.py              # get_twin(vehicle_type) -> correct twin instance
    fault_library/
      ev_faults.json          # threshold defs, fault types, severity mapping
      ice_faults.json
    models.py               # pydantic schemas for twin state, requests, responses
```

### Vehicle-type selection
- Tagged at asset registration, or auto-detected from the first telemetry payload's schema:
  - `state_of_charge` / `pack_voltage` present → EV
  - `rpm` / `oil_pressure` / `coolant_temp` present → ICE
  - Ambiguous → fall back to manual selection UI

### EV digital twin models
- Battery pack: SOC, SOH, cell temperature spread, voltage sag under load
- Motor & inverter: torque output vs. commanded torque, inverter temperature, efficiency curve
- Thermal management loop: coolant temp, cooling pump duty cycle
- Charging behavior: charge rate, cycle count as a degradation proxy
- SOH degradation model: regression/lookup curve (`numpy`/`scipy` are fine here) as a function of charge cycles + average operating temperature — believable predictive maintenance without full electrochemistry

### Engine (ICE) digital twin models
- Combustion: RPM, engine load, air-fuel ratio proxy, misfire indicators
- Cooling: coolant temperature, thermostat behavior
- Lubrication: oil pressure, oil temperature, oil life estimate
- Emissions proxy: fuel-consumption-derived CO2 estimate
- Vibration: noisy accelerometer-like signal as a mechanical-wear anomaly proxy

### `simulate(hypothetical_params)`
Runs the twin forward from current state under hypothetical conditions ("what if this asset keeps driving like this for 30 more days") — this is what backs the predictive agent's forward projections and the conversational assistant's "will it fail soon?" answers.

Expose the twin service as an internal FastAPI API (`POST /twin/{asset_id}/state`, `POST /twin/{asset_id}/simulate`, `POST /twin/{asset_id}/predict`) that the `twin_*` tools on the MCP server wrap.

---

## 5. MCP server (single process, namespaced tool groups, Python `mcp` SDK)

One real, independently running MCP server process, built with `FastMCP` from the official `mcp` Python package. It exposes every tool the platform needs behind one protocol boundary — simpler to run and register than a fleet of servers, while still keeping the "tools over MCP, not in-process function calls" architecture story intact for judges. Internally, organize tools into clearly separated modules by capability group and register them all on the same `FastMCP` instance with a consistent naming prefix, so the boundary between capability groups stays legible even though there's one process.

```python
# mcp_server/server.py
from mcp.server.fastmcp import FastMCP
from mcp_server.tools import telemetry, twin, diagnostics, actions, knowledge_base

mcp = FastMCP("diagnostics-platform")

telemetry.register(mcp)       # telemetry_* tools
twin.register(mcp)            # twin_* tools
diagnostics.register(mcp)     # diagnostics_* tools
actions.register(mcp)         # actions_* tools
knowledge_base.register(mcp)  # kb_* tools

if __name__ == "__main__":
    mcp.run()
```

```
mcp_server/
  server.py                 # single FastMCP instance, wires up all tool modules
  tools/
    telemetry.py             # telemetry_get_latest, telemetry_get_history, telemetry_get_asset_metadata
    twin.py                  # twin_get_state, twin_simulate, twin_predict_failure
    diagnostics.py           # diagnostics_detect_anomaly, diagnostics_get_issue_history, diagnostics_resolve_if_recovered
    actions.py                # actions_trigger_self_heal, actions_send_notification
    knowledge_base.py         # kb_search_repair_docs
```

### Telemetry tools
- `telemetry_get_latest(asset_id)`
- `telemetry_get_history(asset_id, range)`
- `telemetry_get_asset_metadata(asset_id)` — returns vehicle_type, so twin selection is itself tool-driven

### Digital twin tools
- `twin_get_state(asset_id)`
- `twin_simulate(asset_id, hypothetical_params)`
- `twin_predict_failure(asset_id, horizon)`

### Diagnostics tools
- `diagnostics_detect_anomaly(asset_id)` — runs rule-based + lightweight ML anomaly detection (rolling z-score, or `sklearn`'s `IsolationForest`) against twin state
- `diagnostics_get_issue_history(asset_id)`
- `diagnostics_resolve_if_recovered(issue_id)` — the auto-clear logic

### Actions tools
- `actions_trigger_self_heal(asset_id, action)` — throttle load, switch to eco/limp mode, restart a subsystem, schedule a service booking
- `actions_send_notification(channel, message)`

### Knowledge base tools
- `kb_search_repair_docs(query)` — RAG lookup over manuals/fault-code reference docs. Simple, fast Python path: embed a small corpus of repair guidance per fault type with `sentence-transformers`, store vectors in Firestore or a lightweight local index (`faiss` or even `numpy` cosine similarity for a small corpus) so recommendations are grounded, not hallucinated

The server runs as a single process (`python mcp_server/server.py`), registered once with the LangGraph orchestrator's MCP client config (`mcp.client`). Document the full tool schema clearly (grouped by prefix) — this doubles as your architecture diagram content.

---

## 6. Agentic AI layer (Python, LangGraph + Groq)

Multiple focused agents, each modeled as a node in a LangGraph `StateGraph`, sharing one graph state and one MCP client session (`mcp.client`) against the single MCP server. Each agent node's "hands" are the MCP tools it's allowed to call; LangGraph's conditional edges are what actually implement the routing between agents, so the flow is inspectable as a graph rather than hidden in ad-hoc Python control flow.

| Agent (graph node) | Responsibility | MCP tool prefixes used |
|---|---|---|
| Diagnostic agent | Watches twin state, detects/classifies anomalies, writes issue explanation | `telemetry_*`, `twin_*`, `diagnostics_*` |
| Predictive agent | Forecasts failures before they occur, maintains risk score | `twin_*` (predict_failure, simulate) |
| Self-healing agent | Decides and executes safe automated remediation, tracks attempt count, escalates if remediation fails | `actions_*`, `diagnostics_*` |
| Sustainability agent | Computes energy/emissions impact per asset, before/after AI-optimization comparison | `twin_*`, `telemetry_*` |
| Conversational orchestrator | User-facing chat; routes questions to the right agent/tool, synthesizes final answer | all prefixes |

### Graph shape
```
diagnose_node --(anomaly found)--> predict_node --> recommend_node --> self_heal_node
     |                                                                       |
     +--(no anomaly)--> END                                    (recovered)--+--(N failed attempts)-->
                                                                  |                                    escalate_node --> END
                                                                  v
                                                              resolve_node --> END
```
- Graph state: a typed object (pydantic model or `TypedDict`) carrying `asset_id`, latest `twin_state`, the in-progress `issue` draft, `self_heal_attempts`, and the running list of tool-call results/messages for that invocation
- Conditional edges read fields off the state (anomaly severity, self-heal outcome, attempt count) to decide the next node — this is the diagnostic/auto-resolution state machine from Section 7, expressed directly as graph structure
- Each node function calls Groq for reasoning/text generation and, where it needs data or side effects, invokes MCP tools via the shared client session before returning updated state

### Orchestration pattern
- `APScheduler` background job (e.g. every 10-30s) invokes the graph's `diagnose_node` entry point against all assets, creating/updating issues; the graph runs through predict → recommend → (optionally) self-heal in one execution per asset when an anomaly is found
- On issue creation, the diagnostic node's explanation flows into the predictive node (attach risk/horizon) and the recommend node pulls a grounded recommendation via `kb_search_repair_docs`
- Auto-resolution: another `APScheduler` job re-enters the graph at a `resolve_node` that calls `diagnostics_resolve_if_recovered` against fresh telemetry; issue moves OPEN/MONITORING to RESOLVED automatically when metrics stay normal for a defined window, notification fires
- Escalation: a conditional edge out of `self_heal_node` checks `self_heal_attempts` against a budget — if remediation hasn't restored normal metrics in time, the edge routes to `escalate_node` instead of looping back, issue moves to ESCALATED, human-facing alert fires
- Conversational orchestrator is a separate, user-facing graph invocation served over a FastAPI WebSocket route for streaming — it has access to every tool on the MCP server and lets Groq's tool-calling decide at runtime which tools to call based on the user's question, chaining multiple tool calls per turn as needed (e.g. "will it fail soon?" calls `twin_get_state`, then `twin_predict_failure`, then synthesizes an answer), with LangGraph's streaming/event API driving the "checking twin state..." transparency UI

---

## 7. Diagnostic & auto-resolution state machine

```
NEW -> OPEN -> MONITORING -> RESOLVED (auto or manual)
                  -> ESCALATED (if worsening or self-heal fails)
```

- **Detection**: threshold rules (fast, explainable, from the fault library) plus a lightweight anomaly model for things thresholds miss
- **Alerting**: issue created, notification sent, recommendation attached from knowledge base RAG
- **Auto-resolution**: scheduled job re-checks OPEN/MONITORING issues against fresh telemetry; sustained normal range triggers RESOLVED and a "recovered" notification
- **Escalation**: failed self-heal attempts within budget move the issue to ESCALATED, with a human-facing alert

Build the full timeline (the history array on each issue doc) so the dashboard can render the state machine visually per asset — this is the single most-rewarded piece of the rubric (Diagnostic & Auto-Resolution Capability, 20%), build it with real rigor, not a stub.

---

## 8. Dashboard & UX

- **Fleet/asset overview**: cards with health status (green/amber/red), vehicle type icon, risk score, quick trend sparkline
- **Asset detail view**: live telemetry chart, issue timeline (full state machine visualized, not just current state), digital twin visualization (simplified schematic, e.g. a battery/engine diagram with live-colored zones for temperature/charge/wear)
- **Chat panel**: conversational assistant docked alongside the asset view, connected to the FastAPI WebSocket route, showing tool calls being made in real time ("checking twin state...", "predicting failure horizon...")
- **Notifications feed**: chronological, filterable by type (alert/resolved/self-heal/escalation/prediction)
- **Sustainability panel**: energy/emissions per asset, before/after AI-optimization comparison
- **Architecture view (optional, strong judge-facing touch)**: a live diagram showing which LangGraph node/agent and which MCP tool is currently active, useful during the demo to make the agentic layer visible rather than a black box

---

## 9. Build order

1. Firestore setup + FastAPI ingestion endpoint (`POST /telemetry`) + Python simulator with fault injection
2. Twin service: `DigitalTwin` ABC, `EVTwin`, `EngineTwin`, fault libraries, internal FastAPI endpoints
3. Stand up the single MCP server (`mcp_server/server.py`) with `telemetry_*` and `twin_*` tools registered (twin tools wrap the twin service via HTTP or direct import)
4. Rule-based anomaly detection implemented as `diagnostics_*` tools on the same MCP server, writing to `issues`
5. Auto-resolution `APScheduler` job
6. Dashboard: live asset cards, telemetry chart, issue timeline via Firestore `onSnapshot` (frontend listens directly)
7. Notifications feed
8. `actions_*` tools on the MCP server + LangGraph self-heal node + escalation edge
9. `kb_*` tools on the MCP server (repair-doc corpus + RAG lookup)
10. Build the LangGraph `StateGraph`: diagnose/predict/recommend nodes wired into issue creation, using Groq tool-calling against the MCP server via a shared MCP client session
11. Conversational orchestrator graph + chat panel over FastAPI WebSocket, with live tool-call transparency UI driven by LangGraph's streaming events
12. Sustainability agent node + panel
13. Architecture view (optional polish)

---

## 10. Demo script (~5-6 minutes)

1. Show dashboard with 2+ assets (EV and Engine) — both healthy
2. Trigger a fault in the simulator (e.g. EV battery overheating) — dashboard flips to amber in near-real-time
3. Issue appears with the Diagnostic agent's explanation, the Predictive agent's risk score, and a grounded recommendation, all populated automatically
4. Open chat: "Why is asset #12 flagged?" then "What's the recommended fix?" then "Will it fail soon?" — show live MCP tool calls and LangGraph node transitions in the transparency panel
5. Ask "Fix it" — Self-healing agent node triggers `actions_trigger_self_heal`, action shown taken
6. Let simulated telemetry recover — issue auto-clears to RESOLVED, "recovered" notification fires, no human closing it manually
7. Trigger a self-heal failure scenario deliberately — show ESCALATED state and human-facing alert
8. Switch to the Engine twin, trigger a different fault type — same platform, different twin logic, proves architectural generality
9. Close on the sustainability panel (before/after comparison) and fleet-wide risk overview

---

## 11. Suggested repo structure

```
/apps
  /web                    - Next.js frontend
  /api                    - FastAPI core service (ingestion, issue lifecycle, scheduled jobs, WebSocket chat route)
  /simulator              - Python synthetic telemetry generator with fault injection
/services
  /twin_service           - digital twin models (FastAPI internal service)
/mcp_server                - single FastMCP process, tools/ organized by capability group (telemetry, twin, diagnostics, actions, knowledge_base)
/agents
  /graph                   - LangGraph StateGraph definition: nodes (diagnostic, predictive, self_healing, sustainability, conversational), edges, shared graph state schema
requirements.txt (or pyproject.toml with poetry/uv) per Python service
```

### Core Python dependencies
`fastapi`, `uvicorn`, `pydantic`, `apscheduler`, `google-cloud-firestore` (or `firebase-admin`), `groq`, `mcp`, `langgraph`, `langchain-core` (for message/tool schemas LangGraph builds on), `httpx`, `numpy`, `scikit-learn` (for isolation forest), `sentence-transformers` (for RAG embeddings, optional), `websockets`

---

## 12. Mapping back to evaluation criteria

| Criteria | Weight | How this design addresses it |
|---|---|---|
| Solution architecture | 25% | Layered design, twin interface with two swappable implementations, a single MCP tool boundary cleanly namespaced by capability group, LangGraph state machine making agent routing explicit |
| Connected services & cloud integration | 20% | Streaming ingestion, time-series storage option, cloud-hosted agents and MCP server, Firestore real-time listeners |
| Diagnostic & auto-resolution capability | 20% | Full issue lifecycle state machine including escalation path — encoded directly as LangGraph conditional edges — with automatic recovery detection via real background verification |
| Innovation & creativity | 20% | Vehicle-aware twin selection, true multi-agent LangGraph architecture over a single MCP tool surface, all 6 bonus categories integrated cohesively |
| User experience & demo | 15% | Scripted live fault-inject to diagnose to heal to auto-clear to escalate flow, conversational assistant as centerpiece, live agent/tool-call transparency panel |

---

## 13. Non-negotiables for whoever is prompting the coding agent

- Backend is Python throughout: FastAPI for the core API, the MCP server, and the LangGraph agent layer — not a Node/Express mix — keep the whole agent/tool/twin stack in one language so context isn't lost translating between services.
- There must be exactly one MCP server: a real, separately runnable Python process (`mcp.server.fastmcp.FastMCP`) exposing every tool the platform needs, grouped internally by capability with a clear naming prefix, not five servers and not Python functions called in-process and labeled "MCP" for show.
- The multi-agent layer must be a real LangGraph `StateGraph` — distinct nodes per agent, explicit conditional edges for routing, shared typed graph state — not a single monolithic prompt or a hand-rolled if/else dispatcher relabeled as "agents."
- The auto-resolution loop must run against real fresh telemetry checks on an `APScheduler` schedule, not a manual "mark resolved" button.
- The escalation path (self-heal fails -> ESCALATED) must actually exist as a conditional edge in the graph and be demoable.
- Self-healing actions must be scoped to what's actually plausible for a vehicle: throttling, mode switches, subsystem resets, service scheduling, not literal physical repair. State this scope explicitly in the UI/demo copy so it reads as a deliberate design choice.
- Recommendations shown to the user must come from the `kb_search_repair_docs` MCP tool's RAG lookup, not be hallucinated inline by the orchestrator without grounding.
