"""
Validation utilities for YouTube Comment Automation Bot
"""

import re
from typing import Optional, Tuple, List
from urllib.parse import urlparse, parse_qs

from .logging_config import get_logger

logger = get_logger(__name__)


class YouTubeValidator:
    """YouTube URL and content validation utilities"""
    
    # Comprehensive YouTube URL patterns with better regex
    CHANNEL_URL_PATTERNS = [
        # Standard channel URLs
        r'(?:youtube\.com|youtu\.be)/channel/([a-zA-Z0-9_-]{24})',  # UC channel IDs (24 chars)
        r'youtube\.com/c/([a-zA-Z0-9_.-]+)',                       # Custom URLs
        r'youtube\.com/user/([a-zA-Z0-9_.-]+)',                    # Legacy usernames  
        r'youtube\.com/@([a-zA-Z0-9_.-]+)',                        # New handle format
    ]
    
    VIDEO_URL_PATTERNS = [
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',            # Standard watch URLs
        r'youtu\.be/([a-zA-Z0-9_-]{11})',                          # Short URLs
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',                 # Embed URLs
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',                     # Old format
    ]
    
    @staticmethod
    def validate_youtube_url(url: str) -> bool:
        """
        Validate if URL is a valid YouTube URL
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid YouTube URL, False otherwise
        """
        try:
            if not url or not url.strip():
                return False
                
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            parsed = urlparse(url)
            if not parsed.netloc:
                return False
            
            # Check for YouTube domains
            valid_domains = ['youtube.com', 'www.youtube.com', 'youtu.be', 'www.youtu.be', 'm.youtube.com']
            return parsed.netloc.lower() in valid_domains
            
        except Exception as e:
            logger.error(f"Error validating YouTube URL {url}: {e}")
            return False

    @staticmethod 
    def extract_multiple_urls(text: str) -> List[str]:
        """
        Extract multiple YouTube URLs from text input
        
        Args:
            text: Text containing one or more YouTube URLs
            
        Returns:
            List of validated YouTube URLs
        """
        try:
            # Split by common delimiters
            potential_urls = []
            
            # Split by newlines, commas, spaces, semicolons
            for delimiter in ['\n', ',', ';', ' ']:
                if delimiter in text:
                    potential_urls.extend([url.strip() for url in text.split(delimiter)])
                    break
            else:
                # No delimiter found, treat as single URL
                potential_urls = [text.strip()]
            
            # Clean and validate URLs
            valid_urls = []
            seen_urls = set()  # Track URLs to prevent duplicates
            
            for url in potential_urls:
                url = url.strip()
                if url and YouTubeValidator.validate_youtube_url(url):
                    # Ensure proper protocol
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    
                    # Normalize URL for duplicate detection
                    normalized_url = url.lower().split('?')[0].split('#')[0]  # Remove query params and fragments
                    
                    if normalized_url not in seen_urls:
                        valid_urls.append(url)
                        seen_urls.add(normalized_url)
                    else:
                        logger.info(f"Skipping duplicate URL: {url}")
                    
            return valid_urls
            
        except Exception as e:
            logger.error(f"Error extracting multiple URLs from text: {e}")
            return []
    
    @staticmethod
    def extract_channel_id(url: str) -> Optional[str]:
        """
        Extract channel ID from YouTube channel URL with improved accuracy
        
        Args:
            url: YouTube channel URL
            
        Returns:
            Channel ID/identifier if found, None otherwise
        """
        try:
            if not YouTubeValidator.validate_youtube_url(url):
                return None
            
            # Normalize URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            logger.debug(f"Extracting channel ID from: {url}")
            
            # Try each pattern in order of specificity
            for i, pattern in enumerate(YouTubeValidator.CHANNEL_URL_PATTERNS):
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    channel_identifier = match.group(1)
                    logger.info(f"Extracted channel identifier '{channel_identifier}' using pattern {i+1}")
                    
                    # Validate channel ID format
                    if YouTubeValidator.validate_channel_id(channel_identifier):
                        return channel_identifier
                    else:
                        logger.warning(f"Invalid channel identifier format: {channel_identifier}")
                        continue
            
            # Special handling for video URLs - extract channel from video
            video_id = YouTubeValidator.extract_video_id(url)
            if video_id:
                logger.info(f"Found video ID {video_id} in URL, will need to resolve channel via API")
                return f"video:{video_id}"  # Special marker for video-based resolution
            
            logger.warning(f"Could not extract channel ID from URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting channel ID from {url}: {e}")
            return None
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """
        Extract video ID from YouTube video URL with improved patterns
        
        Args:
            url: YouTube video URL
            
        Returns:
            Video ID if found, None otherwise
        """
        try:
            if not YouTubeValidator.validate_youtube_url(url):
                return None
            
            # Try each video pattern
            for pattern in YouTubeValidator.VIDEO_URL_PATTERNS:
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    video_id = match.group(1)
                    if YouTubeValidator.validate_video_id(video_id):
                        logger.info(f"Extracted video ID: {video_id}")
                    return video_id
            
            # Try query parameters for watch URLs
            parsed = urlparse(url)
            if 'v' in parse_qs(parsed.query):
                video_id = parse_qs(parsed.query)['v'][0]
                if YouTubeValidator.validate_video_id(video_id):
                    logger.info(f"Extracted video ID from query: {video_id}")
                    return video_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting video ID from {url}: {e}")
            return None
    
    @staticmethod
    def validate_channel_id(channel_id: str) -> bool:
        """
        Validate YouTube channel ID format with enhanced checks
        
        Args:
            channel_id: Channel ID to validate
            
        Returns:
            True if valid format, False otherwise
        """
        if not channel_id:
            return False
        
        # YouTube channel IDs (24 characters starting with UC)
        if len(channel_id) == 24 and channel_id.startswith('UC') and re.match(r'^[a-zA-Z0-9_-]+$', channel_id):
            return True
        
        # Handle/username formats (alphanumeric, dots, hyphens, underscores)
        if 3 <= len(channel_id) <= 30 and re.match(r'^[a-zA-Z0-9._-]+$', channel_id):
            return True
        
        return False
    
    @staticmethod
    def validate_video_id(video_id: str) -> bool:
        """
        Validate YouTube video ID format
        
        Args:
            video_id: Video ID to validate
            
        Returns:
            True if valid format, False otherwise
        """
        if not video_id:
            return False
        
        # YouTube video IDs are exactly 11 characters
        return len(video_id) == 11 and re.match(r'^[a-zA-Z0-9_-]+$', video_id)


