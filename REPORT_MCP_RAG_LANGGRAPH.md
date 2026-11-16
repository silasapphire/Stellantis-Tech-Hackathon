# How MCP, RAG and LangGraph are used in this project

Smart Connected Diagnostics Platform — EV battery data (NASA Li-ion aging) and diesel ICE data (OBD-II PIDs + DTCs).

**One-line summary.** Telemetry flows into a local store. A **digital-twin service** turns it into findings. **MCP** is the single tool interface that exposes everything the system can *do* (read telemetry, run the twin, raise/resolve issues, search repair docs, trigger actions). **LangGraph** orchestrates a four-step agent pipeline in which a **Cohere** model decides which MCP tools to call. **RAG** is one of those tools: it grounds the repair recommendation in a retrieved knowledge base instead of letting the model improvise.

> **LangChain note.** LangChain itself is **not used**. The only LangChain-family package imported is `langgraph` ([agents/graph/graph.py](agents/graph/graph.py)). `langchain-core` appears in `requirements.txt` only because LangGraph depends on it; nothing in the code imports it. The LLM is called through the Cohere SDK directly ([agents/graph/tool_loop.py](agents/graph/tool_loop.py)), not through a LangChain chat-model wrapper.

```
 Replay simulator ──POST /telemetry──▶ FastAPI ──▶ SQLite document store
 (real OBD / NASA rows)                  │  ▲
                                         │  │ reads/writes
        ┌────────────────────────────────┘  │
        │  one long-lived MCP client session │
        ▼                                    │
 LangGraph graph (diagnose→predict→recommend→self-heal)        Chat WebSocket
        │  Cohere picks tools ───────────────────────────────────┘
        ▼
 MCP server (stdio subprocess, 14 tools) ──▶ Twin service (EV / ICE)
        │                                  ──▶ kb_search_repair_docs (RAG: Cohere embed + cosine)
        └──────────────────────────────────▶ document store, simulator (actions)
```

---

## 1. MCP (Model Context Protocol)

### What it is here
The **MCP server** ([mcp_server/server.py](mcp_server/server.py)) is a `FastMCP` server started as a subprocess over **stdio**. It registers **14 tools** in five modules. Every capability the agents have is one of these tools; the agents contain no business logic of their own.

| Module | Tools | Purpose |
|---|---|---|
| [telemetry.py](mcp_server/tools/telemetry.py) | `telemetry_get_latest`, `telemetry_get_history`, `telemetry_get_asset_metadata` | Read real replayed readings and asset info |
| [twin.py](mcp_server/tools/twin.py) | `twin_get_state`, `twin_simulate`, `twin_predict_failure` | Call the twin service; `predict` also persists risk onto the asset and a snapshot |
| [diagnostics.py](mcp_server/tools/diagnostics.py) | `diagnostics_detect_anomaly`, `diagnostics_get_issue_history`, `diagnostics_resolve_if_recovered`, `diagnostics_update_issue` | Threshold + DTC findings from the twin, IsolationForest outlier check, issue lifecycle (OPEN → MONITORING → RESOLVED / ESCALATED) |
| [actions.py](mcp_server/tools/actions.py) | `actions_trigger_self_heal`, `actions_send_notification` | State-changing actions (`throttle_load`, `eco_mode`, `restart_subsystem`, `schedule_service`) |
| [knowledge_base.py](mcp_server/tools/knowledge_base.py) | `kb_search_repair_docs`, `kb_stats` | **The RAG tool** (section 2) |

### The MCP client side
- [agents/graph/mcp_client.py](agents/graph/mcp_client.py) opens **one shared `ClientSession`** to the server when the API starts. Every graph node, the chat endpoint, the scheduler and the dashboard endpoints reuse it. The environment is passed to the subprocess explicitly (so service URLs and `COHERE_API_KEY` reach the tools).
- [agents/graph/mcp_tools.py](agents/graph/mcp_tools.py) is the bridge: it lists the server's tools and re-shapes each tool's JSON-schema into Cohere's function-calling format (`list_llm_tools`), and executes calls (`call_mcp_tool`).
- [agents/graph/tool_loop.py](agents/graph/tool_loop.py) is the ReAct-style loop used by every agent: send messages + tool schemas to Cohere → if the model returns `tool_calls`, run each through MCP and feed the result back → repeat until a final text answer (bounded by `max_turns`). Tool errors are returned to the model rather than crashing the loop.

