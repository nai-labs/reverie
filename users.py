import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

users = {}

# Load users from environment variables
user_index = 1
while True:
    user_name = os.getenv(f'USER_{user_index}_NAME')
    user_id = os.getenv(f'USER_{user_index}_DISCORD_ID')
    
    if not user_name or not user_id:
        break
    
    try:
        users[user_name] = {
            "discord_id": int(user_id),
            "description": f"{user_name}'s Discord account"
        }
    except ValueError:
        print(f"Warning: Invalid Discord ID for {user_name}: {user_id}")
    
    user_index += 1

# Validation: ensure at least one user is configured
if not users:
    raise ValueError("No users configured. Please check your .env file.")

def get_user_id(username: str) -> int:
    """Get Discord ID for a username"""
    if username not in users:
        raise ValueError(f"User '{username}' not found. Available users: {', '.join(users.keys())}")
    return users[username]["discord_id"]

def list_users() -> list[str]:
    """Get list of available usernames"""
    return list(users.keys())
