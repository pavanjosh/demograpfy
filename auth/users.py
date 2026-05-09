import json
import os
from datetime import datetime, timedelta

USERS_FILE = "users.json"
RESET_HOURS = 24


def load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def save_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def get_or_create_user(user_id: str) -> dict:
    """Return the user's record, creating it if it doesn't exist."""
    users = load_users()
    if user_id not in users:
        users[user_id] = {"usage": 0, "last_login": None}
        save_users(users)
    return users[user_id]


def update_last_login(user_id: str):
    """Record the current timestamp as the user's last login."""
    users = load_users()
    users.setdefault(user_id, {})
    users[user_id]["last_login"] = datetime.now().isoformat()
    save_users(users)


def should_reset_usage(user_id: str) -> bool:
    """Returns True if the user has never queried, or 24+ hours since their last query."""
    users = load_users()
    last_queried_str = users.get(user_id, {}).get("last_queried")
    if not last_queried_str:
        return True
    last_queried = datetime.fromisoformat(last_queried_str)
    return datetime.now() - last_queried >= timedelta(hours=RESET_HOURS)


def reset_usage(user_id: str):
    """Reset the question usage count to 0."""
    users = load_users()
    users.setdefault(user_id, {})
    users[user_id]["usage"] = 0
    save_users(users)


def increment_usage(user_id: str):
    """Increment the question usage count and record the query time."""
    users = load_users()
    users.setdefault(user_id, {"usage": 0})
    users[user_id]["usage"] = users[user_id].get("usage", 0) + 1
    users[user_id]["last_queried"] = datetime.now().isoformat()
    save_users(users)


def get_usage(user_id: str) -> int:
    users = load_users()
    return users.get(user_id, {}).get("usage", 0)


def get_last_login(user_id: str) -> str | None:
    users = load_users()
    return users.get(user_id, {}).get("last_login")


def get_last_queried(user_id: str) -> str | None:
    users = load_users()
    return users.get(user_id, {}).get("last_queried")
