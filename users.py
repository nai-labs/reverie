"""
User configuration mapping friendly names to Discord IDs.
Add new users here instead of modifying .env
"""

users = {
    "niko": {
        "discord_id": 694998976402817054,
        "description": "Niko's Discord account"
    },
    "scarlett": {
        "discord_id": 1205657029243441174,
        "description": "Scarlett's Discord account"
    }
}

def get_user_id(username: str) -> int:
    """Get Discord ID for a username"""
    if username not in users:
        raise ValueError(f"User '{username}' not found. Available users: {', '.join(users.keys())}")
    return users[username]["discord_id"]

def list_users() -> list[str]:
    """Get list of available usernames"""
    return list(users.keys())
