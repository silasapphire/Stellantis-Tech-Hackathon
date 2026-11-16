# Migration checklist

Status: `[ ]` todo · `[~]` in progress · `[x]` done

- [x] **1. Remove Firebase**
  - [x] Replace Firestore with a local SQLite document store (`libs/common/common/store.py`)
  - [x] Port API routers, MCP tools, agents/activity log, scheduler to the store
  - [x] Replace the web app's Firestore `onSnapshot` hooks with API polling (`src/lib/api.ts`)
  - [x] Delete firebase config files, `firebase` npm dep, `google-cloud-firestore` dep, env vars
  - [ ] *(yours)* delete / revoke `serviceAccountKey.json` — left in place, now unused
- [x] **2. Switch the LLM key/provider from Groq to Cohere** (`COHERE_API_KEY`)
  - [x] Tool-calling loop rewritten on the Cohere v2 chat API (`agents/graph/tool_loop.py`)
  - [x] Cohere embeddings for the RAG knowledge base (keyword fallback if no key)
  - [x] `.env.example` / `.env` / requirements updated
  - [ ] *(yours)* paste your key into `.env` — it is empty
- [x] **3. Use the real datasets (ICE = OBD-II diesel PIDs, EV = NASA Li-ion aging)**
  - [x] Data preparation scripts + cleaned outputs in `data/processed/`
  - [x] Twin schemas, fault libraries and thresholds rewritten on the real features
- [x] **4. Remove simulated data that is no longer necessary**
  - [x] Random-walk generators and baseline profiles deleted; simulator replays real data
  - [x] Invented sustainability/CO2 agent removed
  - [x] Optional demo fault-injection overlay kept (off by default)
- [x] **5. UI redesign to match the attached mockup (EV and ICE)**
  - [x] Backend endpoints the dashboard needs (stats, activity, pipeline, kb, mcp, health, twin)
  - [x] Dark theme, sidebar, KPI row, fleet list, digital twin, LangGraph pipeline
  - [x] Live telemetry, RAG matches, MCP tools, recent activity, architecture, chat
  - [x] `next build`, `tsc` and `eslint` pass; screenshots checked for EV and ICE assets
- [x] **6. Report: how MCP, RAG and LangChain/LangGraph are used** (`REPORT_MCP_RAG_LANGGRAPH.md`)
- [x] **7. End-to-end verification** — see the final message for what could and could not be tested
