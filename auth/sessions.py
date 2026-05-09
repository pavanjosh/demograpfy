import json
import os
import uuid
from datetime import datetime, timedelta

SESSIONS_FILE = "sessions.json"
SESSION_TTL_HOURS = 24 * 7  # 7 days


def _load() -> dict:
    if not os.path.exists(SESSIONS_FILE):
        return {}
    with open(SESSIONS_FILE, "r") as f:
        return json.load(f)


def _save(sessions: dict):
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=2)


def create_session(user_id: str, tier: str) -> str:
    sessions = _load()
    now = datetime.now()
    # Prune expired sessions
    sessions = {k: v for k, v in sessions.items()
                if datetime.fromisoformat(v["expires_at"]) > now}
    token = str(uuid.uuid4())
    sessions[token] = {
        "user_id": user_id,
        "tier": tier,
        "expires_at": (now + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
    }
    _save(sessions)
    return token


def get_session(token: str) -> dict | None:
    if not token:
        return None
    sessions = _load()
    session = sessions.get(token)
    if not session:
        return None
    if datetime.fromisoformat(session["expires_at"]) <= datetime.now():
        delete_session(token)
        return None
    return session


def delete_session(token: str):
    sessions = _load()
    sessions.pop(token, None)
    _save(sessions)