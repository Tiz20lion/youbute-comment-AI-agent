"""
YouTube Service

This service handles all interactions with the YouTube Data API v3:
- Channel information retrieval
- Video metadata and content fetching  
- Comment retrieval and posting
        - Video description extraction
- Rate limiting and error handling

Uses the official Google API client library for proper YouTube Data API v3 integration.
"""

import asyncio
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json

# Google API client imports
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
# Removed transcript-related imports - using descriptions instead
import pickle
import os

from ..config import settings
from ..utils.logging_config import get_logger
from ..utils.validators import YouTubeValidator

logger = get_logger(__name__)


class YouTubeService:
    """Service for interacting with YouTube Data API v3 using official Google client."""
    
    def __init__(self):
        """Initialize YouTube service with API configuration."""
        # Use YOUTUBE_API_KEY if available, fallback to GOOGLE_API_KEY
        self.api_key = settings.YOUTUBE_API_KEY or settings.GOOGLE_API_KEY
        
        if not self.api_key:
            logger.error("No YouTube API key configured. Set YOUTUBE_API_KEY or GOOGLE_API_KEY in environment.")
            raise ValueError("YouTube API key is required")
        
        # Build YouTube API service (read-only with API key)
        self.youtube = None
        self._initialize_service()
        
        # OAuth2 service for comment posting (write operations)
        self.youtube_oauth = None
        self.credentials = None
        self.credentials_file = os.path.join(settings.DATA_DIRECTORY, "youtube_credentials.pickle")
        
        # Rate limiting
        self.requests_per_minute = 100
        self.requests_made = []
        
        # Description processing (no special formatter needed)
    
    def _initialize_service(self):
        """Initialize the YouTube API service."""
        try:
            self.youtube = build(
                serviceName='youtube',
                version='v3',
                developerKey=self.api_key,
                cache_discovery=False
            )
            logger.info("YouTube API service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize YouTube API service: {e}")
            raise
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        now = datetime.now()
        
        # Remove requests older than 1 minute
        self.requests_made = [req_time for req_time in self.requests_made 
                             if now - req_time < timedelta(minutes=1)]
        
        # Wait if we've hit the rate limit
        if len(self.requests_made) >= self.requests_per_minute:
            wait_time = 60 - (now - self.requests_made[0]).total_seconds()
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
    
    def _record_request(self):
        """Record a request timestamp for rate limiting."""
        self.requests_made.append(datetime.now())
    
    def _load_credentials(self) -> Optional[Credentials]:
        """Load OAuth2 credentials from file."""
        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'rb') as token:
                    credentials = pickle.load(token)
                    if credentials and credentials.valid:
                        return credentials
                    elif credentials and credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())
                        self._save_credentials(credentials)
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
    
    def get_oauth2_authorization_url(self, port: int = None) -> Optional[str]:
        """
        Get OAuth2 authorization URL for comment posting with dynamic redirect URI.
        
        Args:
            port: The port number to use for redirect URI (defaults to settings.PORT)
            
        Returns:
            Authorization URL or None if OAuth2 not configured
        """
        try:
            if not settings.has_oauth2_credentials():
                logger.error("OAuth2 credentials not configured")
                return None
            
            # Allow HTTP for localhost development
            import os
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            
            # Get dynamic redirect URI based on current port
            redirect_uri = settings.get_oauth2_redirect_uri(port=port)
            
            # Create OAuth2 flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=settings.get_oauth2_scopes()
            )
            
            flow.redirect_uri = redirect_uri
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            
            # Store flow for later use
            self._oauth_flow = flow
            
            logger.info(f"OAuth2 authorization URL generated with redirect URI: {redirect_uri}")
            return authorization_url
            
        except Exception as e:
            logger.error(f"Failed to generate OAuth2 authorization URL: {e}")
            return None
    
    def complete_oauth2_authorization(self, authorization_response: str) -> bool:
        """
        Complete OAuth2 authorization with the response from Google.
        
        Args:
            authorization_response: Full authorization response URL
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Allow HTTP for localhost development
            import os
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            
            # Get dynamic redirect URI (same as in authorization URL generation)
            redirect_uri = settings.get_oauth2_redirect_uri()
            
            # Create a fresh OAuth2 flow for the callback (more reliable than stored flow)
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=settings.get_oauth2_scopes()
            )
            
            flow.redirect_uri = redirect_uri
            
            # Fetch token using the authorization response
            flow.fetch_token(authorization_response=authorization_response)
            
            # Save credentials
            credentials = flow.credentials
            self._save_credentials(credentials)
            self.credentials = credentials
            
            # Initialize OAuth2 service
            self._initialize_oauth_service()
            
            logger.info("OAuth2 authorization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete OAuth2 authorization: {e}")
            return False
    
    def _initialize_oauth_service(self):
        """Initialize YouTube service with OAuth2 credentials for comment posting."""
        try:
            if not self.credentials:
                self.credentials = self._load_credentials()
            
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
    
    def is_authenticated_for_posting(self) -> bool:
        """
        Check if authenticated for comment posting by making an actual API call.
        
        Returns:
            True if authenticated and can post comments
        """
        try:
            if not self.credentials:
                self.credentials = self._load_credentials()
            
            if not self.credentials or not self.credentials.valid:
                logger.info("No valid OAuth2 credentials found")
                return False
            
            # Try to initialize OAuth service
            if not self.youtube_oauth:
                if not self._initialize_oauth_service():
                    logger.info("Failed to initialize OAuth service")
                    return False
            
            # Test the credentials by making a simple API call
            try:
                # Make a test call to get channel info for the authenticated user
                request = self.youtube_oauth.channels().list(
                    part="snippet",
                    mine=True
                )
                response = request.execute()
                
                # If we get here, the credentials are valid and working
                logger.info("OAuth2 credentials verified successfully")
                return True
                
            except Exception as api_error:
                logger.error(f"OAuth2 credentials test failed: {api_error}")
                # Clear invalid credentials
                self.credentials = None
                self.youtube_oauth = None
                return False
            
        except Exception as e:
            logger.error(f"Failed to check authentication status: {e}")
            return False
    
    async def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get channel information using YouTube Data API v3.
        
        Args:
            channel_id: YouTube channel ID
            
        Returns:
            Channel information or None if failed
        """
        try:
            await self._check_rate_limit()
            
            # Use channels().list() method as per API documentation
            request = self.youtube.channels().list(
                part="snippet,statistics,brandingSettings",
                id=channel_id
            )
            
            response = request.execute()
            self._record_request()
            
            if not response.get("items"):
                logger.warning(f"No channel found with ID: {channel_id}")
                return None
            
            channel = response["items"][0]
            snippet = channel.get("snippet", {})
            statistics = channel.get("statistics", {})
            branding = channel.get("brandingSettings", {}).get("channel", {})
            
            return {
                "id": channel_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "handle": snippet.get("customUrl", ""),
                "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "published_at": snippet.get("publishedAt", ""),
                "subscriber_count": int(statistics.get("subscriberCount", 0)),
                "video_count": int(statistics.get("videoCount", 0)),
                "view_count": int(statistics.get("viewCount", 0)),
                "country": snippet.get("country", ""),
                "keywords": branding.get("keywords", "")
            }
            
        except HttpError as e:
            logger.error(f"YouTube API HTTP error getting channel info: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            return None
    
    def _parse_duration_to_seconds(self, duration: str) -> int:
        """
        Parse YouTube duration format (PT#M#S) to seconds.
        
        Args:
            duration: Duration in ISO 8601 format (e.g., PT4M13S)
            
        Returns:
            Duration in seconds
        """
        import re
        
        if not duration:
            return 0
        
        try:
            # Parse PT#H#M#S format
            pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
            match = re.match(pattern, duration)
            
            if not match:
                return 0
            
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            
            return hours * 3600 + minutes * 60 + seconds
            
        except Exception as e:
            logger.warning(f"Failed to parse duration '{duration}': {e}")
            return 0

    async def get_channel_videos(self, channel_id: str, max_results: int = None, exclude_shorts: bool = True) -> List[Dict[str, Any]]:
        """
        Get videos from a channel using YouTube Data API v3, with enhanced shorts filtering.
        
        Args:
            channel_id: YouTube channel ID
            max_results: Maximum number of videos to retrieve
            exclude_shorts: Whether to exclude YouTube Shorts (videos under 60 seconds)
            
        Returns:
            List of video information (with smart shorts handling)
        """
        try:
            await self._check_rate_limit()
            
            # Calculate search limit accounting for shorts filtering
            search_multiplier = 4 if exclude_shorts else 1
            search_max = min((max_results or 10) * search_multiplier, 50)  # API limit is 50
            
            # First, get video IDs from channel
            search_request = self.youtube.search().list(
                part="snippet",
                channelId=channel_id,
                type="video",
                order="date",
                maxResults=search_max
            )
            
            search_response = search_request.execute()
            self._record_request()
            
            if not search_response.get("items"):
                logger.warning(f"No videos found for channel: {channel_id}")
                return []
            
            # Extract video IDs
            video_ids = [item["id"]["videoId"] for item in search_response["items"]]
            
            # Get detailed video information in batches (API allows max 50 IDs per request)
            all_videos = []
            for i in range(0, len(video_ids), 50):
                batch_ids = video_ids[i:i+50]
                
                await self._check_rate_limit()
                
                videos_request = self.youtube.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(batch_ids)
                )
                
                videos_response = videos_request.execute()
                self._record_request()
                all_videos.extend(videos_response.get("items", []))
            
            # Prepare lists for categorizing videos
            regular_videos = []
            shorts_videos = []
            
            for video in all_videos:
                snippet = video.get("snippet", {})
                statistics = video.get("statistics", {})
                content_details = video.get("contentDetails", {})
                
                duration_str = content_details.get("duration", "")
                duration_seconds = self._parse_duration_to_seconds(duration_str)
                
                video_info = {
                    "id": video.get("id", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "duration": duration_str,
                    "duration_seconds": duration_seconds,
                    "view_count": int(statistics.get("viewCount", 0)),
                    "like_count": int(statistics.get("likeCount", 0)),
                    "comment_count": int(statistics.get("commentCount", 0)),
                    "is_short": duration_seconds > 0 and duration_seconds <= 60  # Enhanced shorts detection
                }
                
                # Enhanced shorts detection
                is_short = (
                    duration_seconds <= 60 and duration_seconds > 0  # Duration-based
                    or "#shorts" in snippet.get("description", "").lower()  # Tag-based
                    or "#short" in snippet.get("description", "").lower()
                    or "shorts" in snippet.get("title", "").lower()  # Title-based
                )
                
                video_info["is_short"] = is_short
                
                # Categorize videos
                if is_short:
                    shorts_videos.append(video_info)
                    logger.debug(f"Detected Short: {snippet.get('title', 'Unknown')} ({duration_seconds}s)")
                else:
                    regular_videos.append(video_info)
                    logger.debug(f"Regular video: {snippet.get('title', 'Unknown')} ({duration_seconds}s)")
            
            # Smart selection logic
            if exclude_shorts:
                if regular_videos:
                    selected_videos = regular_videos[:max_results or 10]
                    logger.info(f"✅ Selected {len(selected_videos)} regular videos (excluded {len(shorts_videos)} shorts)")
                else:
                    logger.warning("⚠️ No regular videos found - channel appears to have only YouTube Shorts")
                    if shorts_videos:
                        selected_videos = shorts_videos[:max_results or 10]
                        logger.info(f"📱 Including {len(selected_videos)} Shorts as fallback")
                    else:
                        selected_videos = []
            else:
                # Include all videos when not excluding shorts
                all_categorized = regular_videos + shorts_videos
                selected_videos = all_categorized[:max_results or 10]
                logger.info(f"✅ Selected {len(selected_videos)} videos ({len(regular_videos)} regular, {len(shorts_videos)} shorts)")
            
            return selected_videos
            
        except HttpError as e:
            logger.error(f"YouTube API HTTP error getting channel videos: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get channel videos: {e}")
            return []
    
    async def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific video using YouTube Data API v3.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video details or None if failed
        """
        try:
            await self._check_rate_limit()
            
            request = self.youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=video_id
            )
            
            response = request.execute()
            self._record_request()
            
            if not response.get("items"):
                logger.warning(f"No video found with ID: {video_id}")
                return None
            
            video = response["items"][0]
            snippet = video.get("snippet", {})
            statistics = video.get("statistics", {})
            content_details = video.get("contentDetails", {})
            
            duration_str = content_details.get("duration", "")
            duration_seconds = self._parse_duration_to_seconds(duration_str)
            
            return {
                "id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel_id": snippet.get("channelId", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "duration": duration_str,
                "duration_seconds": duration_seconds,
                "view_count": int(statistics.get("viewCount", 0)),
                "like_count": int(statistics.get("likeCount", 0)),
                "comment_count": int(statistics.get("commentCount", 0)),
                "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "tags": snippet.get("tags", []),
                "category_id": snippet.get("categoryId", ""),
                "default_language": snippet.get("defaultLanguage", ""),
                "default_audio_language": snippet.get("defaultAudioLanguage", ""),
                "is_short": duration_seconds > 0 and duration_seconds <= 60  # Enhanced shorts detection
            }
            
        except HttpError as e:
            logger.error(f"YouTube API HTTP error getting video details: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get video details: {e}")
            return None
    
    async def get_video_comments(self, video_id: str, max_results: int = None) -> List[Dict[str, Any]]:
        """
        Get comments for a video using YouTube Data API v3 commentThreads endpoint.
        
        Args:
            video_id: YouTube video ID
            max_results: Maximum number of comments to retrieve (defaults to settings.MAX_COMMENTS_PER_VIDEO)
            
        Returns:
            List of comments
        """
        try:
            from app.config import settings
            if max_results is None:
                max_results = settings.MAX_COMMENTS_PER_VIDEO
                
            comments = []
            next_page_token = None
            
            while len(comments) < max_results:
                await self._check_rate_limit()
                
                request = self.youtube.commentThreads().list(
                    part="snippet,replies",
                    videoId=video_id,
                    order="relevance",
                    maxResults=min(settings.MAX_COMMENTS_PER_VIDEO, max_results - len(comments)),
                    pageToken=next_page_token
                )
                
                response = request.execute()
                self._record_request()
                
                if not response.get("items"):
                    break
                
                for item in response["items"]:
                    # Get top-level comment
                    comment_snippet = item["snippet"]["topLevelComment"]["snippet"]
                    
                    comment_info = {
                        "id": item.get("id", ""),
                        "text": comment_snippet.get("textDisplay", ""),
                        "text_original": comment_snippet.get("textOriginal", ""),
                        "author": comment_snippet.get("authorDisplayName", ""),
                        "author_channel_id": comment_snippet.get("authorChannelId", {}).get("value", ""),
                        "author_channel_url": comment_snippet.get("authorChannelUrl", ""),
                        "author_profile_image_url": comment_snippet.get("authorProfileImageUrl", ""),
                        "like_count": int(comment_snippet.get("likeCount", 0)),
                        "published_at": comment_snippet.get("publishedAt", ""),
                        "updated_at": comment_snippet.get("updatedAt", ""),
                        "reply_count": int(item["snippet"].get("totalReplyCount", 0)),
                        "can_rate": comment_snippet.get("canRate", False),
                        "viewer_rating": comment_snippet.get("viewerRating", "none"),
                        "moderation_status": comment_snippet.get("moderationStatus", ""),
                        "replies": []
                    }
                    
                    # Get replies if available
                    if "replies" in item and item["replies"].get("comments"):
                        for reply in item["replies"]["comments"]:
                            reply_snippet = reply["snippet"]
                            reply_info = {
                                "id": reply.get("id", ""),
                                "text": reply_snippet.get("textDisplay", ""),
                                "author": reply_snippet.get("authorDisplayName", ""),
                                "like_count": int(reply_snippet.get("likeCount", 0)),
                                "published_at": reply_snippet.get("publishedAt", ""),
                                "parent_id": reply_snippet.get("parentId", "")
                            }
                            comment_info["replies"].append(reply_info)
                    
                    comments.append(comment_info)
                
                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break
            
            return comments
            
        except HttpError as e:
            if e.resp.status == 403:
                logger.warning(f"Comments disabled for video {video_id}")
            else:
                logger.error(f"YouTube API HTTP error getting video comments: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get video comments: {e}")
            return []
    
    async def post_comment(self, video_id: str, text: str) -> Dict[str, Any]:
        """
        Post a comment to a video using YouTube Data API v3.
        
        Requires OAuth2 authentication and proper scopes.
        
        Args:
            video_id: YouTube video ID
            text: Comment text
            
        Returns:
            Dictionary with success status, comment ID, and comment URL
        """
        try:
            logger.info(f"📤 Preparing to post comment to video {video_id}: {text[:50]}...")
            
            # Check if comment posting is enabled
            if not settings.can_post_comments():
                if not settings.ENABLE_COMMENT_POSTING:
                    logger.info(f"💭 Comment posting disabled in settings (safety feature)")
                    return {"success": False, "error": "Comment posting disabled in settings"}
                elif not settings.has_oauth2_credentials():
                    logger.error(f"❌ OAuth2 credentials not configured for comment posting")
                    return {"success": False, "error": "OAuth2 credentials not configured"}
                else:
                    logger.error(f"❌ Comment posting not properly configured")
                    return {"success": False, "error": "Comment posting not properly configured"}
            
            # Check OAuth2 authentication
            if not self.is_authenticated_for_posting():
                logger.error(f"❌ Not authenticated for comment posting. Run OAuth2 flow first.")
                return {"success": False, "error": "Not authenticated for comment posting"}
            
            # Validate comment length
            if len(text) > settings.COMMENT_MAX_LENGTH:
                logger.error(f"❌ Comment too long ({len(text)} > {settings.COMMENT_MAX_LENGTH} chars)")
                return {"success": False, "error": f"Comment too long ({len(text)} > {settings.COMMENT_MAX_LENGTH} chars)"}
            
            if len(text) < settings.COMMENT_MIN_LENGTH:
                logger.error(f"❌ Comment too short ({len(text)} < {settings.COMMENT_MIN_LENGTH} chars)")
                return {"success": False, "error": f"Comment too short ({len(text)} < {settings.COMMENT_MIN_LENGTH} chars)"}
            
            # Rate limiting check
            await self._check_rate_limit()
            
            # Post comment using OAuth2 authenticated service
            request = self.youtube_oauth.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {
                                "textOriginal": text
                            }
                        }
                    }
                }
            )
            
            response = request.execute()
            self._record_request()
            
            comment_id = response.get("id", "")
            comment_url = f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"
            
            logger.info(f"✅ Comment posted successfully! Comment ID: {comment_id}")
            
            # Add delay to respect rate limits
            if settings.COMMENT_POST_DELAY > 0:
                await asyncio.sleep(settings.COMMENT_POST_DELAY)
            
            return {
                "success": True,
                "comment_id": comment_id,
                "comment_url": comment_url,
                "video_id": video_id,
                "posted_at": datetime.now().isoformat()
            }
            
        except HttpError as e:
            error_details = e.error_details[0] if e.error_details else {}
            error_reason = error_details.get("reason", "unknown")
            
            if error_reason == "commentDisabled":
                logger.error(f"❌ Comments are disabled for video {video_id}")
                return {"success": False, "error": "Comments are disabled for this video"}
            elif error_reason == "quotaExceeded":
                logger.error(f"❌ YouTube API quota exceeded")
                return {"success": False, "error": "YouTube API quota exceeded"}
            elif error_reason == "forbidden":
                logger.error(f"❌ Not authorized to post comments (check OAuth2 scopes)")
                return {"success": False, "error": "Not authorized to post comments"}
            else:
                logger.error(f"❌ YouTube API HTTP error posting comment: {e}")
                return {"success": False, "error": f"YouTube API error: {error_reason}"}
            
        except Exception as e:
            logger.error(f"❌ Failed to post comment: {e}")
            return {"success": False, "error": str(e)}
    
    # Transcript functionality removed - using video descriptions instead
    
    async def extract_channel_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract channel ID from various YouTube URL formats with improved resolution.
        
        Args:
            url: YouTube URL
            
        Returns:
            Channel ID or None if not found
        """
        try:
            from ..utils.validators import YouTubeValidator
            
            # Use improved validator
            channel_identifier = YouTubeValidator.extract_channel_id(url)
            if not channel_identifier:
                return None
                
            # Handle special video-based resolution
            if channel_identifier.startswith('video:'):
                video_id = channel_identifier.replace('video:', '')
                return self._get_channel_id_from_video(video_id)
                    
            # If it's already a proper channel ID (UC format), return it
            if channel_identifier.startswith('UC') and len(channel_identifier) == 24:
                        return channel_identifier
                    
            # Resolve username/handle to channel ID
            resolved_id = self._resolve_channel_identifier(channel_identifier)
            if resolved_id:
                return resolved_id
                
            # Fallback: try direct channel lookup
            resolved_id = await self._resolve_channel_by_name(channel_identifier)
            return resolved_id
            
        except Exception as e:
            logger.error(f"Failed to extract channel ID from URL {url}: {e}")
            return None

    def _get_channel_id_from_video(self, video_id: str) -> Optional[str]:
        """
        Get channel ID from a video ID using YouTube API.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Channel ID or None if not found
        """
        try:
            request = self.youtube.videos().list(
                part="snippet",
                id=video_id
            )
            
            response = request.execute()
            self._record_request()
            
            if response.get("items"):
                channel_id = response["items"][0]["snippet"]["channelId"]
                logger.info(f"Resolved video {video_id} to channel {channel_id}")
                return channel_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get channel ID from video {video_id}: {e}")
            return None
    
    def _resolve_channel_identifier(self, identifier: str) -> Optional[str]:
        """
        Resolve username/handle to channel ID using YouTube API with multiple strategies.
        
        Args:
            identifier: Username, handle, or custom URL
            
        Returns:
            Channel ID or None if not found
        """
        try:
            # Strategy 1: Try forUsername parameter (for legacy usernames)
            try:
                request = self.youtube.channels().list(
                    part="id",
                    forUsername=identifier
                )
                response = request.execute()
                self._record_request()
                
                if response.get("items"):
                    channel_id = response["items"][0]["id"]
                    logger.info(f"Resolved username '{identifier}' to channel ID: {channel_id}")
                    return channel_id
            except Exception as e:
                logger.debug(f"forUsername lookup failed for {identifier}: {e}")
            
            # Strategy 2: Search for the channel by exact name match
            request = self.youtube.search().list(
                part="snippet",
                type="channel",
                q=f'"{identifier}"',  # Exact match
                maxResults=5
            )
            
            response = request.execute()
            self._record_request()
            
            # Look for exact matches first
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                channel_title = snippet.get("title", "").lower()
                custom_url = snippet.get("customUrl", "").lower()
                
                # Check for exact matches
                if (channel_title == identifier.lower() or 
                    custom_url == identifier.lower() or
                    custom_url == f"@{identifier.lower()}"):
                    
                    channel_id = item["id"]["channelId"]
                    logger.info(f"Found exact match for '{identifier}': {channel_id}")
                    return channel_id
            
            # Strategy 3: Broader search if no exact match
            request = self.youtube.search().list(
                part="snippet",
                type="channel",
                q=identifier,
                maxResults=1
            )
            
            response = request.execute()
            self._record_request()
            
            if response.get("items"):
                channel_id = response["items"][0]["id"]["channelId"]
                logger.info(f"Found approximate match for '{identifier}': {channel_id}")
                return channel_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to resolve channel identifier {identifier}: {e}")
            return None
    
    async def _resolve_channel_by_name(self, name: str) -> Optional[str]:
        """
        Alternative channel resolution method using channel name.
        
        Args:
            name: Channel name or handle
            
        Returns:
            Channel ID or None if not found
        """
        try:
            await self._check_rate_limit()
            
            # Clean the name
            clean_name = name.lstrip('@').strip()
            
            # Try multiple search variations
            search_queries = [
                f'"{clean_name}"',  # Exact match
                clean_name,         # Partial match
                f"@{clean_name}"    # Handle format
            ]
            
            for query in search_queries:
                request = self.youtube.search().list(
                    part="snippet",
                    type="channel",
                    q=query,
                    maxResults=3
                )
                
                response = request.execute()
                self._record_request()
                
                for item in response.get("items", []):
                    snippet = item.get("snippet", {})
                    if snippet.get("title", "").lower() == clean_name.lower():
                        channel_id = item["id"]["channelId"]
                        logger.info(f"Resolved channel name '{name}' to ID: {channel_id}")
                        return channel_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to resolve channel by name {name}: {e}")
            return None
    
    async def search_channels(self, query: str, max_results: int = None) -> List[Dict[str, Any]]:
        """
        Search for channels using YouTube Data API v3.
        
        Args:
            query: Search query
            max_results: Maximum number of results (defaults to settings.CHANNEL_PARSER_MAX_VIDEOS)
            
        Returns:
            List of channel information
        """
        try:
            from app.config import settings
            if max_results is None:
                max_results = settings.CHANNEL_PARSER_MAX_VIDEOS
                
            await self._check_rate_limit()
            
            request = self.youtube.search().list(
                part="snippet",
                type="channel",
                q=query,
                maxResults=max_results
            )
            
            response = request.execute()
            self._record_request()
            
            channels = []
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                
                channel_info = {
                    "id": item.get("id", {}).get("channelId", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "published_at": snippet.get("publishedAt", "")
                }
                
                channels.append(channel_info)
            
            return channels
            
        except HttpError as e:
            logger.error(f"YouTube API HTTP error searching channels: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to search channels: {e}")
            return []
    
    def get_api_quota_cost(self, operation: str) -> int:
        """
        Get the quota cost for different YouTube API operations.
        
        Args:
            operation: API operation name
            
        Returns:
            Quota cost units
        """
        # YouTube API v3 quota costs
        quota_costs = {
            "channels": 1,
            "videos": 1,
            "search": 100,
            "commentThreads": 1,
            "comments": 1,
            "commentThreads_insert": 50,
            "comments_insert": 50
        }
        
        return quota_costs.get(operation, 1)
    
    def close(self):
        """Close the YouTube service (placeholder for cleanup if needed)."""
        logger.info("YouTube service closed") 
    
    async def get_comment_details(self, comment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific comment including engagement metrics.
        
        Args:
            comment_id: YouTube comment ID
            
        Returns:
            Comment details with engagement metrics or None if not found
        """
        try:
            await self._check_rate_limit()
            
            # Get comment details using the comments.list API
            response = self.youtube.comments().list(
                part='snippet',
                id=comment_id,
                textFormat='plainText'
            ).execute()
            
            self._record_request()
            
            if not response.get('items'):
                logger.warning(f"Comment not found: {comment_id}")
                return None
            
            comment_item = response['items'][0]
            snippet = comment_item['snippet']
            
            # Extract engagement metrics
            engagement_data = {
                'comment_id': comment_id,
                'like_count': snippet.get('likeCount', 0),
                'reply_count': 0,  # Direct replies count from API if available
                'text_display': snippet.get('textDisplay', ''),
                'text_original': snippet.get('textOriginal', ''),
                'author_display_name': snippet.get('authorDisplayName', ''),
                'published_at': snippet.get('publishedAt', ''),
                'updated_at': snippet.get('updatedAt', ''),
                'video_id': snippet.get('videoId', ''),
                'channel_id': snippet.get('channelId', ''),
                'parent_id': snippet.get('parentId'),  # If this is a reply
                'can_rate': snippet.get('canRate', False),
                'viewer_rating': snippet.get('viewerRating', 'none'),
                'moderation_status': snippet.get('moderationStatus', 'published')
            }
            
            # If this is a top-level comment, get reply count
            if not snippet.get('parentId'):
                try:
                    # Get replies to this comment to count them
                    replies_response = self.youtube.comments().list(
                        part='snippet',
                        parentId=comment_id,
                        maxResults=1  # We just need to know if there are replies
                    ).execute()
                    
                    # The total count might be in pageInfo or we need to count manually
                    page_info = replies_response.get('pageInfo', {})
                    engagement_data['reply_count'] = page_info.get('totalResults', len(replies_response.get('items', [])))
                    
                except HttpError as e:
                    # Some comments may not allow replies or API may not support this
                    logger.debug(f"Could not get reply count for comment {comment_id}: {e}")
                    engagement_data['reply_count'] = 0
            
            logger.debug(f"Retrieved engagement data for comment {comment_id}: {engagement_data['like_count']} likes, {engagement_data['reply_count']} replies")
            
            return engagement_data
            
        except HttpError as e:
            error_code = e.resp.status if e.resp else 'unknown'
            error_reason = ""
            
            # Extract more detailed error information
            if e.error_details:
                error_reason = e.error_details[0].get('reason', '')
            
            logger.error(f"YouTube API error getting comment details for {comment_id}: {e} (Status: {error_code}, Reason: {error_reason})")
            
            if error_code == 403:
                if error_reason == 'quotaExceeded':
                    logger.warning("API quota exceeded - temporary issue")
                else:
                    logger.warning("Insufficient permissions or forbidden access")
            elif error_code == 404:
                logger.warning(f"Comment {comment_id} not found or deleted - permanent issue")
            elif error_code == 429:
                logger.warning("Rate limited by YouTube API - temporary issue")
            
            # Return None but let the metrics service handle the error interpretation
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error getting comment details for {comment_id}: {e}")
            return None
    
    def clear_oauth2_credentials(self) -> bool:
        """
        Clear stored OAuth2 credentials and disable authenticated service.
        
        Returns:
            True if credentials were cleared successfully
        """
        try:
            # Clear in-memory credentials
            self.credentials = None
            self.youtube_oauth = None
            
            # Remove credentials file if it exists
            if os.path.exists(self.credentials_file):
                os.remove(self.credentials_file)
                logger.info(f"Removed OAuth2 credentials file: {self.credentials_file}")
            
            logger.info("OAuth2 credentials cleared successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear OAuth2 credentials: {e}")
            return False 