### Who calls MCP tools
| Caller | LLM involved? | Examples |
|---|---|---|
| LangGraph nodes ([agents/graph/nodes/](agents/graph/nodes/)) | Yes – Cohere chooses the tool | diagnose → `diagnostics_detect_anomaly`; predict → `twin_predict_failure`; recommend → `kb_search_repair_docs` + `diagnostics_update_issue`; self-heal → `actions_trigger_self_heal` |
| Chat panel (`/ws/chat/{asset}`) | Yes – can use *all* tools, up to 6 tool turns per message | "Why is EV-B0005 flagged?" → telemetry + twin + KB tools |
| Scheduler, detection sweep ([scheduler.py](apps/api/app/scheduler.py)) | **No** – direct call | `diagnostics_detect_anomaly` (+ `twin_predict_failure` if findings), every 30 s |
| Scheduler, resolution sweep | **No** – direct call | `diagnostics_resolve_if_recovered` per open issue, every 20 s |
| Dashboard API ([dashboard.py](apps/api/app/routers/dashboard.py)) | No | `/kb/search`, `/kb/stats`, `/mcp/tools` call the MCP server |

### Why MCP rather than plain function calls
- **One tool surface** for the agents, the chat assistant, the scheduler and the UI – a fix to a tool is made once.
- **Process isolation:** the tools (store writes, twin calls, embeddings) run in their own process; the agent side only sees schemas and results.
- **Self-describing:** the dashboard's "MCP Tools" panel is populated from the server's own `list_tools`, with per-tool call counts taken from the agent-activity log.
- **Every call is observable:** the `on_tool_result` hook ([activity_log.py](agents/graph/activity_log.py)) writes each real tool call and a summary to the store; the "Recent Activity" and pipeline panels render that log.

---

## 2. RAG (Retrieval-Augmented Generation)

### Purpose
Make the recommendation attached to an issue **grounded** in documented repair guidance. The `recommend` node's prompt tells the model to call `kb_search_repair_docs` and to write a recommendation *only* from the text that comes back.

### Knowledge base
[mcp_server/knowledge_base/repair_docs.json](mcp_server/knowledge_base/repair_docs.json) — **21 documents**:
- 13 ICE documents, one per Diagnostic Trouble Code present in the OBD dataset (P0562, P0113, P0102, P0403, P0404, P2562, P0234, P2015, P2009, P0107, P0069, P0089, P0406),
- 3 ICE system-level documents (cooling, electrical, intake air) and 1 generic anomaly document,
- 4 EV battery documents (overtemperature, capacity fade, end of life, voltage out of range).

Each document's `fault_type` matches the issue `type` the twin produces (e.g. `dtc_P0403`, `battery_degradation`), which makes the query/document match natural.

### Retrieval ([knowledge_base.py](mcp_server/tools/knowledge_base.py))
1. **Embeddings:** Cohere `embed-english-v3.0` (`COHERE_EMBED_MODEL`), with `input_type="search_document"` for the corpus and `"search_query"` for the query.
2. **Index:** document vectors are computed once and cached on disk (`data/processed/kb_embeddings_<hash>.npy`, keyed by corpus + model). Only the short query is embedded per search.
3. **Search:** cosine similarity (normalised vectors, one matrix product in numpy) → top-k, optionally filtered by `vehicle_type` (`EV` / `ICE`; documents tagged `ALL` always qualify). A vector database would be overkill for 21 documents.
4. **Fallback:** if `COHERE_API_KEY` is missing or the embed call fails, the tool falls back to keyword overlap and says so in each result's `retrieval` field (the UI labels it "Keyword" instead of "Similarity").

### Where it appears
- **Agent pipeline:** `recommend` node → `kb_search_repair_docs` → `diagnostics_update_issue` stores the grounded recommendation on the issue (shown as "Recommended (RAG)" in the UI).
- **Chat:** the assistant can call the same tool when asked about repairs.
- **Dashboard:** the "RAG – Repair Knowledge" panel queries the open issue's text through `/kb/search` (which itself calls the MCP tool); the "Knowledge Base (RAG)" view is a free-text search.

### Limits to be aware of
- The corpus is **short, hand-written guidance** based on the standard meaning of each code and common repair practice. It is **not** extracted from manufacturer service manuals; for production use, replace it with licensed repair documentation.
- No chunking, reranking or citation spans — whole documents are retrieved. Cohere `rerank` would be the natural next step if the corpus grows.
- Scores are raw cosine similarities, so absolute values are not comparable to other systems' "similarity %".

---

## 3. LangGraph

### The graph ([agents/graph/graph.py](agents/graph/graph.py))
A `StateGraph(GraphState)` with four nodes and conditional routing:

