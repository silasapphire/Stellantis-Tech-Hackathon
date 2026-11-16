# Smart Connected Diagnostics Platform

Digital-twin diagnostics for an EV battery fleet and a diesel ICE fleet, driven by **real datasets**:

| Fleet | Dataset | Prepared by |
|---|---|---|
| ICE | Diesel OBD-II PIDs + DTC labels (`data/MASTER_TRAIN_X.xlsx`, `MASTER_TEST_X.xlsx`) | `data_prep/prepare_ice.py` |
| EV | NASA Li-ion battery aging (`data/1.…6. BatteryAgingARC*/B00xx.mat`) | `data_prep/prepare_ev.py` |

Stack: FastAPI · SQLite document store · MCP server (14 tools) · LangGraph agents · Cohere (chat + embeddings) · Next.js dashboard.
See [REPORT_MCP_RAG_LANGGRAPH.md](REPORT_MCP_RAG_LANGGRAPH.md) for how MCP, RAG and LangGraph fit together.

## Setup

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then set COHERE_API_KEY
cd apps/web ; npm install ; cd ../..

# Only if you have the raw data and want to regenerate data/processed (already committed):
python data_prep/prepare_ice.py  # -> data/processed/ice_obd_clean.csv (+ report json)
python data_prep/prepare_ev.py   # -> data/processed/ev_*.csv / ev_degradation.json
```

## Run (four terminals, from the repo root, venv active)

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn app.main:app --app-dir services/twin_service --port 8100
uvicorn app.main:app --app-dir apps/api --port 8000
uvicorn app.main:app --app-dir apps/simulator --port 8200
cd apps/web ; npm run dev       # http://localhost:3000
```

Without `COHERE_API_KEY` the platform still replays data, detects issues, scores risk and auto-resolves
(those are non-LLM); the LLM diagnostic sweep, the chat panel and embedding-based RAG need the key
(RAG falls back to keyword matching).

## Notes
- Data lives in `data/diagnostics.db` (SQLite). Delete it to reset the demo.
- `data/processed/` (22 MB) is committed, so after a `git pull` you can run without the raw files. The raw
  datasets (`data/MASTER_*.xlsx`, `data/1.…6. BatteryAgingARC*/`) are only needed to re-run the `data_prep` scripts.
- **Demo controls:** *Self-Healing* view → pick a fault type, severity and ramp speed, then **Inject fault** /
  **Clear now**; or switch **Autopilot** on to inject and clear random faults on a timer.
- The simulator replays recorded rows; the only synthetic element is the optional *demo fault injection*
  (Self-Healing view), which overlays a temporary fault so the self-heal loop can be shown.
