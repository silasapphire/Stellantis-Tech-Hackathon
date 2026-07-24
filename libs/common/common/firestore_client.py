"""Lazy, process-wide Firestore client shared by every service.

Reads credentials from either:
  - GOOGLE_APPLICATION_CREDENTIALS (path to a service account JSON), the standard ADC var, or
  - FIREBASE_SERVICE_ACCOUNT_JSON (path, relative to repo root, set in .env for this project)
plus FIREBASE_PROJECT_ID.
"""
from __future__ import annotations

import os
from functools import lru_cache

from google.cloud import firestore
from google.oauth2 import service_account


class COLLECTIONS:
    ASSETS = "assets"
    TWIN_SNAPSHOTS = "twin_snapshots"
    TELEMETRY = "telemetry"
    ISSUES = "issues"
    NOTIFICATIONS = "notifications"
    CHAT_SESSIONS = "chat_sessions"
    SUSTAINABILITY = "sustainability"


@lru_cache(maxsize=1)
def get_firestore_client() -> firestore.Client:
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    cred_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )

    if not project_id:
        raise RuntimeError(
            "FIREBASE_PROJECT_ID is not set. Copy .env.example to .env and fill in your "
            "Firebase project id and service account path."
        )

    if cred_path:
        credentials = service_account.Credentials.from_service_account_file(cred_path)
        return firestore.Client(project=project_id, credentials=credentials)

    # Falls back to Application Default Credentials (e.g. gcloud auth application-default login).
    return firestore.Client(project=project_id)
