import sqlite3
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "discord_dreams.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the database schema."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        sender TEXT NOT NULL,
                        content TEXT,
                        media_path TEXT
                    )
                """)
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def add_message(self, session_id: str, sender: str, content: str, media_path: Optional[str] = None):
        """Add a message to the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversations (session_id, sender, content, media_path)
                    VALUES (?, ?, ?, ?)
                """, (session_id, sender, content, media_path))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to add message to DB: {e}")

    def get_history(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get conversation history for a session."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM conversations 
                    WHERE session_id = ? 
                    ORDER BY id ASC
                """, (session_id,))
                rows = cursor.fetchall()
                
                # Convert to list of dicts and take the last 'limit' items
                history = [dict(row) for row in rows]
                return history[-limit:]
        except Exception as e:
            logger.error(f"Failed to get history from DB: {e}")
            return []

    def get_last_message(self, session_id: str, sender: Optional[str] = None) -> Optional[Dict]:
        """Get the last message, optionally filtered by sender."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = "SELECT * FROM conversations WHERE session_id = ?"
                params = [session_id]
                
                if sender:
                    query += " AND sender = ?"
                    params.append(sender)
                
                query += " ORDER BY id DESC LIMIT 1"
                
                cursor.execute(query, tuple(params))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get last message from DB: {e}")
            return None

    def delete_last_message(self, session_id: str) -> bool:
        """Delete the last message for a session."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Find the ID of the last message
                cursor.execute("""
                    SELECT id FROM conversations 
                    WHERE session_id = ? 
                    ORDER BY id DESC LIMIT 1
                """, (session_id,))
                row = cursor.fetchone()
                
                if row:
                    cursor.execute("DELETE FROM conversations WHERE id = ?", (row[0],))
                    conn.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete last message from DB: {e}")
            return False

    def edit_last_message(self, session_id: str, new_content: str) -> bool:
        """Edit the content of the last message for a session."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Find the ID of the last message
                cursor.execute("""
                    SELECT id FROM conversations 
                    WHERE session_id = ? 
                    ORDER BY id DESC LIMIT 1
                """, (session_id,))
                row = cursor.fetchone()
                
                if row:
                    cursor.execute("""
                        UPDATE conversations 
                        SET content = ? 
                        WHERE id = ?
                    """, (new_content, row[0]))
                    conn.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to edit last message in DB: {e}")
            return False

    def get_all_sessions(self) -> List[str]:
        """Get a list of all unique session IDs."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT session_id FROM conversations ORDER BY timestamp DESC")
                rows = cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get sessions from DB: {e}")
            return []
