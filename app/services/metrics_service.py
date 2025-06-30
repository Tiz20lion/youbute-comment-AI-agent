"""
Metrics Service for YouTube Comment AI Agent

This service tracks and analyzes:
- Comment posting statistics
- Agent processing metrics
- Video engagement data
- Comment likes and replies tracking
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import glob
from collections import defaultdict, deque
import logging
import hashlib
import ssl
from urllib.error import URLError

from app.config import settings
from app.utils.logging_config import get_logger
from app.utils.file_handler import FileHandler
from app.services.youtube_service import YouTubeService

logger = logging.getLogger(__name__)

class MetricsService:
    """Enhanced service for tracking and analyzing metrics with intelligent caching and retry logic"""
    
    def __init__(self):
        self.youtube_service = None
        self._cache = {}
        self._engagement_cache = {}  # Separate cache for engagement data
        self._cache_ttl = 300  # 5 minutes base cache
        self._engagement_cache_ttl = 1800  # 30 minutes for engagement data (increased)
        self._error_cache_ttl = 7200  # 2 hours for error states
        self._retry_queue = deque()
        self._max_retries = 3
        self._api_error_backoff = {}
        self._batch_size = 15  # Reduced batch size
        self._min_api_interval = 0.5  # Minimum seconds between API calls
        self._last_api_call = None
        self._daily_api_limit = 1000  # Track daily API usage
        self._api_calls_today = 0
        self._last_reset_date = datetime.now().date()
        
        # NEW: Persistent blacklist for deleted/problematic comments
        self._comment_blacklist = self._load_comment_blacklist()
        self._blacklist_file = Path("./data/comment_blacklist.json")
        
        # IMPROVEMENT: Reset error tracking on startup to give comments fresh start
        self._reset_error_tracking()
        
        # Smart caching tiers
        self._quick_cache_ttl = 60   # 1 minute for frequently accessed data
        self._standard_cache_ttl = 300  # 5 minutes for normal data
        self._long_cache_ttl = 1800     # 30 minutes for stable data
        
        # Performance tracking
        self._performance_stats = {
            'api_calls_saved': 0,
            'cache_hits': 0,
            'api_errors_handled': 0,
            'smart_skips': 0
        }
        
    def _reset_daily_limits(self):
        """Reset daily API limits if needed"""
        today = datetime.now().date()
        if today != self._last_reset_date:
            self._api_calls_today = 0
            self._last_reset_date = today
            logger.info("🔄 Daily API limits reset")
    
    async def get_youtube_service(self) -> YouTubeService:
        """Get YouTube service instance with enhanced error handling"""
        try:
            if not self.youtube_service:
                self.youtube_service = YouTubeService()
            return self.youtube_service
        except Exception as e:
            logger.error(f"❌ Error getting YouTube service: {e}")
            return None
    
    async def get_overall_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics with smart caching tiers"""
        cache_key = "overall_metrics"
        
        # Check quick cache first
        if self._is_cached(cache_key, ttl_override=self._quick_cache_ttl):
            self._performance_stats['cache_hits'] += 1
            logger.info(f"🎯 Quick cache hit for overall metrics")
            return self._cache[cache_key]
        
        try:
            logger.info("📊 Calculating fresh overall metrics")
            data_dir = Path("./data/channels")
            
            if not data_dir.exists():
                logger.warning("📁 No channel data directory found")
                return self._empty_metrics()
            
            all_metrics = self._initialize_metrics_structure()
            
            # Process all channel files with progress tracking
            channel_dirs = [d for d in data_dir.iterdir() if d.is_dir()]
            processed_count = 0
            
            for channel_dir in channel_dirs:
                try:
                    await self._process_channel_directory(channel_dir, all_metrics)
                    processed_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ Error processing channel {channel_dir.name}: {e}")
                    continue
            
            # Update engagement data for all video details with real YouTube API data
            if all_metrics["video_details"]:
                logger.info("🔄 Updating engagement data with real YouTube API data")
                all_metrics["video_details"] = await self.update_video_engagement(all_metrics["video_details"])
            
            # Calculate aggregated statistics
            all_metrics = self._calculate_aggregate_stats(all_metrics)
            
            # Add performance metrics
            all_metrics["performance_metrics"]["cache_stats"] = self._performance_stats
            all_metrics["performance_metrics"]["processed_channels"] = processed_count
            
            # Smart caching - use longer TTL for stable data
            cache_ttl = self._determine_cache_ttl(all_metrics)
            self._cache[cache_key] = all_metrics
            self._cache[f"{cache_key}_timestamp"] = datetime.now()
            self._cache[f"{cache_key}_ttl"] = cache_ttl
            
            logger.info(f"📈 Metrics calculated: {all_metrics['total_comments_posted']} comments, {all_metrics['total_videos_processed']} videos")
            return all_metrics
            
        except Exception as e:
            logger.error(f"❌ Error getting overall metrics: {e}")
            return self._empty_metrics()
    
    def _initialize_metrics_structure(self) -> Dict[str, Any]:
        """Initialize the metrics data structure"""
        return {
            "total_comments_posted": 0,
            "total_videos_processed": 0,
            "total_workflows": 0,
            "agent_statistics": {
                "channel_parser": {"videos_processed": 0, "success_rate": 0, "avg_processing_time": 0},
                "content_scraper": {"videos_processed": 0, "comments_scraped": 0, "avg_comments_per_video": 0},
                "content_analyzer": {"videos_processed": 0, "success_rate": 0, "avg_analysis_time": 0},
                "comment_generator": {"videos_processed": 0, "success_rate": 0, "avg_generation_time": 0},
                "comment_poster": {"videos_processed": 0, "comments_posted": 0, "success_rate": 0, "posting_failures": 0}
            },
            "engagement_metrics": {
                "total_likes": 0,
                "total_replies": 0,
                "average_likes_per_comment": 0,
                "average_replies_per_comment": 0,
                "top_performing_comments": [],
                "engagement_trends": [],
                "failed_api_calls": 0,
                "api_health_score": 100,
                "last_api_error": None
            },
            "recent_activity": [],
            "video_details": [],
            "daily_stats": [],
            "performance_metrics": {
                "workflow_success_rate": 0,
                "avg_workflow_duration": 0,
                "api_health": {
                    "youtube_api_success_rate": 100,
                    "daily_api_calls": self._api_calls_today,
                    "api_calls_remaining": max(0, self._daily_api_limit - self._api_calls_today),
                    "last_api_error": None,
                    "retry_queue_size": len(self._retry_queue),
                    "smart_features_active": True
                }
            },
            "last_updated": datetime.now().isoformat()
        }
    
    def _determine_cache_ttl(self, metrics: Dict[str, Any]) -> int:
        """Determine appropriate cache TTL based on data freshness"""
        recent_activity = metrics.get("recent_activity", [])
        
        if not recent_activity:
            return self._long_cache_ttl  # 30 minutes - no recent activity
        
        # Check if there's very recent activity (last 5 minutes)
        latest_activity = recent_activity[0] if recent_activity else {}
        latest_time_str = latest_activity.get('completed_at', '')
        
        try:
            if latest_time_str:
                latest_time = datetime.fromisoformat(latest_time_str.replace('Z', '+00:00'))
                if (datetime.now() - latest_time).total_seconds() < 300:  # 5 minutes
                    return self._quick_cache_ttl  # 1 minute - very recent activity
        except:
            pass
        
        return self._standard_cache_ttl  # 5 minutes - normal activity
    
    async def get_comment_engagement_metrics(self, comment_ids: List[str]) -> Dict[str, Any]:
        """Enhanced engagement metrics with intelligent error handling and API optimization"""
        if not comment_ids:
            return {}
        
        self._reset_daily_limits()
        
        # Check if we're approaching API limits
        if self._api_calls_today >= self._daily_api_limit * 0.9:  # 90% of limit
            logger.warning(f"🚨 Approaching daily API limit ({self._api_calls_today}/{self._daily_api_limit})")
            return self._get_cached_engagement_data(comment_ids)
        
        # Smart cache key with date component
        cache_key = f"engagement_{hashlib.md5(''.join(sorted(comment_ids)).encode()).hexdigest()}_{datetime.now().date()}"
        
        if self._is_cached(cache_key, use_engagement_ttl=True):
            self._performance_stats['cache_hits'] += 1
            logger.info(f"🎯 Cached engagement data for {len(comment_ids)} comments")
            return self._cache[cache_key]
        
        try:
            youtube_service = await self.get_youtube_service()
            if not youtube_service:
                logger.error("❌ YouTube service not available")
                return self._get_cached_engagement_data(comment_ids)
            
            engagement_data = {}
            failed_ids = []
            successful_calls = 0
            skipped_comments = 0
            
            logger.info(f"🔍 Processing engagement data for {len(comment_ids)} comments")
            
            # Filter out comments that should be skipped
            comments_to_process = []
            for comment_id in comment_ids:
                if self._should_skip_comment(comment_id):
                    skipped_comments += 1
                    # Use cached error state
                    engagement_data[comment_id] = self._get_error_state_for_comment(comment_id)
                else:
                    comments_to_process.append(comment_id)
            
            if skipped_comments > 0:
                self._performance_stats['smart_skips'] += skipped_comments
                logger.info(f"⏭️ Smart skip: avoided {skipped_comments} problematic comments")
            
            # Process remaining comments in optimized batches
            for i in range(0, len(comments_to_process), self._batch_size):
                batch = comments_to_process[i:i + self._batch_size]
                await self._process_engagement_batch(batch, engagement_data, youtube_service)
                successful_calls += len([c for c in batch if engagement_data.get(c, {}).get('status') == 'success'])
                
                # Smart rate limiting based on success rate
                batch_success_rate = successful_calls / max(len(engagement_data), 1)
                if batch_success_rate < 0.5:  # Less than 50% success
                    await asyncio.sleep(2.0)  # Longer delay
                elif batch_success_rate < 0.8:  # Less than 80% success
                    await asyncio.sleep(1.0)  # Medium delay
                else:
                    await asyncio.sleep(self._min_api_interval)  # Normal delay
            
            # Calculate API health metrics
            total_processed = len(comments_to_process)
            api_success_rate = (successful_calls / max(total_processed, 1)) * 100 if total_processed > 0 else 100
            
            # Enhanced caching with success-based TTL
            cache_duration = self._engagement_cache_ttl
            if api_success_rate > 90:
                cache_duration = self._long_cache_ttl  # Cache longer for successful data
            elif api_success_rate < 50:
                cache_duration = self._standard_cache_ttl  # Shorter cache for problematic data
            
            self._cache[cache_key] = engagement_data
            self._cache[f"{cache_key}_timestamp"] = datetime.now()
            self._cache[f"{cache_key}_success_rate"] = api_success_rate
            
            logger.info(f"📊 Engagement processing complete: {api_success_rate:.1f}% success rate ({successful_calls}/{total_processed})")
            
            if api_success_rate < 80:
                logger.warning(f"⚠️ Lower success rate, consider reviewing API health")
            
            return engagement_data
            
        except Exception as e:
            logger.error(f"❌ Critical error in engagement metrics: {e}")
            self._performance_stats['api_errors_handled'] += 1
            return self._get_cached_engagement_data(comment_ids)
    
    async def _process_engagement_batch(self, batch: List[str], engagement_data: Dict, youtube_service):
        """Process a batch of comments for engagement metrics with blacklist filtering"""
        # First, filter out blacklisted comments
        filtered_batch = [comment_id for comment_id in batch if not self._is_blacklisted(comment_id)]
        
        if len(filtered_batch) < len(batch):
            skipped_count = len(batch) - len(filtered_batch)
            logger.info(f"⏭️ Smart skip: avoided {skipped_count} problematic comments")
            self._performance_stats['smart_skips'] += skipped_count
        
        for comment_id in filtered_batch:
            # Respect API rate limiting
            if self._last_api_call:
                time_since_last = (datetime.now() - self._last_api_call).total_seconds()
                if time_since_last < self._min_api_interval:
                    await asyncio.sleep(self._min_api_interval - time_since_last)
            
            try:
                self._api_calls_today += 1
                self._last_api_call = datetime.now()
                
                comment_data = await youtube_service.get_comment_details(comment_id)
                
                if comment_data:
                    engagement_data[comment_id] = {
                        "likes": comment_data.get("like_count", 0),
                        "replies": comment_data.get("reply_count", 0),
                        "last_checked": datetime.now().isoformat(),
                        "status": "success",
                        "api_calls_used": 1
                    }
                    # Clear any previous error tracking
                    if comment_id in self._api_error_backoff:
                        del self._api_error_backoff[comment_id]
                else:
                    # IMPROVED: Don't immediately blacklist - could be temporary error
                    # Only track as error for retry logic, don't permanently blacklist yet
                    self._track_api_error(comment_id, "API returned None - may be temporary")
                    
                    engagement_data[comment_id] = {
                        "likes": 0,
                        "replies": 0,
                        "last_checked": datetime.now().isoformat(),
                        "status": "api_error",
                        "error": "Failed to fetch comment data (may be temporary)",
                        "retry_count": self._api_error_backoff.get(comment_id, {}).get('count', 0),
                        "cache_until": (datetime.now() + timedelta(minutes=30)).isoformat()  # Shorter cache for retries
                    }
                    
            except (ssl.SSLError, URLError, ConnectionError) as e:
                error_msg = f"Connection error: {str(e)[:50]}"
                logger.warning(f"🔌 Connection issue for comment {comment_id}: {error_msg}")
                
                engagement_data[comment_id] = {
                    "likes": 0,
                    "replies": 0,
                    "last_checked": datetime.now().isoformat(),
                    "status": "connection_error",
                    "error": error_msg,
                    "retry_after": (datetime.now() + timedelta(minutes=10)).isoformat()
                }
                self._track_api_error(comment_id, error_msg)
                
            except Exception as e:
                error_msg = str(e)[:50]
                logger.warning(f"⚠️ API error for comment {comment_id}: {error_msg}")
                
                # IMPROVED: Only blacklist on confirmed permanent errors
                # Check for specific HTTP 404 errors that indicate deleted comments
                should_blacklist = (
                    ("404" in error_msg and "not found" in error_msg.lower()) or
                    ("comment not found" in error_msg.lower()) or
                    ("comment has been deleted" in error_msg.lower())
                )
                
                if should_blacklist:
                    self._add_to_blacklist(comment_id, f"Confirmed deleted: {error_msg}")
                    cache_duration = timedelta(hours=24)  # Long cache for confirmed deleted
                    status = "deleted"
                else:
                    # For other errors, use retry logic instead of blacklisting
                    cache_duration = timedelta(minutes=15)  # Short cache for retries
                    status = "temporary_error"
                
                engagement_data[comment_id] = {
                    "likes": 0,
                    "replies": 0,
                    "last_checked": datetime.now().isoformat(),
                    "status": status,
                    "error": error_msg,
                    "retry_count": self._api_error_backoff.get(comment_id, {}).get('count', 0),
                    "cache_until": (datetime.now() + cache_duration).isoformat()
                }
                self._track_api_error(comment_id, error_msg)
                self._performance_stats['api_errors_handled'] += 1
    
    async def _process_channel_directory(self, channel_dir: Path, metrics: Dict[str, Any]):
        """Process a single channel directory and update metrics with enhanced detection"""
        try:
            videos_file = channel_dir / "videos_data.json"
            if not videos_file.exists():
                logger.debug(f"📁 No videos_data.json found in {channel_dir}")
                return
            
            with open(videos_file, 'r', encoding='utf-8') as f:
                channel_data = json.load(f)
            
            logger.debug(f"📊 Processing channel: {channel_data.get('channel_name', 'Unknown')}")
            
            # Process videos
            videos = channel_data.get("videos", [])
            metrics["total_videos_processed"] += len(videos)
            
            # Create video lookup map for accessing video data (including thumbnail_url) by video_id
            video_lookup = {}
            for video in videos:
                video_id = video.get("video_id", "")
                if video_id:
                    video_lookup[video_id] = video

            # Enhanced agent statistics tracking
            for video in videos:
                self._update_agent_stats(video, metrics["agent_statistics"])
            
            # Enhanced comment detection - check multiple possible structures
            posted_comments = []
            for video in videos:
                video_comments = []
                
                # Check for posted_comments array
                if "posted_comments" in video:
                    for comment in video["posted_comments"]:
                        comment["video_title"] = video.get("title", "Unknown")
                        comment["video_id"] = video.get("video_id", "")
                        comment["thumbnail_url"] = video.get("thumbnail_url", "")  # Add thumbnail URL
                        video_comments.append(comment)
                
                # Check for comment_posted field directly on video
                elif video.get("comment_posted"):
                    video_comment = {
                        "comment_posted": True,
                        "video_title": video.get("title", "Unknown"),
                        "video_id": video.get("video_id", ""),
                        "comment_id": video.get("comment_id", ""),
                        "comment_url": video.get("comment_url", ""),
                        "final_comment_text": video.get("generated_comment", video.get("final_comment_text", "")),
                        "posted_at": video.get("posted_at", video.get("completion_time", "")),
                        "generation_time": video.get("generation_time", 0),
                        "posting_attempts": video.get("posting_attempts", 1),
                        "thumbnail_url": video.get("thumbnail_url", "")  # Add thumbnail URL
                    }
                    video_comments.append(video_comment)
                
                # Check for workflow state data structure
                elif video.get("workflow_result", {}).get("comment_posting_result") == True:
                    workflow_comment = {
                        "comment_posted": True,
                        "video_title": video.get("title", "Unknown"),
                        "video_id": video.get("video_id", ""),
                        "comment_id": video.get("workflow_result", {}).get("comment_id", ""),
                        "comment_url": video.get("workflow_result", {}).get("comment_url", ""),
                        "final_comment_text": video.get("workflow_result", {}).get("final_comment", video.get("generated_comment", "")),
                        "posted_at": video.get("workflow_result", {}).get("posted_at", video.get("completion_time", "")),
                        "generation_time": video.get("generation_time", 0),
                        "posting_attempts": 1,
                        "thumbnail_url": video.get("thumbnail_url", "")  # Add thumbnail URL
                    }
                    video_comments.append(workflow_comment)
                
                posted_comments.extend(video_comments)
            
            logger.debug(f"🔍 Found {len(posted_comments)} potential comments in channel")
            
            # Process posted comments with enhanced validation
            successfully_posted = 0
            for comment in posted_comments:
                # Multiple ways to check if comment was posted
                comment_posted = (
                    comment.get("comment_posted", False) or 
                    comment.get("success", False) or
                    comment.get("posted", False) or
                    bool(comment.get("comment_id")) or
                    bool(comment.get("comment_url"))
                )
                
                if comment_posted:
                    successfully_posted += 1
                    metrics["total_comments_posted"] += 1
                    
                    # Get video data from lookup for additional fields like thumbnail_url
                    video_id = comment.get("video_id", "")
                    video_data = video_lookup.get(video_id, {})
                    
                    # Add to video details for UI display
                    video_detail = {
                        "video_id": comment.get("video_id", ""),
                        "video_title": comment.get("video_title", "Unknown"),
                        "comment_id": comment.get("comment_id", ""),
                        "comment_url": comment.get("comment_url", ""),
                        "comment_text": comment.get("final_comment_text", "")[:100] + "..." if len(comment.get("final_comment_text", "")) > 100 else comment.get("final_comment_text", ""),
                        "posted_at": comment.get("posted_at", ""),
                        "channel_name": channel_data.get("channel_name", "Unknown Channel"),
                        "thumbnail_url": comment.get("thumbnail_url", video_data.get("thumbnail_url", "")),  # Include thumbnail URL
                        "engagement": {
                            "likes": 0,
                            "replies": 0,
                            "last_checked": None,
                            "api_error": None
                        },
                        "performance": {
                            "generation_time": comment.get("generation_time", 0),
                            "posting_attempts": comment.get("posting_attempts", 1)
                        }
                    }
                    metrics["video_details"].append(video_detail)
            
            logger.debug(f"✅ Successfully detected {successfully_posted} posted comments")
            
            # Add to recent activity with enhanced data
            if channel_data.get("workflow_completed_at") or channel_data.get("completion_time"):
                workflow_duration = self._calculate_workflow_duration(channel_data)
                activity = {
                    "type": "workflow_completed",
                    "channel_name": channel_data.get("channel_name", "Unknown"),
                    "videos_processed": len(videos),
                    "comments_posted": successfully_posted,
                    "completed_at": channel_data.get("workflow_completed_at", channel_data.get("completion_time", "")),
                    "workflow_id": channel_data.get("workflow_id", ""),
                    "duration_minutes": workflow_duration,
                    "success_rate": round((successfully_posted / max(len(videos), 1)) * 100, 1)
                }
                metrics["recent_activity"].append(activity)
                
        except Exception as e:
            logger.error(f"❌ Error processing channel directory {channel_dir}: {e}")
            logger.error(f"🔍 Channel data structure: {str(channel_data)[:500] if 'channel_data' in locals() else 'N/A'}")
    
    def _update_agent_stats(self, video: Dict[str, Any], agent_stats: Dict[str, Dict[str, Any]]):
        """Update agent statistics from video data based on actual data structure and intelligent detection"""
        try:
            # Channel parser stats - tracks video parsing and description extraction
            # Look for actual evidence of work done, not just flags
            if (video.get("description_extracted") or 
                video.get("processed_by_channel_parser") or
                video.get("enhanced_description") or
                video.get("description_metadata", {}).get("success") or
                len(video.get("enhanced_description", "")) > 0):
                agent_stats["channel_parser"]["videos_processed"] += 1
                
            # Content scraper stats - tracks comment scraping
            if (video.get("content_scraped") or 
                "comments" in video or
                video.get("comments_scraped_at") or
                len(video.get("comments", [])) > 0):
                agent_stats["content_scraper"]["videos_processed"] += 1
                comments = video.get("comments", [])
                agent_stats["content_scraper"]["comments_scraped"] += len(comments)
                if len(comments) > 0:
                    if "avg_comments_per_video" not in agent_stats["content_scraper"]:
                        agent_stats["content_scraper"]["avg_comments_per_video"] = 0
                    # Calculate running average
                    total_videos = agent_stats["content_scraper"]["videos_processed"]
                    current_avg = agent_stats["content_scraper"]["avg_comments_per_video"] 
                    agent_stats["content_scraper"]["avg_comments_per_video"] = round(
                        ((current_avg * (total_videos - 1)) + len(comments)) / total_videos, 1
                    )
                
            # Content analyzer stats - tracks content analysis completion
            # Look for analysis data or timestamps, not just flags
            if (video.get("content_analyzed") or
                video.get("analysis") or
                video.get("analyzed_at") or
                video.get("analysis_available")):
                agent_stats["content_analyzer"]["videos_processed"] += 1
                
            # Comment generator stats - tracks comment generation  
            # Look for generated comments or metadata, not just flags
            if (video.get("comment_generated") or
                video.get("generated_comment") or
                video.get("comment_metadata") or
                video.get("comment_ready") or
                len(video.get("generated_comment", "")) > 0):
                agent_stats["comment_generator"]["videos_processed"] += 1
                
            # Comment poster stats - tracks actual posting attempts and results
            if (video.get("comment_posted") or 
                "posted_comments" in video or
                video.get("comment_id") or
                video.get("comment_url") or
                video.get("posting_success")):
                agent_stats["comment_poster"]["videos_processed"] += 1
                
                # Check if comment was actually posted
                if (video.get("comment_posted", False) or 
                    video.get("posting_success", False) or
                    video.get("comment_id")):
                    agent_stats["comment_poster"]["comments_posted"] += 1
                else:
                    agent_stats["comment_poster"]["posting_failures"] += 1
                
                # Also check posted_comments array if it exists
                posted_comments = video.get("posted_comments", [])
                for comment in posted_comments:
                    if comment.get("comment_posted", False):
                        agent_stats["comment_poster"]["comments_posted"] += 1
                    else:
                        agent_stats["comment_poster"]["posting_failures"] += 1
                
        except Exception as e:
            logger.error(f"Error updating agent stats: {e}")
    
    def _calculate_workflow_duration(self, channel_data: Dict[str, Any]) -> float:
        """Calculate workflow duration in minutes"""
        try:
            start_time = channel_data.get("workflow_started_at")
            end_time = channel_data.get("workflow_completed_at")
            
            if start_time and end_time:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                duration = (end_dt - start_dt).total_seconds() / 60
                return round(duration, 2)
        except Exception:
            pass
        return 0.0
    
    def _calculate_aggregate_stats(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate aggregate statistics and success rates"""
        try:
            # Calculate engagement totals from video details
            total_likes = 0
            total_replies = 0
            comments_with_engagement = 0
            deleted_comments = 0
            top_performing_comments = []
            
            for video in metrics.get("video_details", []):
                engagement = video.get("engagement", {})
                likes = engagement.get("likes", 0)
                replies = engagement.get("replies", 0)
                status = engagement.get("status", "")
                
                # Track deleted comments
                if status == "not_found" or engagement.get("error") == "Comment not found or deleted":
                    deleted_comments += 1
                
                total_likes += likes
                total_replies += replies
                
                if likes > 0 or replies > 0:
                    comments_with_engagement += 1
                    
                # Collect top performing comments
                if likes > 0:
                    top_performing_comments.append({
                        "video_title": video.get("video_title", "Unknown"),
                        "comment_text": video.get("comment_text", "")[:100] + "..." if len(video.get("comment_text", "")) > 100 else video.get("comment_text", ""),
                        "likes": likes,
                        "replies": replies,
                        "comment_url": video.get("comment_url", "")
                    })
            
            # Sort and limit top performing comments
            top_performing_comments.sort(key=lambda x: x["likes"], reverse=True)
            top_performing_comments = top_performing_comments[:5]
            
            # Update engagement metrics
            posted_comments = metrics.get("total_comments_posted", 0)
            total_engagement = total_likes + total_replies  # Calculate total engagement
            
            metrics["engagement_metrics"].update({
                "total_likes": total_likes,
                "total_replies": total_replies,
                "deleted_comments": deleted_comments,
                "average_likes_per_comment": round(total_likes / max(posted_comments, 1), 2),
                "average_replies_per_comment": round(total_replies / max(posted_comments, 1), 2),
                "comments_with_engagement": comments_with_engagement,
                "top_performing_comments": top_performing_comments
            })
            
            # Add total engagement to the main metrics (for frontend display)
            metrics["total_engagement"] = total_engagement
            
            # Calculate agent success rates
            for agent_name, stats in metrics["agent_statistics"].items():
                if stats["videos_processed"] > 0:
                    if agent_name == "comment_poster":
                        total_attempts = stats["comments_posted"] + stats["posting_failures"]
                        stats["success_rate"] = round((stats["comments_posted"] / max(total_attempts, 1)) * 100, 1)
                    else:
                        # For other agents, assume success if they processed videos
                        stats["success_rate"] = 95.0  # Default assumption
            
            # Calculate performance metrics
            if metrics["recent_activity"]:
                total_workflows = len(metrics["recent_activity"])
                successful_workflows = len([w for w in metrics["recent_activity"] if w.get("comments_posted", 0) > 0])
                metrics["performance_metrics"]["workflow_success_rate"] = round((successful_workflows / total_workflows) * 100, 1)
                
                avg_duration = sum(w.get("duration_minutes", 0) for w in metrics["recent_activity"]) / total_workflows
                metrics["performance_metrics"]["avg_workflow_duration"] = round(avg_duration, 2)
            
            # Sort recent activity by date
            metrics["recent_activity"].sort(key=lambda x: x.get("completed_at", ""), reverse=True)
            metrics["recent_activity"] = metrics["recent_activity"][:20]  # Keep last 20
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating aggregate stats: {e}")
            return metrics
    
    def _should_skip_comment(self, comment_id: str) -> bool:
        """Check if we should skip a comment due to recent failures - IMPROVED to be less aggressive"""
        # Always skip blacklisted comments (confirmed deleted)
        if self._is_blacklisted(comment_id):
            return True
            
        if comment_id not in self._api_error_backoff:
            return False
            
        error_info = self._api_error_backoff[comment_id]
        
        # IMPROVED: More forgiving retry logic
        # Skip only if we've had many failures (5+) and it's been less than 30 minutes
        if error_info['count'] >= 5:
            time_since_last = datetime.now() - error_info['last_error']
            return time_since_last.total_seconds() < 1800  # 30 minutes (reduced from 1 hour)
        
        # For fewer failures, always retry (don't skip)
        return False
    
    def _track_api_error(self, comment_id: str, error_msg: str):
        """Track API errors for intelligent backoff"""
        if comment_id not in self._api_error_backoff:
            self._api_error_backoff[comment_id] = {
                'count': 0,
                'last_error': datetime.now(),
                'error_types': []
            }
        
        self._api_error_backoff[comment_id]['count'] += 1
        self._api_error_backoff[comment_id]['last_error'] = datetime.now()
        self._api_error_backoff[comment_id]['error_types'].append(error_msg[:50])
    
    async def process_retry_queue(self):
        """Process failed comment IDs in the retry queue"""
        if not self._retry_queue:
            return
            
        logger.info(f"🔄 Processing {len(self._retry_queue)} items in retry queue")
        
        items_to_retry = []
        current_time = datetime.now()
        
        # Find items ready for retry (after 5 minutes)
        while self._retry_queue:
            item = self._retry_queue.popleft()
            time_since_attempt = current_time - item['last_attempt']
            
            if time_since_attempt.total_seconds() > 300 and item['retry_count'] < self._max_retries:
                items_to_retry.append(item)
            elif item['retry_count'] >= self._max_retries:
                logger.warning(f"⏭️ Giving up on comment {item['comment_id']} after {self._max_retries} retries")
            else:
                # Put back in queue
                self._retry_queue.append(item)
                break
        
        # Retry failed items
        if items_to_retry:
            comment_ids = [item['comment_id'] for item in items_to_retry]
            await self.get_comment_engagement_metrics(comment_ids)
    
    async def get_daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily statistics for the past N days with enhanced data"""
        cache_key = f"daily_stats_{days}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
            
        try:
            daily_stats = []
            
            # Get overall metrics first
            overall_metrics = await self.get_overall_metrics()
            recent_activity = overall_metrics.get("recent_activity", [])
            
            # Generate stats for each day
            for i in range(days):
                date = datetime.now() - timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                
                # Filter activities for this date
                day_activities = [
                    activity for activity in recent_activity
                    if activity.get("completed_at", "").startswith(date_str)
                ]
                
                stats = {
                    "date": date_str,
                    "workflows_completed": len(day_activities),
                    "comments_posted": sum(a.get("comments_posted", 0) for a in day_activities),
                    "videos_processed": sum(a.get("videos_processed", 0) for a in day_activities),
                    "success_rate": round(
                        (sum(a.get("comments_posted", 0) for a in day_activities) / 
                         max(sum(a.get("videos_processed", 0) for a in day_activities), 1)) * 100, 1
                    ),
                    "avg_workflow_duration": round(
                        sum(a.get("duration_minutes", 0) for a in day_activities) / max(len(day_activities), 1), 2
                    )
                }
                
                daily_stats.append(stats)
            
            # Cache results
            self._cache[cache_key] = daily_stats[::-1]  # Reverse to show oldest first
            self._cache[f"{cache_key}_timestamp"] = datetime.now()
            
            return daily_stats[::-1]
            
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return []
    
    async def update_video_engagement(self, video_details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update engagement metrics for video comments with smart batching"""
        try:
            # Filter out videos without comment IDs or with recent successful checks
            comment_ids_to_check = []
            
            for video in video_details:
                comment_id = video.get("comment_id")
                if not comment_id:
                    continue
                    
                # Check if we have recent data
                last_checked = video.get("engagement", {}).get("last_checked")
                engagement_status = video.get("engagement", {}).get("status", "")
                
                if last_checked:
                    try:
                        last_check_time = datetime.fromisoformat(last_checked.replace('Z', ''))
                        time_since_check = datetime.now() - last_check_time
                        
                        # IMPROVED: Different retry intervals based on status
                        if engagement_status == "success":
                            # Skip if successful and checked within last 15 minutes
                            if time_since_check.total_seconds() < 900:  # 15 minutes
                                continue
                        elif engagement_status == "deleted":
                            # Skip deleted comments for longer (6 hours)
                            if time_since_check.total_seconds() < 21600:  # 6 hours
                                continue
                        elif engagement_status in ["api_error", "temporary_error"]:
                            # Retry failed comments more frequently (5 minutes)
                            if time_since_check.total_seconds() < 300:  # 5 minutes
                                continue
                        # For other statuses, always retry
                    except:
                        pass
                        
                comment_ids_to_check.append(comment_id)
            
            if not comment_ids_to_check:
                logger.info("📋 All engagement data is up to date")
                return video_details
            
            logger.info(f"🔄 Updating engagement for {len(comment_ids_to_check)} comments")
            
            # Get engagement data
            engagement_data = await self.get_comment_engagement_metrics(comment_ids_to_check)
            
            # Update video details with engagement
            updated_count = 0
            for video in video_details:
                comment_id = video.get("comment_id")
                if comment_id and comment_id in engagement_data:
                    video["engagement"] = engagement_data[comment_id]
                    updated_count += 1
                elif not video.get("engagement"):
                    # Set default engagement for videos without comment IDs
                    video["engagement"] = {
                        "likes": 0,
                        "replies": 0,
                        "last_checked": datetime.now().isoformat(),
                        "status": "no_comment_id"
                    }
            
            logger.info(f"✅ Updated engagement data for {updated_count} videos")
            return video_details
            
        except Exception as e:
            logger.error(f"Error updating video engagement: {e}")
            return video_details
    
    def _is_cached(self, cache_key: str, use_engagement_ttl: bool = False, ttl_override: int = None) -> bool:
        """Check if data is cached and still valid"""
        if cache_key not in self._cache:
            return False
        
        timestamp_key = f"{cache_key}_timestamp"
        if use_engagement_ttl:
            timestamp_key = f"{cache_key}_engagement_timestamp"
            
        if timestamp_key not in self._cache:
            return False
        
        cached_time = self._cache[timestamp_key]
        ttl = self._engagement_cache_ttl if use_engagement_ttl else (ttl_override or self._cache_ttl)
        return (datetime.now() - cached_time).seconds < ttl
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        return {
            "cache_entries": len([k for k in self._cache.keys() if not k.endswith('_timestamp')]),
            "retry_queue_size": len(self._retry_queue),
            "api_error_tracking": len(self._api_error_backoff),
            "cache_hit_ratio": getattr(self, '_cache_hits', 0) / max(getattr(self, '_cache_requests', 1), 1)
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure with enhanced fields"""
        return {
            "total_comments_posted": 0,
            "total_videos_processed": 0,
            "total_workflows": 0,
            "total_engagement": 0,  # Add missing total_engagement field
            "agent_statistics": {
                "channel_parser": {"videos_processed": 0, "success_rate": 0, "avg_processing_time": 0},
                "content_scraper": {"videos_processed": 0, "comments_scraped": 0, "avg_comments_per_video": 0},
                "content_analyzer": {"videos_processed": 0, "success_rate": 0, "avg_analysis_time": 0},
                "comment_generator": {"videos_processed": 0, "success_rate": 0, "avg_generation_time": 0},
                "comment_poster": {"videos_processed": 0, "comments_posted": 0, "success_rate": 0, "posting_failures": 0}
            },
            "engagement_metrics": {
                "total_likes": 0,
                "total_replies": 0,
                "average_likes_per_comment": 0,
                "average_replies_per_comment": 0,
                "top_performing_comments": [],
                "engagement_trends": [],
                "failed_api_calls": 0
            },
            "recent_activity": [],
            "video_details": [],
            "daily_stats": [],
            "performance_metrics": {
                "workflow_success_rate": 0,
                "avg_workflow_duration": 0,
                "api_health": {
                    "youtube_api_success_rate": 100,
                    "last_api_error": None,
                    "retry_queue_size": 0
                }
            },
            "last_updated": datetime.now().isoformat()
        }

    def _get_cached_engagement_data(self, comment_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get cached engagement data for comment IDs.
        
        Args:
            comment_ids: List of comment IDs to get cached data for
            
        Returns:
            Dictionary mapping comment IDs to their engagement data
        """
        cached_data = {}
        current_time = datetime.now()
        
        for comment_id in comment_ids:
            cache_key = f"engagement_{comment_id}"
            cached_entry = self._engagement_cache.get(cache_key)
            
            if cached_entry:
                # Check if cache is still valid (within 1 hour)
                cache_time = cached_entry.get('cached_at')
                if cache_time and (current_time - cache_time) < timedelta(hours=1):
                    cached_data[comment_id] = cached_entry['data']
                    logger.debug(f"Using cached engagement data for comment {comment_id}")
        
        return cached_data
    
    def _cache_engagement_data(self, comment_id: str, engagement_data: Dict[str, Any]):
        """
        Cache engagement data for a comment.
        
        Args:
            comment_id: Comment ID
            engagement_data: Engagement data to cache
        """
        cache_key = f"engagement_{comment_id}"
        self._engagement_cache[cache_key] = {
            'data': engagement_data,
            'cached_at': datetime.now()
        }
        logger.debug(f"Cached engagement data for comment {comment_id}")

    def _get_error_state_for_comment(self, comment_id: str) -> Dict[str, Any]:
        """
        Get cached error state for a comment that should be skipped.
        
        Args:
            comment_id: Comment ID to get error state for
            
        Returns:
            Dictionary containing error state information
        """
        # Check if we have cached error information
        error_info = self._api_error_backoff.get(comment_id, {})
        
        return {
            "likes": 0,
            "replies": 0,
            "last_checked": datetime.now().isoformat(),
            "status": "skipped",
            "error": error_info.get('last_error', 'Previously failed, skipping'),
            "retry_count": error_info.get('count', 0),
            "cache_until": (datetime.now() + timedelta(hours=2)).isoformat(),
            "api_calls_used": 0
        }

    def _load_comment_blacklist(self) -> Dict[str, Dict[str, Any]]:
        """Load persistent blacklist of problematic comments"""
        blacklist_file = Path("./data/comment_blacklist.json")
        try:
            if blacklist_file.exists():
                with open(blacklist_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load comment blacklist: {e}")
        
        return {}
    
    def _save_comment_blacklist(self):
        """Save comment blacklist to persistent storage"""
        try:
            blacklist_file = Path("./data/comment_blacklist.json")
            blacklist_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(blacklist_file, 'w') as f:
                json.dump(self._comment_blacklist, f, indent=2)
                
        except Exception as e:
            logger.error(f"Could not save comment blacklist: {e}")
    
    def _add_to_blacklist(self, comment_id: str, reason: str):
        """Add a comment to the blacklist to prevent future API calls"""
        self._comment_blacklist[comment_id] = {
            'reason': reason,
            'first_failed': datetime.now().isoformat(),
            'failure_count': self._comment_blacklist.get(comment_id, {}).get('failure_count', 0) + 1,
            'last_attempted': datetime.now().isoformat()
        }
        self._save_comment_blacklist()
        self._performance_stats['smart_skips'] += 1
        logger.info(f"🚫 Added comment {comment_id} to blacklist: {reason}")
    
    def _is_blacklisted(self, comment_id: str) -> bool:
        """Check if a comment is blacklisted"""
        blacklist_entry = self._comment_blacklist.get(comment_id)
        if not blacklist_entry:
            return False
        
        # Remove from blacklist after 7 days (maybe content was restored)
        try:
            first_failed = datetime.fromisoformat(blacklist_entry['first_failed'])
            if (datetime.now() - first_failed).days > 7:
                del self._comment_blacklist[comment_id]
                self._save_comment_blacklist()
                return False
        except:
            pass
        
        return True

    def _reset_error_tracking(self):
        """Reset API error tracking to give comments a fresh start"""
        self._api_error_backoff.clear()
        logger.info("🔄 Reset API error tracking - giving all comments a fresh start")

# Global instance
metrics_service = MetricsService() 