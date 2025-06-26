#!/usr/bin/env python3
"""
YouTube Description Extractor Agent

This agent is responsible for extracting video descriptions from YouTube videos
using the YouTube Data API. This replaces the transcript extractor since
transcript extraction was causing bot detection issues.

Part of the 6-agent YouTube comment automation workflow:
1. Channel Parser → 2. Description Extractor (THIS) → 3. Content Scraper → 4. Content Analyzer → 5. Comment Generator → 6. Comment Poster
"""

import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logging_config import get_logger
from ..models.schemas import ProcessingStatus
from ..config import settings
from ..services.youtube_service import YouTubeService
from ..services.telegram_service import telegram_service  # Use global instance
from ..utils.validators import YouTubeValidator

logger = get_logger(__name__)


class DescriptionExtractorAgent:
    """
    YouTube Description Extractor Agent
    
    This agent extracts video descriptions from YouTube videos using the YouTube Data API.
    It replaces the transcript extractor to avoid bot detection issues.
    """
    
    def __init__(self):
        """Initialize the description extractor agent."""
        self.youtube_service = YouTubeService()
        self.telegram_service = telegram_service
        self.max_retries = settings.DESCRIPTION_RETRY_ATTEMPTS
        self.timeout = settings.DESCRIPTION_TIMEOUT
        
        # Statistics tracking
        self.stats = {
            'total_videos': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'total_characters': 0,
            'empty_descriptions': 0
        }
        
        logger.info("📄 Description Extractor Agent initialized")
        
    async def process(self, state: dict) -> dict:
        """
        Process videos and extract descriptions.
        
        Args:
            state: Current workflow state containing videos from channel_parser
            
        Returns:
            Updated state with description data added to videos
        """
        try:
            logger.info("📄 Description Extractor Agent starting")
            
            # Get videos from state
            videos = state.get('videos', [])
            if not videos:
                logger.warning("⚠️ No videos found in state")
                return state
            
            video_count = len(videos)
            self.stats['total_videos'] = video_count
            
            logger.info(f"📄 Description Extractor Agent starting for {video_count} videos")
            
            # Send initial notification
            await self._notify_start(video_count)
            
            # Process videos with description extraction
            start_time = time.time()
            updated_videos = await self._extract_descriptions_for_videos(videos)
            processing_time = time.time() - start_time
            
            # Update state with descriptions
            state['videos'] = updated_videos
            
            # Log final statistics
            await self._log_final_stats(processing_time)
            
            # Send completion notification
            await self._notify_completion()
            
            logger.info(f"✅ Description Extractor completed. Success: {self.stats['successful_extractions']}, Failed: {self.stats['failed_extractions']}")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Description Extractor Agent error: {e}")
            await self._notify_error(f"Description extraction failed: {e}")
            return state
    
    async def _extract_descriptions_for_videos(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract descriptions for all videos using the YouTube Data API.
        
        Args:
            videos: List of video dictionaries
            
        Returns:
            Updated list of video dictionaries with description data
        """
        updated_videos = []
        
        for i, video in enumerate(videos, 1):
            try:
                video_id = video.get('video_id')
                title = video.get('title', 'Unknown')
                
                logger.info(f"🔄 Processing video {i}/{len(videos)}: {title}")
                
                if not video_id:
                    logger.warning(f"⚠️ No video ID found for '{title}'")
                    video['description'] = ""
                    video['description_metadata'] = {
                        'success': False,
                        'error': 'No video ID',
                        'char_count': 0,
                        'word_count': 0
                    }
                    updated_videos.append(video)
                    self.stats['failed_extractions'] += 1
                    continue
                
                # Extract description using YouTube service
                result = await self._extract_single_description(video_id, title)
                
                # Update video with description data
                video['description'] = result['description']
                video['description_metadata'] = result['metadata']
                
                # Update statistics
                self._update_stats(result)
                
                updated_videos.append(video)
                
            except Exception as e:
                logger.error(f"❌ Error processing video {i}: {e}")
                video['description'] = ""
                video['description_metadata'] = {
                    'success': False,
                    'error': str(e),
                    'char_count': 0,
                    'word_count': 0
                }
                updated_videos.append(video)
                self.stats['failed_extractions'] += 1
        
        return updated_videos
    
    async def _extract_single_description(self, video_id: str, title: str) -> Dict[str, Any]:
        """
        Extract description for a single video.
        
        Args:
            video_id: YouTube video ID
            title: Video title for logging
            
        Returns:
            Dictionary with description and metadata
        """
        try:
            logger.info(f"🔍 Extracting description for '{title}' (ID: {video_id})")
            
            # Get video details which includes description
            video_details = await self.youtube_service.get_video_details(video_id)
            
            if not video_details:
                logger.warning(f"⚠️ Could not get video details for '{title}'")
                return {
                    'description': "",
                    'metadata': {
                        'success': False,
                        'error': 'Could not get video details',
                        'char_count': 0,
                        'word_count': 0
                    }
                }
            
            description = video_details.get('description', '')
            
            if description and len(description.strip()) > 0:
                logger.info(f"✅ Description extracted for '{title}' ({len(description)} chars)")
                return {
                    'description': description,
                    'metadata': {
                        'success': True,
                        'error': '',
                        'char_count': len(description),
                        'word_count': len(description.split()) if description else 0
                    }
                }
            else:
                logger.warning(f"⚠️ Empty description for '{title}'")
                return {
                    'description': "",
                    'metadata': {
                        'success': True,  # Still successful, just empty
                        'error': 'Empty description',
                        'char_count': 0,
                        'word_count': 0
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ Error extracting description for '{title}': {e}")
            return {
                'description': "",
                'metadata': {
                    'success': False,
                    'error': str(e),
                    'char_count': 0,
                    'word_count': 0
                }
            }
    
    def _update_stats(self, result: Dict[str, Any]):
        """Update extraction statistics."""
        try:
            metadata = result.get('metadata', {})
            if metadata.get('success'):
                self.stats['successful_extractions'] += 1
                char_count = metadata.get('char_count', 0)
                self.stats['total_characters'] += char_count
                
                if char_count == 0:
                    self.stats['empty_descriptions'] += 1
            else:
                self.stats['failed_extractions'] += 1
                
        except Exception as e:
            logger.debug(f"Error updating stats: {e}")
    
    async def _log_final_stats(self, processing_time: float):
        """Log final extraction statistics."""
        try:
            logger.info("📊 Description Extraction Statistics:")
            logger.info(f"  Total videos: {self.stats['total_videos']}")
            logger.info(f"  Successful extractions: {self.stats['successful_extractions']}")
            logger.info(f"  Empty descriptions: {self.stats['empty_descriptions']}")
            logger.info(f"  Failed extractions: {self.stats['failed_extractions']}")
            logger.info(f"  Total characters: {self.stats['total_characters']:,}")
            logger.info(f"  Processing time: {processing_time:.2f}s")
                    
        except Exception as e:
            logger.debug(f"Error logging final stats: {e}")
    
    async def _notify_start(self, video_count: int):
        """Send start notification via Telegram."""
        try:
            # Skip notifications - handled by main workflow progress updates
            pass
        except Exception as e:
            logger.debug(f"Error sending start notification: {e}")
    
    async def _notify_completion(self):
        """Send completion notification via Telegram."""
        try:
            # Skip notifications - handled by main workflow progress updates
            pass
        except Exception as e:
            logger.debug(f"Error sending completion notification: {e}")
    
    async def _notify_error(self, error_message: str):
        """Send error notification via Telegram."""
        try:
            # Skip notifications - handled by main workflow progress updates
            pass
        except Exception as e:
            logger.debug(f"Error sending error notification: {e}")


class DescriptionExtractor(DescriptionExtractorAgent):
    """Alias for backwards compatibility."""
    pass


async def description_extractor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node wrapper for the description extractor agent.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state with description data
    """
    agent = DescriptionExtractorAgent()
    return await agent.process(state)


async def test_description_extraction(video_url: str) -> Dict[str, Any]:
    """
    Test description extraction for a single video.
    
    Args:
        video_url: YouTube video URL
        
    Returns:
        Test results
    """
    video_id = YouTubeValidator.extract_video_id(video_url)
    if not video_id:
        return {"error": "Invalid video URL"}
    
    # Create test state
    test_state = {
        "videos": [{"video_id": video_id, "title": "Test Video"}]
    }
    
    agent = DescriptionExtractorAgent()
    result = await agent._extract_single_description(video_id, "Test Video")
    
    return result


# Export the main components
__all__ = [
    'DescriptionExtractorAgent',
    'DescriptionExtractor', 
    'description_extractor_node',
    'test_description_extraction'
] 