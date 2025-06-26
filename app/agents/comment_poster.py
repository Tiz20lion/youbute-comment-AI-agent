"""
Agent 6: Comment Poster

This agent handles:
- Posting generated comments to YouTube videos
- Success/failure tracking and retry logic
- YouTube API rate limit management
- Telegram notifications for posting status
- Final workflow completion and cleanup
- Error handling and recovery strategies
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json

from ..services.youtube_service import YouTubeService
from ..services.telegram_service import telegram_service, TelegramService  # Use global instance + type
from ..utils.logging_config import get_logger
from ..utils.file_handler import FileHandler
from ..models.schemas import ProcessingStatus
from app.config import settings

logger = get_logger(__name__)


class CommentPosterAgent:
    """Agent responsible for posting comments to YouTube and managing final workflow completion."""
    
    def __init__(self):
        """Initialize the Comment Poster Agent."""
        self.name = "comment_poster"
        self.description = "Posts generated comments to YouTube videos and manages workflow completion"
        
        # Retry configuration
        self.max_retries = settings.COMMENT_POST_RETRIES
        self.retry_delay_base = 5  # seconds
        self.batch_delay = 2  # seconds between posts to respect rate limits
        
        # Use global telegram service instance and validate it's initialized
        if not hasattr(telegram_service, 'application') or not telegram_service.application:
            logger.warning("⚠️ Telegram service not properly initialized")
            self.telegram_service = None
        else:
            self.telegram_service = telegram_service
        
        # Configuration
        self.post_delay = settings.COMMENT_POST_DELAY
        self.timeout = settings.COMMENT_POST_TIMEOUT
        
        # Statistics tracking
        self.stats = {
            "total_attempts": 0,
            "successful_posts": 0,
            "failed_posts": 0,
            "approval_requests": 0,
            "approved_posts": 0,
            "rejected_posts": 0,
            "errors": []
        }
        
        logger.info("📝 Comment Poster Agent initialized")
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the comment posting workflow.
        
        Args:
            state: Current workflow state with generated comments
            
        Returns:
            Updated workflow state with posting results
        """
        try:
            logger.info(f"📤 Comment Poster Agent starting for {len(state.get('videos', []))} videos")
            
            videos = state.get("videos", [])
            if not videos:
                return self._create_error_state(state, "No videos found in state")
            
            # Filter videos that are ready for posting
            videos_to_post = [v for v in videos if v.get("comment_ready", False)]
            logger.info(f"📝 Found {len(videos_to_post)} videos ready for comment posting")
            
            if not videos_to_post:
                logger.warning("⚠️ No videos ready for comment posting")
                return self._complete_workflow_without_posting(state, videos)
            
            # Initialize services
            youtube_service = YouTubeService()
            
            # Check if Telegram service is properly initialized
            if not hasattr(telegram_service, 'application') or not telegram_service.application:
                logger.warning("Telegram service not fully initialized - approval requests will be skipped")
            
            # Check if comment posting is properly configured
            if not youtube_service.is_authenticated_for_posting():
                logger.error("❌ Not authenticated for comment posting")
                
                # Try to send error message if Telegram is available
                if hasattr(telegram_service, 'application') and telegram_service.application:
                    try:
                        await telegram_service.send_message(
                            state.get("telegram_user_id"),
                            "❌ **Comment Posting Failed**\n\n"
                            "The bot is not authenticated for posting comments to YouTube.\n\n"
                            "**To fix this:**\n"
                            "1. Run `python oauth2_setup.py` to authenticate\n"
                            "2. Set `ENABLE_COMMENT_POSTING=true` in your .env file\n"
                            "3. Restart the bot"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send error notification: {e}")
                
                return self._complete_workflow_without_posting(state, videos)
            
            # Process each video for comment posting
            updated_videos = []
            successful_posts = 0
            failed_posts = 0
            
            for i, video in enumerate(videos):
                if video.get("comment_ready", False):
                    logger.info(f"🔄 Posting comment for video {i+1}/{len(videos)}: {video.get('title', 'Unknown')}")
                    
                    # Post comment for this video
                    updated_video = await self._post_video_comment(
                        video, 
                        youtube_service,
                        telegram_service,
                        state
                    )
                    
                    # Track statistics
                    if updated_video.get("comment_posted", False):
                        successful_posts += 1
                        updated_video["status"] = ProcessingStatus.COMPLETED.value
                    else:
                        failed_posts += 1
                        updated_video["status"] = ProcessingStatus.FAILED.value
                    
                    # Rate limiting delay between posts
                    if i < len(videos_to_post) - 1:  # Don't delay after last post
                        logger.info(f"⏳ Waiting {self.batch_delay}s before next post (rate limiting)")
                        await asyncio.sleep(self.batch_delay)
                
                else:
                    # Video not ready for posting
                    updated_video = {
                        **video,
                        "comment_posted": False,
                        "posting_skipped": True,
                        "posting_skip_reason": "Comment not ready or generation failed"
                    }
                
                updated_videos.append(updated_video)
            
            # Send final completion notification
            await self._send_completion_notification(
                state, 
                updated_videos, 
                successful_posts, 
                failed_posts, 
                telegram_service
            )
            
            # Update workflow state with final completion
            updated_state = self._complete_workflow_state(
                state, 
                updated_videos, 
                successful_posts, 
                failed_posts
            )
            
            # Save final results to file if we have a channel ID
            channel_id = state.get("channel_id")
            if channel_id:
                try:
                    channel_name = state.get("channel_name", "")
                    channel_data_file = FileHandler.get_channel_data_file(channel_id, channel_name)
                    await FileHandler.update_json(channel_data_file, {
                        "final_results": updated_state,
                        "posted_comments": [
                            {
                                "video_id": v.get("video_id"),
                                "video_title": v.get("title"),
                                "comment_posted": v.get("comment_posted", False),
                                "comment_id": v.get("comment_id"),
                                "comment_url": v.get("comment_url"),
                                "final_comment_text": v.get("final_comment_text"),
                                "posted_at": v.get("posted_at")
                            } for v in updated_videos
                        ],
                        "workflow_completed_at": datetime.now().isoformat()
                    })
                    
                    logger.info(f"💾 Final results saved to: {channel_data_file}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to save final results: {e}")
            
            logger.info(f"✅ Comment Poster completed! Success: {successful_posts}, Failed: {failed_posts}")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"❌ Comment Poster Agent failed: {str(e)}")
            return self._create_error_state(state, str(e))
    
    async def _post_video_comment(
        self, 
        video: Dict[str, Any], 
        youtube_service: YouTubeService,
        telegram_service: TelegramService,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Post comment to a single video with user approval and retry logic.
        
        Args:
            video: Video data dictionary with generated comment
            youtube_service: YouTube service instance
            telegram_service: Telegram service instance
            state: Current workflow state
            
        Returns:
            Updated video data with posting results
        """
        video_id = video.get("video_id", "")
        video_title = video.get("title", "Unknown")
        comment_text = video.get("generated_comment", "")
        
        if not comment_text:
            logger.error(f"❌ No comment to post for video: '{video_title}'")
            return {
                **video,
                "comment_posted": False,
                "posting_error": "No comment available to post",
                "posting_attempts": 0
            }
        
        # Request user approval before posting
        user_id = state.get("user_id") or state.get("chat_id")
        video_url = video.get("url", f"https://www.youtube.com/watch?v={video_id}")
        
        logger.info(f"🔔 Requesting approval for comment on '{video_title}'")
        
        # Check if Telegram service is available for approval
        if not hasattr(telegram_service, 'application') or not telegram_service.application:
            logger.warning("Telegram service not initialized - skipping approval request and posting automatically")
            
            # Log the comment for manual review
            logger.info(f"📝 Auto-posting comment for '{video_title}' (Telegram unavailable):")
            logger.info(f"   Comment: {comment_text}")
            logger.info(f"   Video URL: {video_url}")
            
            # Set approval status for tracking
            approval_status = "auto_approved_telegram_unavailable"
        else:
            # Send approval request to user via Telegram
            try:
                approval_granted = await telegram_service.request_comment_approval(
                    user_id=int(user_id),
                    video_title=video_title,
                    video_url=video_url,
                    comment_text=comment_text,
                    timeout=600,  # 10 minutes timeout - increased from 5 minutes
                    auto_approve_on_timeout=True,  # Enable auto-approval on timeout
                    workflow_id=state.get("workflow_id")  # Pass workflow_id for auto-approval mode
                )
                
                if not approval_granted:
                    logger.info(f"❌ User rejected or timeout for comment on '{video_title}'")
                    return {
                        **video,
                        "comment_posted": False,
                        "posting_error": "User rejected or approval timeout",
                        "posting_attempts": 0,
                        "final_comment_text": comment_text,
                        "posting_success": False,
                        "approval_status": "rejected_or_timeout"
                    }
                
                logger.info(f"✅ User approved comment for '{video_title}' - proceeding with posting")
                approval_status = "approved"
                
            except Exception as e:
                logger.error(f"❌ Error requesting approval for '{video_title}': {e}")
                return {
                    **video,
                    "comment_posted": False,
                    "posting_error": f"Approval request failed: {str(e)}",
                    "posting_attempts": 0,
                    "final_comment_text": comment_text,
                    "posting_success": False,
                    "approval_status": "error"
                }
        
        # Attempt to post comment with retries (only after approval)
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"📤 Posting attempt {attempt}/{self.max_retries} for '{video_title}'")
                
                # Post the comment
                posting_result = await youtube_service.post_comment(video_id, comment_text)
                
                if posting_result.get("success", False):
                    # Success! Send notification and return
                    logger.info(f"✅ Comment posted successfully to '{video_title}'")
                    
                    await self._send_posting_success_notification(
                        video, 
                        comment_text, 
                        posting_result,
                        telegram_service, 
                        state
                    )
                    
                    return {
                        **video,
                        "comment_posted": True,
                        "comment_id": posting_result.get("comment_id", "unknown"),
                        "comment_url": posting_result.get("comment_url", ""),
                        "posted_at": posting_result.get("posted_at", datetime.now().isoformat()),
                        "posting_attempts": attempt,
                        "final_comment_text": comment_text,
                        "posting_success": True,
                        "approval_status": approval_status
                    }
                
                else:
                    # Failed attempt
                    logger.warning(f"⚠️ Posting attempt {attempt} failed for '{video_title}'")
                    
                    if attempt < self.max_retries:
                        # Wait before retry with exponential backoff
                        retry_delay = self.retry_delay_base * (2 ** (attempt - 1))
                        logger.info(f"⏳ Waiting {retry_delay}s before retry...")
                        await asyncio.sleep(retry_delay)
                    
            except Exception as e:
                logger.error(f"❌ Error on posting attempt {attempt} for '{video_title}': {str(e)}")
                
                if attempt < self.max_retries:
                    retry_delay = self.retry_delay_base * (2 ** (attempt - 1))
                    logger.info(f"⏳ Waiting {retry_delay}s before retry...")
                    await asyncio.sleep(retry_delay)
        
        # All attempts failed
        logger.error(f"❌ Failed to post comment to '{video_title}' after {self.max_retries} attempts")
        
        await self._send_posting_failure_notification(
            video, 
            comment_text, 
            telegram_service, 
            state,
            f"Failed after {self.max_retries} attempts"
        )
        
        return {
            **video,
            "comment_posted": False,
            "posting_error": f"Failed after {self.max_retries} attempts",
            "posting_attempts": self.max_retries,
            "final_comment_text": comment_text,
            "posting_success": False,
            "approval_status": f"{approval_status}_but_failed"
        }
    
    async def _send_posting_success_notification(
        self, 
        video: Dict[str, Any], 
        comment_text: str, 
        posting_result: Dict[str, Any],
        telegram_service: TelegramService, 
        state: Dict[str, Any]
    ):
        """Log success notification for comment posting (no Telegram messages sent)."""
        try:
            video_title = video.get("title", "Unknown")
            comment_id = posting_result.get("comment_id", "")
            comment_url = posting_result.get("comment_url", "")
            posted_at = posting_result.get("posted_at", "")
            
            # Just log the success - NO Telegram messages at all during posting
            logger.info(f"✅ Comment posted successfully to '{video_title}'")
            logger.info(f"   Comment ID: {comment_id}")
            logger.info(f"   Comment URL: {comment_url}")
            logger.info(f"   Posted at: {posted_at}")
            logger.info(f"   Comment text: {comment_text[:100]}...")
            
            # DELETE PREVIOUS INTERMEDIATE MESSAGES (progress updates, approvals, etc.)
            await self._delete_previous_intermediate_messages(telegram_service, state.get("user_id"))
            
            # NO individual success messages - only final completion message will show all results
            
        except Exception as e:
            logger.error(f"Failed to process success notification: {str(e)}")
    
    async def _delete_previous_intermediate_messages(self, telegram_service, user_id):
        """Delete all previous intermediate messages for a user."""
        try:
            if (user_id and hasattr(telegram_service, 'progress_message_ids') and 
                user_id in telegram_service.progress_message_ids):
                
                message_ids = telegram_service.progress_message_ids[user_id].copy()
                
                # Delete all stored intermediate messages
                for message_id in message_ids:
                    try:
                        await telegram_service.application.bot.delete_message(
                            chat_id=user_id,  # chat_id is same as user_id for private chats
                            message_id=message_id
                        )
                        logger.debug(f"🗑️ Deleted intermediate message {message_id} for user {user_id}")
                    except Exception as e:
                        logger.debug(f"Could not delete message {message_id}: {e}")
                
                # Clear the stored message IDs
                telegram_service.progress_message_ids[user_id] = []
                
        except Exception as e:
            logger.debug(f"Error deleting previous intermediate messages: {e}")
    
    async def _send_disappearing_message(self, telegram_service, chat_id, text, disappear_after=30):
        """Send a message that disappears after specified time."""
        try:
            message = await telegram_service.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown"
            )
            
            # Schedule deletion
            if hasattr(message, 'message_id'):
                asyncio.create_task(
                    self._delete_message_after_delay(
                        telegram_service, 
                        chat_id, 
                        message.message_id, 
                        disappear_after
                    )
                )
            
        except Exception as e:
            logger.error(f"Failed to send disappearing message: {e}")
    
    async def _delete_message_after_delay(self, telegram_service, chat_id, message_id, delay_seconds):
        """Delete message after specified delay."""
        try:
            await asyncio.sleep(delay_seconds)
            if hasattr(telegram_service, 'application') and telegram_service.application:
                await telegram_service.application.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id
                )
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")  # Use debug level as this is not critical
    
    async def _send_posting_failure_notification(
        self, 
        video: Dict[str, Any], 
        comment_text: str, 
        telegram_service: TelegramService, 
        state: Dict[str, Any],
        error_reason: str
    ):
        """Send failure notification for comment posting."""
        try:
            # Check if Telegram service is properly initialized
            if not hasattr(telegram_service, 'application') or not telegram_service.application:
                logger.warning("Telegram service not initialized, skipping notification")
                return
                
            video_title = video.get("title", "Unknown")
            video_url = video.get("url", "")
            
            message = f"""
❌ **Comment Posting Failed**

📹 **Video:** {video_title}
🔗 **Link:** {video_url}

⚠️ **Error:** {error_reason}

💬 **Generated Comment (not posted):**
"{comment_text}"

🎯 **Video Suggestions:**
{self._format_video_suggestions(video.get("video_suggestions", []))}
            """.strip()
            
            await telegram_service.send_message(
                chat_id=state.get("chat_id", ""),
                text=message,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Failed to send failure notification: {str(e)}")
    
    async def _send_completion_notification(
        self, 
        state: Dict[str, Any], 
        videos: List[Dict[str, Any]], 
        successful_posts: int, 
        failed_posts: int, 
        telegram_service: TelegramService
    ):
        """Send final workflow completion notification."""
        try:
            # Check if Telegram service is properly initialized
            if not hasattr(telegram_service, 'application') or not telegram_service.application:
                logger.debug("Telegram service not initialized, completion notification handled by main workflow")
                return
                
            channel_name = state.get("channel_name", "Unknown Channel")
            total_videos = len(videos)
            
            # Calculate statistics
            stats = state.get("statistics", {})
            processing_time = self._calculate_processing_time(state)
            
            # Create completion summary
            if successful_posts > 0:
                status_emoji = "🎉"
                status_text = "**Workflow Completed Successfully!**"
            elif failed_posts > 0:
                status_emoji = "⚠️"
                status_text = "**Workflow Completed with Issues**"
            else:
                status_emoji = "ℹ️"
                status_text = "**Workflow Completed - No Comments Posted**"
            
            message = f"""
{status_emoji} {status_text}

📺 **Channel:** {channel_name}
⏱️ **Processing Time:** {processing_time}

📊 **Final Results:**
• **Videos Processed:** {total_videos}
• **Comments Posted:** {successful_posts}
• **Posting Failures:** {failed_posts}
• **Success Rate:** {(successful_posts / total_videos * 100):.1f}%

📈 **Processing Statistics:**
• **Transcripts Extracted:** {stats.get('transcripts_extracted', 0)}
• **Comments Scraped:** {stats.get('total_comments_scraped', 0)}
• **Videos Analyzed:** {stats.get('videos_analyzed', 0)}
• **Comments Generated:** {stats.get('comments_generated', 0)}

{self._format_video_results_summary(videos)}
            """.strip()
            
            await telegram_service.send_message(
                chat_id=state.get("chat_id", ""),
                text=message,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Failed to send completion notification: {str(e)}")
    
    def _format_video_suggestions(self, suggestions: List[str]) -> str:
        """Format video suggestions for notification."""
        if not suggestions:
            return "• No suggestions generated"
        
        formatted = []
        for i, suggestion in enumerate(suggestions[:3], 1):  # Limit to 3 suggestions
            formatted.append(f"• {suggestion}")
        
        return "\n".join(formatted)
    
    def _format_video_results_summary(self, videos: List[Dict[str, Any]]) -> str:
        """Format video results summary for notification."""
        if not videos:
            return ""
        
        summary_lines = ["🎬 **Video Results:**"]
        
        for i, video in enumerate(videos[:5], 1):  # Show up to 5 videos
            title = video.get("title", "Unknown")[:50]  # Truncate long titles
            posted = "✅" if video.get("comment_posted", False) else "❌"
            summary_lines.append(f"{i}. {posted} {title}")
        
        if len(videos) > 5:
            summary_lines.append(f"... and {len(videos) - 5} more videos")
        
        return "\n".join(summary_lines)
    
    def _calculate_processing_time(self, state: Dict[str, Any]) -> str:
        """Calculate total processing time."""
        try:
            started_at = state.get("started_at")
            if started_at:
                start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                processing_time = datetime.now(start_time.tzinfo) - start_time
                
                minutes = int(processing_time.total_seconds() // 60)
                seconds = int(processing_time.total_seconds() % 60)
                
                if minutes > 0:
                    return f"{minutes}m {seconds}s"
                else:
                    return f"{seconds}s"
            
            return "Unknown"
            
        except Exception:
            return "Unknown"
    
    def _complete_workflow_without_posting(
        self, 
        state: Dict[str, Any], 
        videos: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Complete workflow when no comments are ready for posting."""
        return {
            **state,
            
            # Updated video data
            "videos": videos,
            
            # Workflow completion
            "current_step": "completed",
            "completed_steps": state.get("completed_steps", []) + ["comment_poster"],
            "status": ProcessingStatus.COMPLETED.value,
            "progress_percentage": 100,
            
            # Statistics
            "statistics": {
                **state.get("statistics", {}),
                "comments_posted": 0,
                "posting_failures": 0,
                "posting_success_rate": 0,
                "workflow_completed": True,
                "completion_reason": "No comments ready for posting"
            },
            
            # Timestamps
            "comment_poster_completed_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
    
    def _complete_workflow_state(
        self, 
        current_state: Dict[str, Any], 
        updated_videos: List[Dict[str, Any]], 
        successful_posts: int, 
        failed_posts: int
    ) -> Dict[str, Any]:
        """Complete workflow state with posting results."""
        total_videos = len(updated_videos)
        
        return {
            **current_state,
            
            # Updated video data
            "videos": updated_videos,
            
            # Workflow completion
            "current_step": "completed",
            "completed_steps": current_state.get("completed_steps", []) + ["comment_poster"],
            "status": ProcessingStatus.COMPLETED.value,
            "progress_percentage": 100,
            
            # Final statistics
            "statistics": {
                **current_state.get("statistics", {}),
                "comments_posted": successful_posts,
                "posting_failures": failed_posts,
                "posting_success_rate": (successful_posts / total_videos * 100) if total_videos > 0 else 0,
                "workflow_completed": True,
                "total_processing_time": self._calculate_processing_time(current_state)
            },
            
            # Final timestamps
            "comment_poster_completed_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            
            # Workflow summary
            "workflow_summary": self._generate_workflow_summary(
                current_state, 
                updated_videos, 
                successful_posts, 
                failed_posts
            )
        }
    
    def _generate_workflow_summary(
        self, 
        state: Dict[str, Any], 
        videos: List[Dict[str, Any]], 
        successful_posts: int, 
        failed_posts: int
    ) -> Dict[str, Any]:
        """Generate comprehensive workflow summary."""
        stats = state.get("statistics", {})
        
        return {
            "channel_info": {
                "channel_name": state.get("channel_name", "Unknown"),
                "channel_url": state.get("channel_url", ""),
                "total_videos_processed": len(videos)
            },
            "processing_results": {
                "transcripts_extracted": stats.get("transcripts_extracted", 0),
                "comments_scraped": stats.get("total_comments_scraped", 0),
                "videos_analyzed": stats.get("videos_analyzed", 0),
                "comments_generated": stats.get("comments_generated", 0),
                "comments_posted": successful_posts,
                "posting_failures": failed_posts
            },
            "success_rates": {
                "description_success_rate": stats.get("analysis_success_rate", 0),
                "analysis_success_rate": stats.get("analysis_success_rate", 0),
                "generation_success_rate": stats.get("comment_generation_success_rate", 0),
                "posting_success_rate": (successful_posts / len(videos) * 100) if videos else 0
            },
            "timing": {
                "started_at": state.get("started_at"),
                "completed_at": datetime.now().isoformat(),
                "total_processing_time": self._calculate_processing_time(state)
            },
            "workflow_status": "completed_successfully" if successful_posts > 0 else "completed_with_issues"
        }
    
    def _create_error_state(self, current_state: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Create error state when comment posting fails."""
        return {
            **current_state,
            "status": ProcessingStatus.FAILED.value,
            "error_message": f"Comment posting failed: {error_message}",
            "failed_at": datetime.now().isoformat(),
            "current_step": "comment_poster",
            "progress_percentage": 90  # Keep previous progress
        }
    
    async def get_posting_summary(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get a summary of comment posting results.
        
        Args:
            videos: List of processed videos
            
        Returns:
            Summary statistics
        """
        total_videos = len(videos)
        posted_comments = sum(1 for v in videos if v.get("comment_posted", False))
        failed_posts = sum(1 for v in videos if v.get("posting_error"))
        skipped_posts = sum(1 for v in videos if v.get("posting_skipped", False))
        
        # Posting attempt analysis
        total_attempts = sum(v.get("posting_attempts", 0) for v in videos)
        avg_attempts = total_attempts / total_videos if total_videos > 0 else 0
        
        # Success rate by video
        success_rate = (posted_comments / total_videos * 100) if total_videos > 0 else 0
        
        return {
            "total_videos": total_videos,
            "comments_posted": posted_comments,
            "posting_failures": failed_posts,
            "posting_skipped": skipped_posts,
            "success_rate": round(success_rate, 2),
            "average_posting_attempts": round(avg_attempts, 1),
            "videos_requiring_retry": sum(1 for v in videos if v.get("posting_attempts", 0) > 1),
            "posting_efficiency": round((posted_comments / max(total_attempts, 1) * 100), 2)
        }


# Agent node function for LangGraph integration
async def comment_poster_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node function for Comment Poster Agent.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state with posting results and completion
    """
    agent = CommentPosterAgent()
    return await agent.execute(state)


# Helper functions for testing and development
async def test_comment_poster(sample_videos_with_comments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Test function for Comment Poster Agent.
    
    Args:
        sample_videos_with_comments: Sample videos with generated comments
        
    Returns:
        Test result state
    """
    initial_state = {
        "videos": sample_videos_with_comments,
        "channel_name": "Test Channel",
        "channel_url": "https://youtube.com/channel/test",
        "chat_id": "test_chat",
        "user_id": "test_user",
        "started_at": datetime.now().isoformat(),
                    "completed_steps": ["channel_parser", "description_extractor", "content_scraper", "content_analyzer", "comment_generator"],
        "statistics": {
            "transcripts_extracted": 3,
            "total_comments_scraped": 150,
            "videos_analyzed": 3,
            "comments_generated": 3
        }
    }
    
    agent = CommentPosterAgent()
    result = await agent.execute(initial_state)
    
    # Add summary
    if result.get("videos"):
        summary = await agent.get_posting_summary(result["videos"])
        result["posting_summary"] = summary
    
    return result


# Export the main components
__all__ = [
    'CommentPosterAgent',
    'comment_poster_node',
    'test_comment_poster'
] 