from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from cohere.core.api_error import ApiError
from agents.graph.nodes.conversational import run_conversation_turn
from common.store import COLLECTIONS, get_store
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger("chat")

_HISTORY_TURNS = 10


@router.websocket("/ws/chat/{asset_id}")
async def chat_ws(websocket: WebSocket, asset_id: str) -> None:
    await websocket.accept()
    session = websocket.app.state.mcp_session
    try:
        while True:
            user_message = await websocket.receive_text()
            _save_message(asset_id, "user", user_message)

            async def on_tool_call(name: str, args: dict) -> None:
                await websocket.send_json({"type": "tool_call", "tool": name, "args": args})

            try:
                history = _load_history(asset_id)
                answer, transcript = await run_conversation_turn(
                    session, asset_id, user_message, history=history, on_tool_call=on_tool_call
                )
            except Exception as exc:
                # A model/tool failure should never kill the connection - tell the user and
                # keep the socket open so they can just try again.
                logger.exception("chat turn failed for asset %s", asset_id)
                await websocket.send_json({"type": "error", "content": _friendly_error_message(exc)})
                continue

            _save_message(asset_id, "assistant", answer, tool_calls=transcript)
            await websocket.send_json({"type": "final", "content": answer})
    except WebSocketDisconnect:
        pass


def _friendly_error_message(exc: Exception) -> str:
    if isinstance(exc, RuntimeError) and "COHERE_API_KEY" in str(exc):
        return "The assistant isn't configured: set COHERE_API_KEY in .env and restart the API."
    if isinstance(exc, ApiError) and exc.status_code == 429:
        return "The assistant hit Cohere's rate limit and can't respond right now - please try again in a minute."
    if isinstance(exc, ApiError) and exc.status_code in (401, 403):
        return "Cohere rejected the API key - check COHERE_API_KEY in .env."
    return "Sorry, something went wrong answering that. Please try again."


def _load_history(asset_id: str) -> list[dict[str, str]]:
    db = get_store()
    query = (
        db.collection(COLLECTIONS.CHAT_SESSIONS)
        .document(asset_id)
        .collection("messages")
        .order_by("timestamp", direction="DESCENDING")
        .limit(_HISTORY_TURNS)
    )
    docs = list(query.stream())[::-1]
    return [{"role": d.to_dict()["role"], "content": d.to_dict()["content"]} for d in docs if d.to_dict()["role"] != "tool"]


def _save_message(asset_id: str, role: str, content: str, tool_calls: list[dict] | None = None) -> None:
    db = get_store()
    message_id = str(uuid.uuid4())
    db.collection(COLLECTIONS.CHAT_SESSIONS).document(asset_id).collection("messages").document(message_id).set(
        {
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "timestamp": datetime.now(timezone.utc),
        }
    )
