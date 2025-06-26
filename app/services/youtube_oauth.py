"""
YouTube OAuth2 Service

Handles OAuth2 authentication for YouTube comment posting.
This is required for write operations like posting comments.
"""

import os
import pickle
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from ..config import settings
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class YouTubeOAuth2Service:
    """Service for handling YouTube OAuth2 authentication."""
    
    def __init__(self):
        """Initialize OAuth2 service."""
        self.credentials = None
        self.youtube_oauth = None
        self.credentials_file = os.path.join(settings.DATA_DIRECTORY, "youtube_credentials.pickle")
        self._oauth_flow = None
        
        # Try to load existing credentials
        self._load_credentials()
    
    def _load_credentials(self) -> Optional[Credentials]:
        """Load OAuth2 credentials from file."""
        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'rb') as token:
                    credentials = pickle.load(token)
                    if credentials and credentials.valid:
                        self.credentials = credentials
                        return credentials
                    elif credentials and credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())
                        self._save_credentials(credentials)
                        self.credentials = credentials
                        return credentials
            return None
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None
    
    def _save_credentials(self, credentials: Credentials):
        """Save OAuth2 credentials to file."""
        try:
            with open(self.credentials_file, 'wb') as token:
                pickle.dump(credentials, token)
            logger.info("OAuth2 credentials saved successfully")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
    
    def get_authorization_url(self) -> Optional[str]:
        """
        Get OAuth2 authorization URL for comment posting.
        
        Returns:
            Authorization URL or None if OAuth2 not configured
        """
        try:
            if not settings.has_oauth2_credentials():
                logger.error("OAuth2 credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
                return None
            
            # Allow HTTP for localhost development
            import os
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            
            # Create OAuth2 flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [settings.GOOGLE_OAUTH2_REDIRECT_URI]
                    }
                },
                scopes=settings.get_oauth2_scopes()
            )
            
            flow.redirect_uri = settings.GOOGLE_OAUTH2_REDIRECT_URI
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            
            # Store flow for later use
            self._oauth_flow = flow
            
            logger.info("OAuth2 authorization URL generated")
            return authorization_url
            
        except Exception as e:
            logger.error(f"Failed to generate OAuth2 authorization URL: {e}")
            return None
    
    def complete_authorization(self, authorization_response: str) -> bool:
        """
        Complete OAuth2 authorization with the response from Google.
        
        Args:
            authorization_response: Full authorization response URL
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._oauth_flow:
                logger.error("OAuth2 flow not initialized. Call get_authorization_url() first.")
                return False
            
            # Allow HTTP for localhost development
            import os
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            
            # Fetch token
            self._oauth_flow.fetch_token(authorization_response=authorization_response)
            
            # Save credentials
            credentials = self._oauth_flow.credentials
            self._save_credentials(credentials)
            self.credentials = credentials
            
            # Initialize OAuth2 service
            self._initialize_service()
            
            logger.info("OAuth2 authorization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete OAuth2 authorization: {e}")
            return False
    
    def _initialize_service(self):
        """Initialize YouTube service with OAuth2 credentials."""
        try:
            if self.credentials and self.credentials.valid:
                self.youtube_oauth = build(
                    serviceName='youtube',
                    version='v3',
                    credentials=self.credentials,
                    cache_discovery=False
                )
                logger.info("YouTube OAuth2 service initialized successfully")
                return True
            else:
                logger.warning("No valid OAuth2 credentials available")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize YouTube OAuth2 service: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """
        Check if authenticated for comment posting.
        
        Returns:
            True if authenticated and can post comments
        """
        try:
            if not self.credentials:
                self._load_credentials()
            
            if not self.credentials or not self.credentials.valid:
                return False
            
            if not self.youtube_oauth:
                return self._initialize_service()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check authentication status: {e}")
            return False
    
    def get_authenticated_service(self):
        """
        Get authenticated YouTube service for comment posting.
        
        Returns:
            YouTube service instance or None if not authenticated
        """
        if self.is_authenticated():
            return self.youtube_oauth
        return None
    
    def revoke_credentials(self) -> bool:
        """
        Revoke OAuth2 credentials and delete stored tokens.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.credentials:
                # Revoke the credentials
                self.credentials.revoke(Request())
            
            # Delete credentials file
            if os.path.exists(self.credentials_file):
                os.remove(self.credentials_file)
            
            # Reset instance variables
            self.credentials = None
            self.youtube_oauth = None
            self._oauth_flow = None
            
            logger.info("OAuth2 credentials revoked successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke credentials: {e}")
            return False 