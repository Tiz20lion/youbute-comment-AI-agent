"""
Agent 1: Channel Parser

This agent handles:
- YouTube channel URL parsing and validation (supports multiple URLs)
- Individual video URL processing with channel discovery
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
        self.description = "Parses YouTube channel URLs (single or multiple) and individual video URLs with channel discovery"
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the channel parsing workflow with support for multiple URLs and individual videos.
        
        Args:
            state: Current workflow state containing channel_url(s) or video URL(s)
            
        Returns:
            Updated workflow state with channel info and videos
        """
        try:
            channel_url_input = state.get("channel_url", "")
            logger.info(f"🔍 Channel Parser starting for input: {channel_url_input}")
            
            # Extract multiple URLs from input
            urls = YouTubeValidator.extract_multiple_urls(channel_url_input)
            if not urls:
                return self._create_error_state(state, f"No valid YouTube URLs found in: {channel_url_input}")
            
            logger.info(f"📺 Found {len(urls)} valid YouTube URL(s)")
            for i, url in enumerate(urls, 1):
                logger.info(f"  {i}. {url}")
            
            # Categorize URLs into videos and channels
            video_urls = []
            channel_urls = []
            
            for url in urls:
                video_id = YouTubeValidator.extract_video_id(url)
                if video_id:
                    video_urls.append(url)
                    logger.info(f"📹 Detected video URL: {url}")
                else:
                    channel_urls.append(url)
                    logger.info(f"📺 Detected channel URL: {url}")
            
            # Process all URLs and collect all channels
            all_channels_data = []
            processed_channels = set()
            processed_videos = set()  # Track processed video IDs to prevent duplicates
            
            # Process individual video URLs first
            for i, video_url in enumerate(video_urls, 1):
                try:
                    # Extract video ID to check for duplicates
                    video_id = YouTubeValidator.extract_video_id(video_url)
                    if video_id in processed_videos:
                        logger.info(f"⏭️ Skipping already processed video: {video_url}")
                        continue
                    
                    logger.info(f"🎬 Processing video URL #{i}: {video_url}")
                    video_channel_data = await self._process_video_url(video_url, i)
                    if video_channel_data and video_channel_data.get("channel_id") not in processed_channels:
                        all_channels_data.append(video_channel_data)
                        processed_channels.add(video_channel_data.get("channel_id"))
                        processed_videos.add(video_id)  # Mark video as processed
                        logger.info(f"✅ Successfully processed video URL and discovered channel")
                    else:
                        logger.warning(f"⚠️ Failed to process video URL or channel already processed")
                except Exception as e:
                    logger.error(f"❌ Error processing video URL {video_url}: {e}")
                    continue
            
            # Process channel URLs
            for i, channel_url in enumerate(channel_urls, len(video_urls) + 1):
                try:
                    channel_data = await self._process_single_channel(channel_url, i)
                    if channel_data and channel_data.get("channel_id") not in processed_channels:
                        all_channels_data.append(channel_data)
                        processed_channels.add(channel_data.get("channel_id"))
                        logger.info(f"✅ Successfully processed channel #{i}")
                    else:
                        logger.warning(f"⚠️ Failed to process channel URL or channel already processed")
                except Exception as e:
                    logger.error(f"❌ Error processing channel URL {channel_url}: {e}")
                    continue
            
            # Check if we have any successful results
            if not all_channels_data:
                return self._create_error_state(state, "Failed to process any URLs successfully")
            
            # Combine all channel data
            return await self._combine_channels_data(state, all_channels_data)
            
        except Exception as e:
            logger.error(f"Channel Parser execution failed: {e}")
            return self._create_error_state(state, f"Channel Parser failed: {str(e)}")
    
    async def _process_video_url(self, video_url: str, url_number: int) -> Optional[Dict[str, Any]]:
        """
        Process a single video URL, extract the specific video, and discover the channel's latest videos.
        
        Args:
            video_url: Single YouTube video URL
            url_number: URL sequence number for logging
            
        Returns:
            Channel data dictionary with the specific video included, or None if failed
        """
        try:
            logger.info(f"🎬 Processing video URL #{url_number}: {video_url}")
            
            # Extract video ID
            video_id = YouTubeValidator.extract_video_id(video_url)
            if not video_id:
                logger.error(f"Could not extract video ID from: {video_url}")
                return None
            
            logger.info(f"📹 Extracted video ID: {video_id}")
            
            # Initialize YouTube service
            youtube_service = YouTubeService()
            
            # Get the specific video details first
            specific_video = await youtube_service.get_video_details(video_id)
            if not specific_video:
                logger.error(f"Could not fetch video details for ID: {video_id}")
                return None
            
            logger.info(f"🎯 Retrieved specific video: {specific_video.get('title', 'Unknown')}")
            
            # Get channel ID from the video
            channel_id = specific_video.get('channel_id')
            if not channel_id:
                logger.error(f"Could not extract channel ID from video: {video_id}")
                return None
            
            logger.info(f"🔍 Discovered channel ID from video: {channel_id}")
            
            # Get channel information
            channel_info = await youtube_service.get_channel_info(channel_id)
            if not channel_info:
                logger.error(f"Could not fetch channel info for ID: {channel_id}")
                return None
            
            logger.info(f"📋 Channel info retrieved: {channel_info.get('title', 'Unknown')}")
            
            # Get latest videos from the channel (exclude shorts by default)
            from app.config import settings
            channel_videos = await youtube_service.get_channel_videos(
                channel_id, 
                max_results=settings.CHANNEL_PARSER_MAX_VIDEOS,
                exclude_shorts=True
            )
            
            logger.info(f"🎬 Found {len(channel_videos)} latest videos from channel (shorts excluded)")
            
            # Combine the specific video with channel videos, ensuring the specific video is first
            all_videos = []
            
            # Add the specific video first (marked as priority)
            processed_specific_video = {
                # Basic video info
                "video_id": specific_video.get("id", ""),
                "title": specific_video.get("title", ""),
                "description": specific_video.get("description", ""),
                "url": video_url,  # Use the original URL provided by user
                "thumbnail_url": specific_video.get("thumbnail_url", ""),
                "published_at": specific_video.get("published_at", ""),
                "duration": specific_video.get("duration", ""),
                "duration_seconds": specific_video.get("duration_seconds", 0),
                "view_count": specific_video.get("view_count", 0),
                "like_count": specific_video.get("like_count", 0),
                "comment_count": specific_video.get("comment_count", 0),
                "is_short": specific_video.get("is_short", False),
                
                # Special markers for user-requested video
                "is_user_requested": True,
                "priority_video": True,
                
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
                "processing_order": 1,  # Always first
                "created_at": datetime.now().isoformat()
            }
            
            all_videos.append(processed_specific_video)
            logger.info(f"  🎯 1. {specific_video.get('title', 'Unknown Title')[:50]}... (USER REQUESTED)")
            
            # Add channel videos (skip if it's the same as the specific video)
            processing_order = 2
            for video in channel_videos:
                if video.get("id") != video_id:  # Skip duplicate
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
                        
                        # Channel discovery markers
                        "is_user_requested": False,
                        "priority_video": False,
                        "discovered_from_video": video_id,
                        
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
                        "processing_order": processing_order,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    all_videos.append(processed_video)
                    duration_info = f" ({video.get('duration_seconds', 0)}s)" if video.get('duration_seconds') else ""
                    logger.info(f"  {processing_order}. {video.get('title', 'Unknown Title')[:50]}...{duration_info}")
                    processing_order += 1
            
            # Return channel data with video-first approach
            return {
                "channel_id": channel_id,
                "channel_name": channel_info.get("title", ""),
                "channel_handle": channel_info.get("handle", ""),
                "channel_description": channel_info.get("description", ""),
                "channel_subscriber_count": channel_info.get("subscriber_count", 0),
                "channel_video_count": channel_info.get("video_count", 0),
                "channel_view_count": channel_info.get("view_count", 0),
                "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                "original_video_url": video_url,  # Track the original video URL
                "discovery_method": "video_url",  # Mark how this channel was discovered
                "videos": all_videos,
                "channel_info": channel_info
            }
            
        except Exception as e:
            logger.error(f"Failed to process video URL {video_url}: {e}")
            return None
    
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
                    
                    # Channel discovery markers
                    "is_user_requested": False,
                    "priority_video": False,
                    
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
                "discovery_method": "channel_url",  # Mark how this channel was discovered
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
    
    async def _combine_channels_data(self, state: Dict[str, Any], channels_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combine data from multiple channels into a unified workflow state.
        Now saves each channel individually for better organization.
        
        Args:
            state: Current workflow state
            channels_data: List of channel data dictionaries
            
        Returns:
            Updated workflow state with combined channel information
        """
        try:
            # Save each channel individually first
            await self._save_channels_individually(channels_data, state)
            
            # Combine all videos from all channels for workflow processing
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
                    # Add channel identification to each video
                    video["channel_id"] = channel_data.get("channel_id")
                    video["channel_name"] = channel_data.get("channel_name")
                    video["processing_order"] = processing_order
                    processing_order += 1
                    all_videos.append(video)
                
                total_subscribers += channel_data.get("channel_subscriber_count", 0)
                total_channel_videos += channel_data.get("channel_video_count", 0)
                total_channel_views += channel_data.get("channel_view_count", 0)
            
            # Create workflow summary (but don't use multi-channel storage)
            if len(channels_data) > 1:
                channel_names = [ch.get("channel_name", "Unknown") for ch in channels_data]
                workflow_summary = f"Multi-Channel Processing ({', '.join(channel_names[:3])}{'...' if len(channel_names) > 3 else ''})"
                # Use primary channel ID for workflow tracking
                workflow_channel_id = primary_channel.get("channel_id", "")
            else:
                workflow_summary = primary_channel.get("channel_name", "")
                workflow_channel_id = primary_channel.get("channel_id", "")
            
            # Update workflow state
            updated_state = {
                **state,
                
                # Channel information (primary channel for workflow tracking)
                "channel_id": workflow_channel_id,
                "channel_name": workflow_summary,
                "channel_handle": primary_channel.get("channel_handle", ""),
                "channel_description": primary_channel.get("channel_description", ""),
                "channel_subscriber_count": total_subscribers,
                "channel_video_count": total_channel_videos,
                "channel_view_count": total_channel_views,
                
                # Multiple channels info
                "channels_data": channels_data,
                "total_channels_processed": len(channels_data),
                "individual_channels_saved": True,  # Flag indicating proper storage
                
                # Video data (combined from all channels for processing)
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
            
            logger.info(f"✅ Processed {len(channels_data)} channels individually with {len(all_videos)} total videos")
            return updated_state
            
        except Exception as e:
            logger.error(f"Failed to combine channel data: {e}")
            return self._create_error_state(state, f"Failed to combine channel data: {e}")
    
    async def _save_channels_individually(self, channels_data: List[Dict[str, Any]], workflow_state: Dict[str, Any]):
        """
        Save each channel to its own directory instead of a combined file.
        
        Args:
            channels_data: List of channel data dictionaries  
            workflow_state: Current workflow state
        """
        try:
            for channel_data in channels_data:
                channel_id = channel_data.get("channel_id", "")
                channel_name = channel_data.get("channel_name", "")
                
                if not channel_id:
                    logger.warning(f"Skipping channel with missing ID: {channel_name}")
                    continue
                
                # Initialize individual channel data
                await FileHandler.initialize_channel_data(
                    channel_id=channel_id,
                    channel_name=channel_name
                )
                
                # Save individual channel data with videos
                channel_data_file = FileHandler.get_channel_data_file(channel_id, channel_name)
                individual_channel_structure = {
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "processed_at": datetime.now().isoformat(),
                    "status": "individual_processing",
                    "videos": channel_data.get("videos", []),
                    "statistics": {
                        "total_videos": len(channel_data.get("videos", [])),
                        "processed_videos": 0,
                        "failed_videos": 0,
                        "comments_posted": 0
                    },
                    "channel_info": channel_data.get("channel_info", {}),
                    "workflow_metadata": {
                        "workflow_id": workflow_state.get("workflow_id"),
                        "processed_individually": True,
                        "discovery_method": channel_data.get("discovery_method", "multi_url"),
                        "user_id": workflow_state.get("user_id"),
                        "chat_id": workflow_state.get("chat_id")
                    }
                }
                
                success = await FileHandler.save_json(individual_channel_structure, channel_data_file)
                if success:
                    logger.info(f"💾 Saved individual channel: {channel_name} ({len(channel_data.get('videos', []))} videos)")
                else:
                    logger.error(f"❌ Failed to save individual channel: {channel_name}")
                    
        except Exception as e:
            logger.error(f"Failed to save channels individually: {e}")
            raise
    
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
            Channel summary dictionary or None if not found
        """
        try:
            youtube_service = YouTubeService()
            channel_info = await youtube_service.get_channel_info(channel_id)
            
            if channel_info:
                return {
                    "channel_id": channel_id,
                    "name": channel_info.get("title", ""),
                    "subscriber_count": channel_info.get("subscriber_count", 0),
                    "video_count": channel_info.get("video_count", 0),
                    "view_count": channel_info.get("view_count", 0),
                    "description": channel_info.get("description", "")[:200] + "..." if channel_info.get("description", "") else ""
                }
            
            return None
            
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


# Testing function
async def test_channel_parser(channel_url: str) -> Dict[str, Any]:
    """
    Test the channel parser with a given URL.
    
    Args:
        channel_url: YouTube channel URL to test
        
    Returns:
        Test results
    """
    test_state = {
        "channel_url": channel_url,
        "completed_steps": [],
        "statistics": {}
    }
    
    agent = ChannelParserAgent()
    result = await agent.execute(test_state)
    
    return {
        "input_url": channel_url,
        "success": result.get("status") != ProcessingStatus.FAILED.value,
        "channel_id": result.get("channel_id"),
        "channel_name": result.get("channel_name"),
        "videos_found": len(result.get("videos", [])),
        "error": result.get("error_message"),
        "processing_time": "N/A"  # Would need timing logic
    }


# Main execution for testing
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Test with single URL
        print("Testing Channel Parser with single URL...")
        result1 = await test_channel_parser("https://www.youtube.com/@mkbhd")
        print(f"Result 1: {result1}")
        
        # Test with multiple URLs
        print("\nTesting Channel Parser with multiple URLs...")
        multi_url_state = {
            "channel_url": "https://www.youtube.com/@mkbhd\nhttps://www.youtube.com/@unboxtherapy",
            "completed_steps": [],
            "statistics": {}
        }
        
        agent = ChannelParserAgent()
        result2 = await agent.execute(multi_url_state)
        
        print(f"Multi-URL Result:")
        print(f"  Status: {result2.get('status')}")
        print(f"  Channels: {result2.get('total_channels_processed', 0)}")
        print(f"  Videos: {len(result2.get('videos', []))}")
        print(f"  Error: {result2.get('error_message', 'None')}")
    
    asyncio.run(main()) 