class ContentValidator:
    """Content validation utilities"""
    
    @staticmethod
    def validate_comment_content(comment: str, max_length: int = 500) -> Tuple[bool, str]:
        """
        Validate comment content
        
        Args:
            comment: Comment text to validate
            max_length: Maximum allowed length
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not comment or not comment.strip():
            return False, "Comment cannot be empty"
        
        if len(comment) > max_length:
            return False, f"Comment exceeds maximum length of {max_length} characters"
        
        # Check for prohibited content patterns
        prohibited_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',  # URLs
            r'@[a-zA-Z0-9_]+',  # @ mentions
            r'#[a-zA-Z0-9_]+',  # Hashtags
        ]
        
        for pattern in prohibited_patterns:
            if re.search(pattern, comment, re.IGNORECASE):
                return False, f"Comment contains prohibited content: {pattern}"
        
        return True, ""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename by removing invalid characters
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Replace spaces with underscores
        sanitized = sanitized.replace(' ', '_')
        
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        return sanitized
    
    @staticmethod
    def validate_telegram_user_id(user_id: str) -> bool:
        """
        Validate Telegram user ID format
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if valid format, False otherwise
        """
        try:
            # Telegram user IDs are positive integers
            user_id_int = int(user_id)
            return user_id_int > 0
        except (ValueError, TypeError):
            return False


# Create validator instances
youtube_validator = YouTubeValidator()
content_validator = ContentValidator()

# Convenience functions for backwards compatibility
def validate_youtube_url(url: str) -> bool:
    """Convenience function for backwards compatibility"""
    return YouTubeValidator.validate_youtube_url(url)

def extract_channel_id(url: str) -> Optional[str]:
    """Convenience function for backwards compatibility"""
    return YouTubeValidator.extract_channel_id(url)

def extract_video_id(url: str) -> Optional[str]:
    """Convenience function for backwards compatibility"""
    return YouTubeValidator.extract_video_id(url)

def validate_channel_id(channel_id: str) -> bool:
    """Convenience function for backwards compatibility"""
    return YouTubeValidator.validate_channel_id(channel_id)

def validate_video_id(video_id: str) -> bool:
    """Convenience function for backwards compatibility"""
    return YouTubeValidator.validate_video_id(video_id)

def validate_comment_content(comment: str, max_length: int = 500) -> Tuple[bool, str]:
    """Convenience function for backwards compatibility"""
    return ContentValidator.validate_comment_content(comment, max_length)

def sanitize_filename(filename: str) -> str:
    """Convenience function for backwards compatibility"""
    return ContentValidator.sanitize_filename(filename)

def validate_telegram_user_id(user_id: str) -> bool:
    """Convenience function for backwards compatibility"""
    return ContentValidator.validate_telegram_user_id(user_id)

def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for Telegram MarkdownV2
    """
    # Characters that need to be escaped in MarkdownV2
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def escape_markdown(text: str) -> str:
    """
    Escape special characters for Telegram Markdown (legacy).
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for Telegram Markdown
    """
    # Characters that need to be escaped in Markdown
    escape_chars = ['*', '_', '`', '[', ']']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def safe_telegram_message(text: str, max_length: int = 4096) -> str:
    """
    Create a safe Telegram message by escaping special characters and truncating.
    
    Args:
        text: Message text
        max_length: Maximum message length (Telegram limit is 4096)
        
    Returns:
        Safe message text
    """
    # Escape markdown characters
    safe_text = escape_markdown(text)
    
    # Truncate if too long
    if len(safe_text) > max_length:
        safe_text = safe_text[:max_length - 3] + "..."
    
    return safe_text 