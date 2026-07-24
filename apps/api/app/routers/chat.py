from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agents.graph.nodes.conversational import run_conversation_turn
from common.firestore_client import COLLECTIONS, get_firestore_client
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

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

            history = _load_history(asset_id)
            answer, transcript = await run_conversation_turn(
                session, asset_id, user_message, history=history, on_tool_call=on_tool_call
            )

            _save_message(asset_id, "assistant", answer, tool_calls=transcript)
            await websocket.send_json({"type": "final", "content": answer})
    except WebSocketDisconnect:
        pass


def _load_history(asset_id: str) -> list[dict[str, str]]:
    db = get_firestore_client()
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
    db = get_firestore_client()
    message_id = str(uuid.uuid4())
    db.collection(COLLECTIONS.CHAT_SESSIONS).document(asset_id).collection("messages").document(message_id).set(
        {
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "timestamp": datetime.now(timezone.utc),
        }
    )
