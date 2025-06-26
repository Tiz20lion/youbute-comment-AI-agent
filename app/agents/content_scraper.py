"""
Agent 3: Content Scraper

This agent handles:
- Scraping video descriptions and metadata
- Fetching top 100 comments sorted by relevance/likes
- Handling comment pagination and threading
- Rate limiting for YouTube Data API
- Comment analysis and filtering
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..services.youtube_service import YouTubeService
from ..utils.logging_config import get_logger
from ..models.schemas import ProcessingStatus, CommentData

logger = get_logger(__name__)


class ContentScraperAgent:
    """Agent responsible for scraping video content and comments from YouTube."""
    
    def __init__(self):
        """Initialize the Content Scraper Agent."""
        from ..config import settings
        self.name = "content_scraper"
        self.description = "Scrapes video descriptions and comments from YouTube"
        self.max_comments_per_video = settings.MAX_COMMENTS_PER_VIDEO
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the content scraping workflow.
        
        Args:
            state: Current workflow state with video data
            
        Returns:
            Updated workflow state with scraped content
        """
        try:
            logger.info(f"🔍 Content Scraper Agent starting for {len(state.get('videos', []))} videos")
            
            videos = state.get("videos", [])
            if not videos:
                return self._create_error_state(state, "No videos found in state")
            
            # Process each video to scrape content and comments
            updated_videos = []
            total_comments_scraped = 0
            videos_with_comments = 0
            
            youtube_service = YouTubeService()
            
            for i, video in enumerate(videos):
                logger.info(f"🔄 Scraping content for video {i+1}/{len(videos)}: {video.get('title', 'Unknown')}")
                
                # Scrape content for this video
                updated_video = await self._scrape_video_content(
                    video, 
                    youtube_service
                )
                
                # Track statistics
                comments_count = len(updated_video.get("comments", []))
                total_comments_scraped += comments_count
                
                if comments_count > 0:
                    videos_with_comments += 1
                    updated_video["status"] = ProcessingStatus.COMPLETED.value
                else:
                    updated_video["status"] = ProcessingStatus.SKIPPED.value
                
                updated_videos.append(updated_video)
            
            # Update workflow state
            updated_state = self._update_workflow_state(
                state, 
                updated_videos, 
                total_comments_scraped, 
                videos_with_comments
            )
            
            logger.info(f"✅ Content Scraper completed. Total comments: {total_comments_scraped}, Videos with comments: {videos_with_comments}")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"❌ Content Scraper Agent failed: {str(e)}")
            return self._create_error_state(state, str(e))
    
    async def _scrape_video_content(
        self, 
        video: Dict[str, Any], 
        youtube_service: YouTubeService
    ) -> Dict[str, Any]:
        """
        Scrape content and comments for a single video.
        
        Args:
            video: Video data dictionary
            youtube_service: YouTube service instance
            
        Returns:
            Updated video data with scraped content
        """
        video_id = video.get("video_id")
        video_title = video.get("title", "Unknown")
        
        try:
            # Step 1: Get enhanced video details (if not already complete)
            enhanced_details = await self._get_enhanced_video_details(
                video_id, 
                youtube_service
            )
            
            # Step 2: Scrape comments
            comments_result = await youtube_service.get_video_comments(
                video_id, 
                max_results=self.max_comments_per_video
            )
            
            # Step 3: Process and structure the data
            # comments_result is already a list of comments
            processed_comments = self._process_comments(comments_result)
            
            # Step 4: Analyze comment quality and relevance
            comment_analytics = self._analyze_comments(processed_comments)
            
            # Step 5: Update video data
            updated_video = {
                **video,
                **enhanced_details,
                "comments": processed_comments,
                "comments_count": len(processed_comments),
                "comments_scraped_at": datetime.now().isoformat(),
                "comment_analytics": comment_analytics,
                "content_scraped": True
            }
            
            logger.info(f"✅ Scraped {len(processed_comments)} comments for '{video_title}'")
            
            return updated_video
            
        except Exception as e:
            logger.error(f"❌ Error scraping content for '{video_title}': {str(e)}")
            return {
                **video,
                "comments": [],
                "comments_count": 0,
                "content_scraped": False,
                "error_message": f"Content scraping failed: {str(e)}",
                "status": ProcessingStatus.FAILED.value
            }
    
    async def _get_enhanced_video_details(
        self, 
        video_id: str, 
        youtube_service: YouTubeService
    ) -> Dict[str, Any]:
        """
        Get enhanced video details if not already complete.
        
        Args:
            video_id: YouTube video ID
            youtube_service: YouTube service instance
            
        Returns:
            Enhanced video details
        """
        try:
            video_details = await youtube_service.get_video_details(video_id)
            
            if video_details:
                return {
                    "enhanced_description": video_details.get("description", ""),
                    "category_id": video_details.get("categoryId"),
                    "default_language": video_details.get("defaultLanguage"),
                    "tags": video_details.get("tags", []),
                    "live_broadcast_content": video_details.get("liveBroadcastContent"),
                    "made_for_kids": video_details.get("madeForKids", False),
                    "privacy_status": video_details.get("privacyStatus"),
                    "upload_status": video_details.get("uploadStatus"),
                    "enhanced_at": datetime.now().isoformat()
                }
            
            return {}
            
        except Exception as e:
            logger.warning(f"Could not get enhanced details for video {video_id}: {str(e)}")
            return {}
    
    def _process_comments(self, raw_comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process and structure raw comments data.
        
        Args:
            raw_comments: Raw comments from YouTube API
            
        Returns:
            Processed and structured comments
        """
        processed_comments = []
        
        for comment in raw_comments:
            try:
                # Extract comment data
                comment_data = {
                    "comment_id": comment.get("id", ""),
                    "text": comment.get("textDisplay", ""),
                    "text_original": comment.get("textOriginal", ""),
                    "author_name": comment.get("authorDisplayName", "Unknown"),
                    "author_channel_id": comment.get("authorChannelId", {}).get("value", ""),
                    "author_profile_image": comment.get("authorProfileImageUrl", ""),
                    "like_count": int(comment.get("likeCount", 0)),
                    "published_at": comment.get("publishedAt", ""),
                    "updated_at": comment.get("updatedAt", ""),
                    
                    # Additional metadata
                    "is_reply": comment.get("parentId") is not None,
                    "parent_id": comment.get("parentId"),
                    "total_reply_count": int(comment.get("totalReplyCount", 0)),
                    "can_rate": comment.get("canRate", False),
                    "viewer_rating": comment.get("viewerRating", "none"),
                    
                    # Processing metadata
                    "text_length": len(comment.get("textDisplay", "")),
                    "word_count": len(comment.get("textDisplay", "").split()),
                    "scraped_at": datetime.now().isoformat()
                }
                
                # Calculate relevance score
                comment_data["relevance_score"] = self._calculate_comment_relevance(comment_data)
                
                processed_comments.append(comment_data)
                
            except Exception as e:
                logger.warning(f"Error processing comment: {str(e)}")
                continue
        
        # Sort by relevance score (highest first)
        processed_comments.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return processed_comments
    
    def _calculate_comment_relevance(self, comment: Dict[str, Any]) -> float:
        """
        Calculate relevance score for a comment.
        
        Args:
            comment: Comment data
            
        Returns:
            Relevance score (0-100)
        """
        score = 0.0
        
        # Like count contributes to relevance
        like_count = comment.get("like_count", 0)
        score += min(like_count * 2, 30)  # Max 30 points from likes
        
        # Comment length (sweet spot around 50-200 characters)
        text_length = comment.get("text_length", 0)
        if 20 <= text_length <= 500:
            length_score = min(20, text_length / 25)  # Max 20 points
            score += length_score
        
        # Reply count indicates engagement
        reply_count = comment.get("total_reply_count", 0)
        score += min(reply_count * 5, 25)  # Max 25 points from replies
        
        # Recency bonus (newer comments get slight boost)
        try:
            published_at = comment.get("published_at", "")
            if published_at:
                # Simple recency scoring - could be enhanced
                score += 5  # Base recency bonus
        except:
            pass
        
        # Content quality indicators
        text = comment.get("text", "").lower()
        
        # Positive indicators
        if any(word in text for word in ["great", "excellent", "amazing", "love", "awesome", "helpful"]):
            score += 5
        
        # Question indicators (often engage discussion)
        if "?" in text:
            score += 3
        
        # Negative indicators (reduce relevance)
        if any(word in text for word in ["spam", "first", "like if", "subscribe"]):
            score -= 10
        
        # Very short comments are less relevant
        if text_length < 10:
            score -= 5
        
        return max(0, min(100, score))  # Clamp between 0-100
    
    def _analyze_comments(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze comments for insights and statistics.
        
        Args:
            comments: List of processed comments
            
        Returns:
            Comment analytics data
        """
        if not comments:
            return {
                "total_comments": 0,
                "average_length": 0,
                "total_likes": 0,
                "top_commenters": [],
                "engagement_metrics": {}
            }
        
        total_comments = len(comments)
        total_likes = sum(c.get("like_count", 0) for c in comments)
        total_replies = sum(c.get("total_reply_count", 0) for c in comments)
        
        # Average metrics
        avg_length = sum(c.get("text_length", 0) for c in comments) / total_comments
        avg_likes = total_likes / total_comments
        avg_relevance = sum(c.get("relevance_score", 0) for c in comments) / total_comments
        
        # Top commenters by engagement
        commenter_stats = {}
        for comment in comments:
            author = comment.get("author_name", "Unknown")
            if author not in commenter_stats:
                commenter_stats[author] = {
                    "comment_count": 0,
                    "total_likes": 0,
                    "total_length": 0
                }
            commenter_stats[author]["comment_count"] += 1
            commenter_stats[author]["total_likes"] += comment.get("like_count", 0)
            commenter_stats[author]["total_length"] += comment.get("text_length", 0)
        
        # Sort top commenters by engagement
        top_commenters = sorted(
            commenter_stats.items(), 
            key=lambda x: x[1]["total_likes"] + x[1]["comment_count"], 
            reverse=True
        )[:5]
        
        # Engagement metrics
        high_engagement_comments = sum(1 for c in comments if c.get("like_count", 0) > 5)
        question_comments = sum(1 for c in comments if "?" in c.get("text", ""))
        
        return {
            "total_comments": total_comments,
            "total_likes": total_likes,
            "total_replies": total_replies,
            "average_length": round(avg_length, 2),
            "average_likes": round(avg_likes, 2),
            "average_relevance_score": round(avg_relevance, 2),
            "high_engagement_comments": high_engagement_comments,
            "question_comments": question_comments,
            "top_commenters": [
                {
                    "name": name,
                    "comments": stats["comment_count"],
                    "total_likes": stats["total_likes"],
                    "avg_length": round(stats["total_length"] / stats["comment_count"], 2)
                }
                for name, stats in top_commenters
            ],
            "engagement_rate": round((high_engagement_comments / total_comments) * 100, 2) if total_comments > 0 else 0
        }
    
    def _update_workflow_state(
        self, 
        current_state: Dict[str, Any], 
        updated_videos: List[Dict[str, Any]], 
        total_comments_scraped: int, 
        videos_with_comments: int
    ) -> Dict[str, Any]:
        """
        Update workflow state with content scraping results.
        
        Args:
            current_state: Current workflow state
            updated_videos: Videos with scraped content
            total_comments_scraped: Total comments scraped
            videos_with_comments: Number of videos with comments
            
        Returns:
            Updated workflow state
        """
        total_videos = len(updated_videos)
        
        return {
            **current_state,
            
            # Updated video data
            "videos": updated_videos,
            
            # Workflow progress
            "current_step": "content_analyzer",
            "completed_steps": current_state.get("completed_steps", []) + ["content_scraper"],
            "status": ProcessingStatus.IN_PROGRESS.value,
            "progress_percentage": 60,  # 3/5 agents completed
            
            # Statistics
            "statistics": {
                **current_state.get("statistics", {}),
                "total_comments_scraped": total_comments_scraped,
                "videos_with_comments": videos_with_comments,
                "average_comments_per_video": total_comments_scraped / total_videos if total_videos > 0 else 0,
                "content_scraping_success_rate": (videos_with_comments / total_videos * 100) if total_videos > 0 else 0
            },
            
            # Timestamps
            "content_scraper_completed_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
    
    def _create_error_state(self, current_state: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """
        Create error state when content scraping fails.
        
        Args:
            current_state: Current workflow state
            error_message: Error description
            
        Returns:
            Error state
        """
        return {
            **current_state,
            "status": ProcessingStatus.FAILED.value,
            "error_message": f"Content scraping failed: {error_message}",
            "failed_at": datetime.now().isoformat(),
            "current_step": "content_scraper",
            "progress_percentage": 40  # Keep previous progress
        }
    
    async def get_scraping_summary(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get a summary of content scraping results.
        
        Args:
            videos: List of processed videos
            
        Returns:
            Summary statistics
        """
        total_videos = len(videos)
        videos_with_comments = sum(1 for v in videos if v.get("comments_count", 0) > 0)
        total_comments = sum(v.get("comments_count", 0) for v in videos)
        
        # Comment engagement analysis
        all_comments = []
        for video in videos:
            all_comments.extend(video.get("comments", []))
        
        if all_comments:
            avg_comment_length = sum(c.get("text_length", 0) for c in all_comments) / len(all_comments)
            avg_likes_per_comment = sum(c.get("like_count", 0) for c in all_comments) / len(all_comments)
            high_engagement_comments = sum(1 for c in all_comments if c.get("like_count", 0) > 10)
        else:
            avg_comment_length = 0
            avg_likes_per_comment = 0
            high_engagement_comments = 0
        
        return {
            "total_videos_processed": total_videos,
            "videos_with_comments": videos_with_comments,
            "total_comments_scraped": total_comments,
            "average_comments_per_video": total_comments / total_videos if total_videos > 0 else 0,
            "success_rate": (videos_with_comments / total_videos * 100) if total_videos > 0 else 0,
            "comment_engagement": {
                "average_comment_length": round(avg_comment_length, 2),
                "average_likes_per_comment": round(avg_likes_per_comment, 2),
                "high_engagement_comments": high_engagement_comments,
                "engagement_rate": round((high_engagement_comments / len(all_comments) * 100), 2) if all_comments else 0
            }
        }


# Agent node function for LangGraph integration
async def content_scraper_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node function for Content Scraper Agent.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state with scraped content
    """
    agent = ContentScraperAgent()
    return await agent.execute(state)


# Helper functions for testing and development
async def test_content_scraper(video_ids: List[str]) -> Dict[str, Any]:
    """
    Test function for Content Scraper Agent.
    
    Args:
        video_ids: List of YouTube video IDs to test
        
    Returns:
        Test result state
    """
    # Create mock video data for testing
    mock_videos = []
    for video_id in video_ids:
        mock_videos.append({
            "video_id": video_id,
            "title": f"Test Video {video_id}",
            "url": f"https://youtube.com/watch?v={video_id}",
            "description": f"Test description for video {video_id}",
            "status": ProcessingStatus.PENDING.value
        })
    
    initial_state = {
        "videos": mock_videos,
                    "completed_steps": ["channel_parser", "description_extractor"],
        "statistics": {}
    }
    
    agent = ContentScraperAgent()
    result = await agent.execute(initial_state)
    
    # Add summary
    if result.get("videos"):
        summary = await agent.get_scraping_summary(result["videos"])
        result["scraping_summary"] = summary
    
    return result


async def scrape_single_video_comments(video_id: str, max_comments: int = 50) -> Dict[str, Any]:
    """
    Scrape comments for a single video (utility function).
    
    Args:
        video_id: YouTube video ID
        max_comments: Maximum number of comments to scrape
        
    Returns:
        Comments scraping result
    """
    try:
        youtube_service = YouTubeService()
        result = await youtube_service.get_video_comments(video_id, max_results=max_comments)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Export the main components
__all__ = [
    'ContentScraperAgent',
    'content_scraper_node',
    'test_content_scraper',
    'scrape_single_video_comments'
] 