"""
Authentication Service

Handles user authentication, password management, and session management
using a local SQLite database for secure access to the YouTube Comment AI Agent.
"""

import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import bcrypt

from ..config import settings
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class AuthService:
    """Service for handling user authentication and session management."""
    
    def __init__(self):
        """Initialize the authentication service."""
        self.db_path = os.path.join(settings.DATA_DIRECTORY, "auth.db")
        self.sessions: Dict[str, Dict[str, Any]] = {}  # In-memory session storage
        self.session_timeout = timedelta(hours=24)  # 24-hour sessions
        
        # Ensure data directory exists
        os.makedirs(settings.DATA_DIRECTORY, exist_ok=True)
        
        # Initialize database
        self._initialize_database()
        
        # Create default user if none exists
        self._create_default_user()
    
    def _initialize_database(self):
        """Initialize the SQLite database with user table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        is_admin BOOLEAN DEFAULT 0,
                        requires_password_reset BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        login_attempts INTEGER DEFAULT 0,
                        locked_until TIMESTAMP
                    )
                """)
                
                # Create sessions table (for persistent sessions if needed)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                """)
                
                conn.commit()
                logger.info("✅ Authentication database initialized successfully")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize authentication database: {e}")
            raise
    
    def _create_default_user(self):
        """Create the default TizlionAI user if no users exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if any users exist
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                
                if user_count == 0:
                    # Create default user
                    default_username = "TizlionAI"
                    default_password = "TizlionAI"
                    password_hash = self._hash_password(default_password)
                    
                    cursor.execute("""
                        INSERT INTO users (username, password_hash, is_admin, requires_password_reset)
                        VALUES (?, ?, ?, ?)
                    """, (default_username, password_hash, True, True))
                    
                    conn.commit()
                    logger.info(f"✅ Default user '{default_username}' created successfully")
                    logger.info("🔐 User must reset password on first login")
                
        except Exception as e:
            logger.error(f"❌ Failed to create default user: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user with username and password.
        
        Returns:
            Dict with success status, user info, and session details
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get user data
                cursor.execute("""
                    SELECT id, username, password_hash, is_admin, requires_password_reset,
                           login_attempts, locked_until
                    FROM users WHERE username = ?
                """, (username,))
                
                user_data = cursor.fetchone()
                
                if not user_data:
                    logger.warning(f"❌ Login attempt with invalid username: {username}")
                    return {
                        "success": False,
                        "message": "Invalid username or password",
                        "requires_password_reset": False
                    }
                
                user_id, db_username, password_hash, is_admin, requires_reset, login_attempts, locked_until = user_data
                
                # Check if account is locked
                if locked_until:
                    lock_time = datetime.fromisoformat(locked_until)
                    if datetime.now() < lock_time:
                        logger.warning(f"❌ Login attempt on locked account: {username}")
                        return {
                            "success": False,
                            "message": f"Account locked until {lock_time.strftime('%Y-%m-%d %H:%M:%S')}",
                            "requires_password_reset": False
                        }
                
                # Verify password
                if not self._verify_password(password, password_hash):
                    # Increment login attempts
                    new_attempts = login_attempts + 1
                    
                    # Lock account after 5 failed attempts
                    if new_attempts >= 5:
                        lock_until = datetime.now() + timedelta(minutes=30)
                        cursor.execute("""
                            UPDATE users SET login_attempts = ?, locked_until = ?
                            WHERE id = ?
                        """, (new_attempts, lock_until.isoformat(), user_id))
                        logger.warning(f"🔒 Account locked for 30 minutes: {username}")
                        message = "Account locked for 30 minutes due to multiple failed login attempts"
                    else:
                        cursor.execute("""
                            UPDATE users SET login_attempts = ?
                            WHERE id = ?
                        """, (new_attempts, user_id))
                        message = f"Invalid username or password. {5 - new_attempts} attempts remaining."
                    
                    conn.commit()
                    logger.warning(f"❌ Invalid password for user: {username}")
                    return {
                        "success": False,
                        "message": message,
                        "requires_password_reset": False
                    }
                
                # Reset login attempts on successful authentication
                cursor.execute("""
                    UPDATE users SET login_attempts = 0, locked_until = NULL, last_login = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), user_id))
                conn.commit()
                
                logger.info(f"✅ User authenticated successfully: {username}")
                
                return {
                    "success": True,
                    "message": "Authentication successful",
                    "user_id": user_id,
                    "username": db_username,
                    "is_admin": bool(is_admin),
                    "requires_password_reset": bool(requires_reset)
                }
                
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return {
                "success": False,
                "message": "Authentication system error",
                "requires_password_reset": False
            }
    
    def reset_password(self, username: str, current_password: str, new_password: str) -> Dict[str, Any]:
        """
        Reset a user's password.
        
        Returns:
            Dict with success status and message
        """
        try:
            # First authenticate with current password
            auth_result = self.authenticate_user(username, current_password)
            
            if not auth_result["success"]:
                return {
                    "success": False,
                    "message": "Current password is incorrect"
                }
            
            # Validate new password strength
            if len(new_password) < 8:
                return {
                    "success": False,
                    "message": "New password must be at least 8 characters long"
                }
            
            # Hash new password
            new_password_hash = self._hash_password(new_password)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update password and remove reset requirement
                cursor.execute("""
                    UPDATE users 
                    SET password_hash = ?, requires_password_reset = 0
                    WHERE username = ?
                """, (new_password_hash, username))
                
                conn.commit()
                
                logger.info(f"✅ Password reset successfully for user: {username}")
                
                return {
                    "success": True,
                    "message": "Password reset successfully"
                }
                
        except Exception as e:
            logger.error(f"❌ Password reset error: {e}")
            return {
                "success": False,
                "message": "Password reset system error"
            }
    
    def create_session(self, user_id: int, username: str, is_admin: bool) -> str:
        """
        Create a new user session.
        
        Returns:
            Session ID
        """
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + self.session_timeout
        
        self.sessions[session_id] = {
            "user_id": user_id,
            "username": username,
            "is_admin": is_admin,
            "created_at": datetime.now(),
            "expires_at": expires_at
        }
        
        logger.info(f"✅ Session created for user: {username}")
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Validate a session ID and return user info if valid.
        
        Returns:
            User info dict or None if invalid
        """
        if not session_id or session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Check if session has expired
        if datetime.now() > session["expires_at"]:
            del self.sessions[session_id]
            return None
        
        return session
    
    def logout_session(self, session_id: str) -> bool:
        """
        Logout a session by removing it.
        
        Returns:
            True if session was found and removed
        """
        if session_id in self.sessions:
            username = self.sessions[session_id]["username"]
            del self.sessions[session_id]
            logger.info(f"✅ User logged out: {username}")
            return True
        return False
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions."""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if now > session["expires_at"]
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            logger.info(f"🧹 Cleaned up {len(expired_sessions)} expired sessions")
    
    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information by username."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, username, is_admin, requires_password_reset, created_at, last_login
                    FROM users WHERE username = ?
                """, (username,))
                
                user_data = cursor.fetchone()
                
                if user_data:
                    return {
                        "id": user_data[0],
                        "username": user_data[1],
                        "is_admin": bool(user_data[2]),
                        "requires_password_reset": bool(user_data[3]),
                        "created_at": user_data[4],
                        "last_login": user_data[5]
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting user info: {e}")
            return None


# Global auth service instance
auth_service = AuthService() 