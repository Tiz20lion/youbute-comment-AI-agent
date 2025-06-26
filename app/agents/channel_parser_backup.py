"""
Agent 1: Channel Parser

This agent handles:
- YouTube channel URL parsing and validation (supports multiple URLs)
- Channel ID extraction from various URL formats
- Channel information retrieval
- Top videos discovery and metadata extraction (excluding shorts by default)
- Initial workflow state setup
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from ..services.youtube_service import YouTubeService
from ..utils.logging_config import get_logger
from ..utils.validators import YouTubeValidator
from ..utils.file_handler import FileHandler
from ..models.schemas import ProcessingStatus

logger = get_logger(__name__)


class ChannelParserAgent:
    """Agent responsible for parsing YouTube channels and extracting basic information."""
    
    def __init__(self):
        """Initialize the Channel Parser Agent."""
        self.name = "channel_parser"
        self.description = "Parses YouTube channel URLs (single or multiple) and extracts top videos"
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the channel parsing workflow with support for multiple URLs.
        
        Args:
            state: Current workflow state containing channel_url(s)
            
        Returns:
            Updated workflow state with channel info and videos
        """
        try:
            channel_url_input = state.get("channel_url", "")
            logger.info(f"🔍 Channel Parser starting for input: {channel_url_input}")
            
            # Extract multiple URLs from input
            channel_urls = YouTubeValidator.extract_multiple_urls(channel_url_input)
            if not channel_urls:
                return self._create_error_state(state, f"No valid YouTube URLs found in: {channel_url_input}")
            
            logger.info(f"📺 Found {len(channel_urls)} valid YouTube URL(s)")
            for i, url in enumerate(channel_urls, 1):
                logger.info(f"  {i}. {url}")
            
            # Process each URL and collect all channels
            all_channels_data = []
            processed_channels = set()  # Avoid duplicates
            
            for url_index, channel_url in enumerate(channel_urls):
                try:
                    channel_data = await self._process_single_channel(channel_url, url_index + 1)
                    if channel_data and channel_data.get("channel_id"):
                        channel_id = channel_data["channel_id"]
                        if channel_id not in processed_channels:
                            all_channels_data.append(channel_data)
                            processed_channels.add(channel_id)
                            logger.info(f"✅ Successfully processed channel {channel_id}")
                        else:
                            logger.info(f"⚠️ Skipping duplicate channel {channel_id}")
                    else:
                        logger.warning(f"⚠️ Failed to process URL: {channel_url}")
                except Exception as e:
                    logger.error(f"❌ Error processing URL {channel_url}: {e}")
                    continue
            
            if not all_channels_data:
                return self._create_error_state(state, "Failed to process any valid channels from the provided URLs")
            
            # Combine all channel data
            combined_state = await self._combine_channel_data(state, all_channels_data)
            
            logger.info(f"✅ Channel Parser completed successfully! Processed {len(all_channels_data)} channel(s)")
            return combined_state
            
        except Exception as e:
            logger.error(f"❌ Channel Parser failed: {str(e)}")
            return self._create_error_state(state, str(e))
    
    async def _process_single_channel(self, channel_url: str, url_number: int) -> Optional[Dict[str, Any]]:
        """
        Process a single channel URL and extract its information.
        
        Args:
            channel_url: Single YouTube channel URL
            url_number: URL sequence number for logging
            
        Returns:
            Channel data dictionary or None if failed
        """
        try:
            logger.info(f"🔍 Processing URL #{url_number}: {channel_url}")
            
            # Validate YouTube URL
            if not YouTubeValidator.validate_youtube_url(channel_url):
                logger.error(f"Invalid YouTube URL: {channel_url}")
                return None
            
            # Extract channel identifier
            channel_identifier = YouTubeValidator.extract_channel_id(channel_url)
            if not channel_identifier:
                logger.error(f"Could not extract channel ID from: {channel_url}")
                return None
            
            logger.info(f"📺 Extracted channel identifier: {channel_identifier}")
            
            # Initialize YouTube service
            youtube_service = YouTubeService()
            
            # Resolve channel identifier to actual channel ID
            channel_id = await self._resolve_channel_id(youtube_service, channel_identifier, channel_url)
            if not channel_id:
                logger.error(f"Could not resolve channel identifier '{channel_identifier}' to channel ID")
                return None
            
            # Get channel information
            channel_info = await youtube_service.get_channel_info(channel_id)
            if not channel_info:
                logger.error(f"Could not fetch channel info for ID: {channel_id}")
                return None
            
            logger.info(f"📋 Channel info retrieved: {channel_info.get('title', 'Unknown')}")
            
            # Get top videos from channel (exclude shorts by default)
            from app.config import settings
            videos = await youtube_service.get_channel_videos(
                channel_id, 
                max_results=settings.CHANNEL_PARSER_MAX_VIDEOS,
                exclude_shorts=True  # Explicitly exclude YouTube Shorts
            )
            
            if not videos:
                logger.warning(f"No videos found for channel: {channel_id}")
                # Don't fail completely, return channel info without videos
            
            logger.info(f"🎬 Found {len(videos)} videos from channel (shorts excluded)")
            
            # Process videos and add initial structure
            processed_videos = []
            for i, video in enumerate(videos, 1):
                processed_video = {
                    # Basic video info
                    "video_id": video.get("id", ""),
                    "title": video.get("title", ""),
                    "description": video.get("description", ""),
                    "url": f"https://www.youtube.com/watch?v={video.get('id', '')}",
                    "thumbnail_url": video.get("thumbnail_url", ""),
                    "published_at": video.get("published_at", ""),
                    "duration": video.get("duration", ""),
                    "duration_seconds": video.get("duration_seconds", 0),
                    "view_count": video.get("view_count", 0),
                    "like_count": video.get("like_count", 0),
                    "comment_count": video.get("comment_count", 0),
                    "is_short": video.get("is_short", False),
                    
                    # Processing status flags
                    "description_extracted": False,
                    "content_scraped": False,
                    "content_analyzed": False,
                    "comment_generated": False,
                    "comment_posted": False,
                    
                    # Data containers (to be filled by other agents)
                    "transcript": "",
                    "comments": [],
                    "analysis": {},
                    "generated_comment": "",
                    "video_suggestions": [],
                    
                    # Processing metadata
                    "status": ProcessingStatus.PENDING.value,
                    "processing_order": i,
                    "created_at": datetime.now().isoformat()
                }
                
                processed_videos.append(processed_video)
                duration_info = f" ({video.get('duration_seconds', 0)}s)" if video.get('duration_seconds') else ""
                logger.info(f"  {i}. {video.get('title', 'Unknown Title')[:50]}...{duration_info}")
            
            # Return channel data
            return {
                "channel_id": channel_id,
                "channel_name": channel_info.get("title", ""),
                "channel_handle": channel_info.get("handle", ""),
                "channel_description": channel_info.get("description", ""),
                "channel_subscriber_count": channel_info.get("subscriber_count", 0),
                "channel_video_count": channel_info.get("video_count", 0),
                "channel_view_count": channel_info.get("view_count", 0),
                "channel_url": channel_url,
                "videos": processed_videos,
                "channel_info": channel_info
            }
            
        except Exception as e:
            logger.error(f"Failed to process channel URL {channel_url}: {e}")
            return None
    
    async def _resolve_channel_id(self, youtube_service: YouTubeService, channel_identifier: str, original_url: str) -> Optional[str]:
        """
        Resolve channel identifier to actual channel ID using multiple strategies.
        
        Args:
            youtube_service: YouTube service instance
            channel_identifier: Channel identifier to resolve
            original_url: Original URL for reference
            
        Returns:
            Resolved channel ID or None if failed
        """
        try:
            # Handle special video-based resolution
            if channel_identifier.startswith('video:'):
                video_id = channel_identifier.replace('video:', '')
                resolved_id = youtube_service._get_channel_id_from_video(video_id)
                if resolved_id:
                    logger.info(f"🔍 Resolved video {video_id} to channel ID: {resolved_id}")
                    return resolved_id
                else:
                    logger.error(f"Failed to resolve video {video_id} to channel ID")
                    return None
            
            # If it's already a proper channel ID (UC format), return it
            if channel_identifier.startswith('UC') and len(channel_identifier) == 24:
                logger.info(f"✅ Channel ID already in proper format: {channel_identifier}")
                return channel_identifier
            
            # Resolve username/handle to channel ID
            resolved_id = youtube_service._resolve_channel_identifier(channel_identifier)
            if resolved_id:
                logger.info(f"🔍 Resolved '{channel_identifier}' to channel ID: {resolved_id}")
                return resolved_id
            
            # Fallback: try direct channel lookup
            resolved_id = await youtube_service._resolve_channel_by_name(channel_identifier)
            if resolved_id:
                logger.info(f"🔍 Resolved channel name '{channel_identifier}' to ID: {resolved_id}")
                return resolved_id
            
            logger.error(f"❌ Could not resolve channel identifier '{channel_identifier}' from URL: {original_url}")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving channel identifier {channel_identifier}: {e}")
            return None
    
    async def _combine_channel_data(self, state: Dict[str, Any], channels_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combine data from multiple channels into a unified workflow state.
        
        Args:
            state: Current workflow state
            channels_data: List of channel data dictionaries
            
        Returns:
            Updated workflow state with combined channel information
        """
        try:
            # Combine all videos from all channels
            all_videos = []
            total_subscribers = 0
            total_channel_videos = 0
            total_channel_views = 0
            
            # Channel information for primary channel (first one)
            primary_channel = channels_data[0]
            
            # Combine videos and statistics
            processing_order = 1
            for channel_data in channels_data:
                channel_videos = channel_data.get("videos", [])
                for video in channel_videos:
                    video["processing_order"] = processing_order
                    processing_order += 1
                    all_videos.append(video)
                
                total_subscribers += channel_data.get("channel_subscriber_count", 0)
                total_channel_videos += channel_data.get("channel_video_count", 0)
                total_channel_views += channel_data.get("channel_view_count", 0)
            
            # Create channel summary for multiple channels
            if len(channels_data) > 1:
                channel_names = [ch.get("channel_name", "Unknown") for ch in channels_data]
                combined_name = f"Multi-Channel ({', '.join(channel_names[:3])}{'...' if len(channel_names) > 3 else ''})"
                combined_id = f"multi_{hash('_'.join([ch.get('channel_id', '') for ch in channels_data]))}"
            else:
                combined_name = primary_channel.get("channel_name", "")
                combined_id = primary_channel.get("channel_id", "")
            
            # Save channel data to files
            for channel_data in channels_data:
                try:
                    channel_id = channel_data.get("channel_id", "")
                    channel_name = channel_data.get("channel_name", "")
                    
                    await FileHandler.initialize_channel_data(
                        channel_id=channel_id,
                        channel_name=channel_name
                    )
                    
                    # Save individual channel data
                    channel_data_file = FileHandler.get_channel_data_file(channel_id, channel_name)
                    await FileHandler.update_json(channel_data_file, {
                        "channel_info": channel_data.get("channel_info", {}),
                        "videos": channel_data.get("videos", []),
                        "last_updated": datetime.now().isoformat()
                    })
                    
                    logger.info(f"💾 Channel data saved for: {channel_name}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to save data for channel {channel_data.get('channel_id', 'unknown')}: {e}")
            
            # Update workflow state
            updated_state = {
                **state,
                
                # Channel information (combined or primary)
                "channel_id": combined_id,
                "channel_name": combined_name,
                "channel_handle": primary_channel.get("channel_handle", ""),
                "channel_description": primary_channel.get("channel_description", ""),
                "channel_subscriber_count": total_subscribers,
                "channel_video_count": total_channel_videos,
                "channel_view_count": total_channel_views,
                
                # Multiple channels info
                "channels_data": channels_data,
                "total_channels_processed": len(channels_data),
                
                # Video data (combined from all channels)
                "videos": all_videos,
                
                # Workflow progress
                "current_step": "channel_parser",
                "completed_steps": state.get("completed_steps", []) + ["channel_parser"],
                "status": ProcessingStatus.PROCESSING.value,
                "progress_percentage": 15,
                
                # Statistics
                "statistics": {
                    **state.get("statistics", {}),
                    "total_channels_processed": len(channels_data),
                    "channel_videos_found": len(all_videos),
                    "total_channel_subscribers": total_subscribers,
                    "total_video_views": sum(v.get("view_count", 0) for v in all_videos),
                    "total_video_likes": sum(v.get("like_count", 0) for v in all_videos),
                    "total_video_comments": sum(v.get("comment_count", 0) for v in all_videos),
                    "shorts_excluded": sum(1 for v in all_videos if not v.get("is_short", False))
                },
                
                # Timestamps
                "channel_parser_completed_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Combined data from {len(channels_data)} channels with {len(all_videos)} total videos")
            return updated_state
            
        except Exception as e:
            logger.error(f"Failed to combine channel data: {e}")
            return self._create_error_state(state, f"Failed to combine channel data: {e}")
    
    def _create_error_state(self, current_state: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Create error state when channel parsing fails."""
        return {
            **current_state,
            "status": ProcessingStatus.FAILED.value,
            "error_message": f"Channel parsing failed: {error_message}",
            "current_step": "channel_parser",
            "failed_at": datetime.now().isoformat(),
            "progress_percentage": 0
        }
    
    async def get_channel_summary(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of channel information.
        
        Args:
            channel_id: YouTube channel ID
            
        Returns:
            Channel summary or None if failed
        """
        try:
            youtube_service = YouTubeService()
            
            # Get channel info
            channel_info = await youtube_service.get_channel_info(channel_id)
            if not channel_info:
                return None
            
            # Get basic video stats
            videos = await youtube_service.get_channel_videos(channel_id, max_results=5)
            
            return {
                "channel_id": channel_id,
                "title": channel_info.get("title", ""),
                "subscriber_count": channel_info.get("subscriber_count", 0),
                "video_count": channel_info.get("video_count", 0),
                "view_count": channel_info.get("view_count", 0),
                "recent_videos": len(videos),
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get channel summary for {channel_id}: {e}")
            return None


# LangGraph node wrapper
async def channel_parser_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node wrapper for the Channel Parser Agent.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    agent = ChannelParserAgent()
    return await agent.execute(state)


# Test function
async def test_channel_parser(channel_url: str) -> Dict[str, Any]:
    """
    Test the channel parser with a given URL.
    
    Args:
        channel_url: YouTube channel URL to test
        
    Returns:
        Test results
    """
    try:
        initial_state = {
            "channel_url": channel_url,
            "completed_steps": [],
            "statistics": {}
        }
        
        agent = ChannelParserAgent()
        result = await agent.execute(initial_state)
        
        return {
            "success": result.get("status") != ProcessingStatus.FAILED.value,
            "channel_id": result.get("channel_id"),
            "channel_name": result.get("channel_name"),
            "videos_found": len(result.get("videos", [])),
            "channels_processed": result.get("total_channels_processed", 1),
            "error": result.get("error_message"),
            "statistics": result.get("statistics", {})
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "channel_id": None,
            "channel_name": None,
            "videos_found": 0,
            "channels_processed": 0,
            "statistics": {}
        }


if __name__ == "__main__":
    # Example usage
    async def main():
        # Test with single URL
        result = await test_channel_parser("https://www.youtube.com/@mkbhd")
        print(f"Single URL test: {result}")
        
        # Test with multiple URLs
        multi_result = await test_channel_parser("""
        https://www.youtube.com/@mkbhd
        https://www.youtube.com/@unboxtherapy
        """)
        print(f"Multiple URLs test: {multi_result}")
    
    import asyncio
    asyncio.run(main()) 