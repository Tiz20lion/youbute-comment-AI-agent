"""
Authentication Middleware

Middleware for securing all routes in the YouTube Comment AI Agent application.
Handles session validation, redirects, and route protection.
"""

from fastapi import Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
from typing import Optional, Dict, Any

from ..services.auth_service import auth_service
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication for all routes."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # Public routes that don't require authentication
        self.public_routes = {
            "/",
            "/login",
            "/auth/login",
            "/auth/reset-password",
            "/auth/logout",
            "/oauth2callback",  # Allow OAuth2 callback without authentication
            "/health",
            "/favicon.ico",
            "/static",
            "/docs",
            "/openapi.json",
            "/redoc"
        }
        
        # Routes that require authentication but allow password reset redirect
        self.protected_routes = {
            "/dashboard",
            "/api",
            "/settings",
            "/metrics",
            "/ws"
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and handle authentication."""
        
        # Get the request path
        path = request.url.path
        
        # Check if this is a public route
        if self._is_public_route(path):
            response = await call_next(request)
            return response
        
        # Check if this is a protected route
        if self._is_protected_route(path):
            
            # Get session ID from cookies
            session_id = request.cookies.get("session_id")
            
            if not session_id:
                logger.info(f"🔒 Unauthorized access attempt to {path} - no session")
                return self._redirect_to_login(request)
            
            # Validate session
            session = auth_service.validate_session(session_id)
            
            if not session:
                logger.info(f"🔒 Unauthorized access attempt to {path} - invalid session")
                return self._redirect_to_login(request)
            
            # Check if user needs to reset password
            user_info = auth_service.get_user_info(session["username"])
            if user_info and user_info.get("requires_password_reset", False):
                if not path.startswith("/auth/reset-password"):
                    logger.info(f"🔐 Redirecting {session['username']} to password reset")
                    return RedirectResponse(url="/auth/reset-password", status_code=302)
            
            # Add user info to request state for use in route handlers
            request.state.user = session
            
            # Clean up expired sessions periodically
            auth_service.cleanup_expired_sessions()
            
            logger.debug(f"✅ Authenticated request to {path} by {session['username']}")
        
        # Process the request
        response = await call_next(request)
        return response
    
    def _is_public_route(self, path: str) -> bool:
        """Check if a route is public (doesn't require authentication)."""
        
        # Exact matches
        if path in self.public_routes:
            return True
        
        # Static files
        if path.startswith("/static/"):
            return True
        
        # Health check and docs
        if path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return True
        
        return False
    
    def _is_protected_route(self, path: str) -> bool:
        """Check if a route is protected (requires authentication)."""
        
        # All routes are protected by default except public ones
        return not self._is_public_route(path)
    
    def _redirect_to_login(self, request: Request) -> RedirectResponse:
        """Redirect to login page with original URL as next parameter."""
        
        # Get the original URL for redirect after login
        original_url = str(request.url)
        
        # Only add next parameter for non-root paths
        if request.url.path != "/":
            login_url = f"/login?next={original_url}"
        else:
            login_url = "/login"
        
        return RedirectResponse(url=login_url, status_code=302)


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get the current authenticated user from the request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User session info or None if not authenticated
    """
    return getattr(request.state, "user", None)


def require_auth(request: Request) -> Dict[str, Any]:
    """
    Require authentication for a route handler.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User session info
        
    Raises:
        HTTPException: If user is not authenticated
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(request: Request) -> Dict[str, Any]:
    """
    Require admin privileges for a route handler.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User session info
        
    Raises:
        HTTPException: If user is not authenticated or not admin
    """
    user = require_auth(request)
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user 