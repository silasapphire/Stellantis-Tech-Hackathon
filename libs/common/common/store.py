"""Local document store shared by every service (replaces the former Firestore client).

One SQLite file (WAL mode, so the API process and the MCP-server subprocess can both
write to it) holding JSON documents addressed by a collection path + id, e.g.
  assets/ev-1
  telemetry/ev-1/readings/<uuid>

The query surface is deliberately tiny - `.collection().document().get/set/update`,
`.where(field, "==" | "in", value)`, `.order_by()`, `.limit()`, `.stream()`, `.add()` -
which is all the platform needs. datetimes are stored (and returned) as ISO-8601 strings.

Location: $DIAGNOSTICS_DB_PATH, default <repo>/data/diagnostics.db
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

_REPO_ROOT = Path(__file__).resolve().parents[3]
TELEMETRY_RETENTION = int(os.environ.get("TELEMETRY_RETENTION_PER_ASSET", "5000"))


class COLLECTIONS:
    ASSETS = "assets"
    TWIN_SNAPSHOTS = "twin_snapshots"
    TELEMETRY = "telemetry"
    ISSUES = "issues"
    NOTIFICATIONS = "notifications"
    CHAT_SESSIONS = "chat_sessions"
    AGENT_ACTIVITY = "agent_activity"


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value)}")


def _dumps(data: dict) -> str:
    return json.dumps(data, default=_json_default)


class DocumentSnapshot:
    def __init__(self, ref: "DocumentRef", data: dict | None):
        self.reference = ref
        self.id = ref.id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict:
        return dict(self._data or {})


class DocumentRef:
    def __init__(self, store: "Store", collection_path: str, doc_id: str):
        self._store = store
        self._collection_path = collection_path
        self.id = doc_id

    def collection(self, name: str) -> "CollectionRef":
        return CollectionRef(self._store, f"{self._collection_path}/{self.id}/{name}")

    def get(self) -> DocumentSnapshot:
        row = self._store._execute(
            "SELECT data FROM docs WHERE collection=? AND id=?", (self._collection_path, self.id)
        ).fetchone()
        return DocumentSnapshot(self, json.loads(row[0]) if row else None)

    def set(self, data: dict) -> None:
        self._store._execute(
            "INSERT INTO docs(collection, id, data) VALUES(?,?,?) "
            "ON CONFLICT(collection,id) DO UPDATE SET data=excluded.data",
            (self._collection_path, self.id, _dumps(data)),
            commit=True,
        )

    def update(self, fields: dict) -> None:
        with self._store._lock:
            current = self.get()
            if not current.exists:
                raise KeyError(f"{self._collection_path}/{self.id} does not exist")
            merged = {**current.to_dict(), **json.loads(_dumps(fields))}
            self.set(merged)


class Query:
    def __init__(self, store: "Store", collection_path: str):
        self._store = store
        self._collection_path = collection_path
        self._where: list[tuple[str, str, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def where(self, field: str, op: str, value: Any) -> "Query":
        if op not in ("==", "in"):
            raise ValueError(f"unsupported operator: {op}")
        self._where.append((field, op, value))
        return self

    def order_by(self, field: str, direction: str = "ASCENDING") -> "Query":
        self._order = (field, direction.upper().startswith("DESC"))
        return self

    def limit(self, n: int) -> "Query":
        self._limit = n
        return self

    def stream(self) -> Iterator[DocumentSnapshot]:
        sql = "SELECT id, data FROM docs WHERE collection=?"
        params: list[Any] = [self._collection_path]
        for field, op, value in self._where:
            expr = f"json_extract(data, '$.{field}')"
            if op == "==":
                sql += f" AND {expr} = ?"
                params.append(value)
            else:
                values = list(value)
                sql += f" AND {expr} IN ({','.join('?' * len(values))})"
                params.extend(values)
        if self._order:
            field, desc = self._order
            sql += f" ORDER BY json_extract(data, '$.{field}') {'DESC' if desc else 'ASC'}"
        else:
            sql += " ORDER BY rowid"
        if self._limit is not None:
            sql += " LIMIT ?"
            params.append(self._limit)
        for doc_id, data in self._store._execute(sql, tuple(params)).fetchall():
            yield DocumentSnapshot(DocumentRef(self._store, self._collection_path, doc_id), json.loads(data))


class CollectionRef(Query):
    def document(self, doc_id: str | None = None) -> DocumentRef:
        return DocumentRef(self._store, self._collection_path, doc_id or str(uuid.uuid4()))

    def add(self, data: dict) -> DocumentRef:
        ref = self.document()
        ref.set(data)
        return ref


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS docs ("
            " collection TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,"
            " PRIMARY KEY (collection, id))"
        )

    def _execute(self, sql: str, params: tuple = (), commit: bool = False) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def collection(self, name: str) -> CollectionRef:
        return CollectionRef(self, name)

    def prune_collection(self, collection_path: str, order_field: str, keep: int) -> None:
        """Delete all but the newest `keep` docs (by `order_field`) - used to cap telemetry growth."""
        self._execute(
            "DELETE FROM docs WHERE collection=? AND rowid NOT IN ("
            " SELECT rowid FROM docs WHERE collection=? "
            f" ORDER BY json_extract(data,'$.{order_field}') DESC LIMIT ?)",
            (collection_path, collection_path, keep),
        )

    def delete_collection(self, collection_path: str) -> None:
        self._execute("DELETE FROM docs WHERE collection=? OR collection LIKE ?", (collection_path, collection_path + "/%"))


@lru_cache(maxsize=1)
def get_store() -> Store:
    path = os.environ.get("DIAGNOSTICS_DB_PATH")
    resolved = Path(path) if path else _REPO_ROOT / "data" / "diagnostics.db"
    if not resolved.is_absolute():
        resolved = (_REPO_ROOT / resolved).resolve()
    return Store(resolved)