```
START → diagnose ─┬─ no anomaly ───────────────────────────────▶ END
                  ├─ anomaly, already has a recommendation ──────▶ (skip to decision below)
                  └─ anomaly, new ─▶ predict ─▶ recommend ─┬─ severity ≠ high, or retries exhausted ─▶ END
                                                           └─ severity = high ─▶ self_heal ─▶ END
```

| Node | MCP tools it uses | Output written to graph state |
|---|---|---|
| `diagnose` ([diagnostic.py](agents/graph/nodes/diagnostic.py)) | `diagnostics_detect_anomaly` | findings, the issue, a plain-language explanation |
| `predict` ([predictive.py](agents/graph/nodes/predictive.py)) | `twin_predict_failure` | risk level / score / time-to-threshold |
| `recommend` ([recommend.py](agents/graph/nodes/recommend.py)) | `kb_search_repair_docs`, `diagnostics_update_issue` | RAG-grounded recommendation |
| `self_heal` ([self_healing.py](agents/graph/nodes/self_healing.py)) | `actions_trigger_self_heal` | chosen action and whether it was effective |

The shared state ([state.py](agents/graph/state.py)) also accumulates a `tool_calls` transcript. The routing logic is deliberate cost control: an already-recommended issue skips the expensive predict + recommend calls on later sweeps, and self-healing is attempted only for `high` severity and at most 3 times.

### How it runs
`run_diagnostic_pipeline(session, asset_id)` is invoked **per asset** by the scheduler's diagnostic sweep (every `DIAGNOSTIC_SWEEP_SECONDS`, default 180 s). The sweep is skipped (with a warning) when `COHERE_API_KEY` is not set. Each node is a small Cohere tool-loop (2–4 turns) with its own system prompt.

### What deliberately is *not* in the graph
- **Detection and resolution sweeps** are plain scheduled MCP calls. They are deterministic comparisons; spending an LLM call per tick would add cost and no value. They are why asset status, the issue list and auto-resolution keep working without an LLM key.
- **The chat assistant** is a tool loop ([conversational.py](agents/graph/nodes/conversational.py)), not a graph: it is open-ended and needs every tool, so there is no fixed topology to encode.

### What the pipeline does with the real data
- The twin turns the latest reading into findings: numeric thresholds (battery temperature, SOH, cell voltage; coolant, system voltage, intake temperature) and, for ICE, **one finding per active DTC** straight from the dataset's labels.
- Self-heal actions (`throttle_load`, `eco_mode`, `restart_subsystem`) can only clear a **demo-injected** fault overlay. Against a genuine DTC or a genuinely aged battery they report `effective=False`, the issue keeps its state, and after the retry budget it is **escalated** for human service. The prompt steers the model to `schedule_service` for DTCs and degradation.

---

## 4. End-to-end example (ICE-KIA-SPORTAGE, DTC P0403)

1. The simulator replays a real Kia Sportage OBD row (with `dtc_codes = [P0403, P0404, P2015, P2009]`) to `POST /telemetry`.
2. **Detection sweep** → `diagnostics_detect_anomaly` → the twin returns one finding per DTC → four `OPEN` issues, asset status `warning`, and `twin_predict_failure` stores a risk score. (No LLM.)
3. **LangGraph run** (needs Cohere): `diagnose` writes a plain-language explanation → `predict` summarises the risk → `recommend` calls `kb_search_repair_docs("P0403 EGR circuit…")`, gets `R-ICE-P0403`, and stores the grounded recommendation. Severity is `medium`, so the graph ends without self-heal.
4. The dashboard shows the issue with its recommendation, the RAG match, the MCP tool calls, and the pipeline's progress, all read from the store.
5. For a `high`-severity code (e.g. P0234 overboost) the graph continues to `self_heal`; the chosen action cannot clear a real DTC, so after 3 attempts the **resolution sweep** escalates it.

---

## 5. Verification status

| Piece | Verified how |
|---|---|
| MCP server + all 14 tools, issue lifecycle, store, twin, scheduler sweeps, dashboard endpoints | Run end-to-end against the real replayed data (detect → predict → KB → self-heal → resolve) |
| RAG retrieval | Keyword fallback exercised live; the Cohere-embedding path exercised against a **mocked** Cohere HTTP endpoint (correct request shape and response parsing; the similarity quality itself is untested) |
| Cohere tool-calling loop / LangGraph nodes | The tool loop was exercised against a **mocked** Cohere endpoint (message and tool-result serialisation, MCP round-trip). **Not tested against the live Cohere API – no API key was available**, so the LLM-driven graph run and chat answers still need a first run with your key |
