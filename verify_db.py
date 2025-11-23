import os
import shutil
from conversation_manager import ConversationManager
from database_manager import DatabaseManager

# Clean up previous test artifacts
if os.path.exists("discord_dreams.db"):
    # Rename it to keep it safe if it was real
    # But for this test we want a clean slate or just append?
    # Let's just use the existing one, it's fine.
    pass

print("--- SQLite Verification ---")

# 1. Initialize ConversationManager
print("Initializing ConversationManager...")
# We need a valid character name. 'Gus' is in characters.py?
# Let's check characters.py or use a known one.
# I'll assume 'Gus' or 'Raquel' exists based on previous context or just pick the first one.
from characters import characters
char_name = list(characters.keys())[0]
print(f"Using character: {char_name}")

cm = ConversationManager(char_name)
session_id = "test_session_123"
cm.set_log_file(session_id) # This sets session_id and creates folder

print(f"Session ID: {cm.session_id}")

# 2. Add messages
print("Adding messages...")
cm.add_user_message("Hello, are you there?")
cm.add_assistant_response("Yes, I am here.")

# 3. Verify DB content
print("Verifying DB content...")
db = DatabaseManager()
history = db.get_history(session_id)

if len(history) >= 2:
    print("SUCCESS: Retrieved messages from DB.")
    print(f"User: {history[-2]['content']}")
    print(f"Bot: {history[-1]['content']}")
else:
    print("FAILURE: Could not retrieve messages from DB.")
    print(f"History length: {len(history)}")

# 4. Verify Last Message
last_msg = db.get_last_message(session_id)
if last_msg and last_msg['content'] == "Yes, I am here.":
    print("SUCCESS: get_last_message works.")
else:
    print(f"FAILURE: get_last_message failed. Got: {last_msg}")

# 5. Clean up (optional, maybe keep for inspection)
# shutil.rmtree(cm.subfolder_path)
print("Verification complete.")
