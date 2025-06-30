"""
LangGraph Workflow Orchestration

This module defines the complete workflow for YouTube comment automation using LangGraph.
The workflow consists of 6 sequential agents:
1. Channel Parser -> 2. Description Extractor -> 3. Content Scraper 
-> 4. Content Analyzer -> 5. Comment Generator -> 6. Comment Poster

Features:
- Sequential agent execution with state management
- Error handling and recovery strategies
- Progress tracking and Telegram notifications
- Conditional routing based on processing results
- Comprehensive workflow monitoring and logging
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import json
import time

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from ..agents.channel_parser import channel_parser_node
from ..agents.transcript_extractor import description_extractor_node
from ..agents.content_scraper import content_scraper_node
from ..agents.content_analyzer import content_analyzer_node
from ..agents.comment_generator import comment_generator_node
from ..agents.comment_poster import comment_poster_node
from ..services.telegram_service import TelegramService
from ..utils.logging_config import get_logger
from ..models.schemas import ProcessingStatus

logger = get_logger(__name__)


# Define the workflow state structure
class WorkflowState(TypedDict):
    """
    Complete state structure for the YouTube comment automation workflow.
    This state is passed between all agents and contains all processing data.
    """
    
    # Input data
    channel_url: str
    user_id: str
    chat_id: str
    
    # Workflow identification
    workflow_id: str
    
    # Channel information
    channel_id: Optional[str]
    channel_name: Optional[str]
    channel_handle: Optional[str]
    
    # Video data
    videos: List[Dict[str, Any]]
    
    # Workflow control
    current_step: str
    completed_steps: List[str]
    status: str
    progress_percentage: int
    
    # Error handling
    error_message: Optional[str]
    failed_at: Optional[str]
    retry_count: int
    
    # Statistics and metrics
    statistics: Dict[str, Any]
    
    # Timestamps
    started_at: str
    last_updated: str
    completed_at: Optional[str]
    
    # Workflow summary (final)
    workflow_summary: Optional[Dict[str, Any]]


class YouTubeCommentWorkflow:
    """
    Main workflow orchestrator for YouTube comment automation.
    
    This class manages the complete 6-agent workflow using LangGraph,
    handles state transitions, error recovery, and progress notifications.
    """
    
    def __init__(self):
        """Initialize the workflow orchestrator."""
        self.workflow_graph = None
        
        # Use the global telegram service instance instead of creating a new one
        try:
            from ..services.telegram_service import telegram_service
            self.telegram_service = telegram_service
        except (ValueError, ImportError) as e:
            logger.warning(f"Telegram service not available: {e}")
            self.telegram_service = None
        
        # Workflow configuration
        self.max_workflow_retries = 2
        self.agent_timeout = 900  # 15 minutes per agent - increased for comment approval
        
        # Build the workflow graph
        self._build_workflow_graph()
    
    def _build_workflow_graph(self):
        """Build the LangGraph workflow with all 6 agents."""
        
        # Create the state graph
        workflow = StateGraph(WorkflowState)
        
        # Add all agent nodes
        workflow.add_node("channel_parser", self._wrap_agent_node(channel_parser_node, "channel_parser"))
        workflow.add_node("description_extractor", self._wrap_agent_node(description_extractor_node, "description_extractor"))
        workflow.add_node("content_scraper", self._wrap_agent_node(content_scraper_node, "content_scraper"))
        workflow.add_node("content_analyzer", self._wrap_agent_node(content_analyzer_node, "content_analyzer"))
        workflow.add_node("comment_generator", self._wrap_agent_node(comment_generator_node, "comment_generator"))
        workflow.add_node("comment_poster", self._wrap_agent_node(comment_poster_node, "comment_poster"))
        
        # Add error handling node
        workflow.add_node("error_handler", self._error_handler_node)
        
        # Set entry point
        workflow.set_entry_point("channel_parser")
        
        # Use conditional edges for all transitions (including error handling)
        workflow.add_conditional_edges(
            "channel_parser",
            self._should_handle_error,
            {
                "continue": "description_extractor",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "description_extractor",
            self._should_handle_error,
            {
                "continue": "content_scraper",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "content_scraper",
            self._should_handle_error,
            {
                "continue": "content_analyzer",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "content_analyzer",
            self._should_handle_error,
            {
                "continue": "comment_generator",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "comment_generator",
            self._should_handle_error,
            {
                "continue": "comment_poster",
                "error": "error_handler"
            }
        )
        
        # Comment poster can either end successfully or handle errors
        workflow.add_conditional_edges(
            "comment_poster",
            self._should_handle_error,
            {
                "continue": END,
                "error": "error_handler"
            }
        )
        
        # Error handler always ends the workflow
        workflow.add_edge("error_handler", END)
        
        # Compile the workflow
        self.workflow_graph = workflow.compile()
        
        logger.info("🔧 LangGraph workflow compiled successfully with 6 agents")
    
    def _wrap_agent_node(self, agent_function, agent_name: str):
        """
        Wrap agent node with error handling, timeout, and progress tracking.
        """
        async def wrapped_agent(state: WorkflowState) -> WorkflowState:
            try:
                logger.info(f"🚀 Starting agent: {agent_name}")
                
                # Update progress before agent execution
                await self._update_progress(state, agent_name, "starting")
                
                # Execute agent with timeout
                result = await asyncio.wait_for(
                    agent_function(state),
                    timeout=self.agent_timeout
                )
                
                # Update progress after successful execution
                await self._update_progress(result, agent_name, "completed")
                
                logger.info(f"✅ Agent {agent_name} completed successfully")
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Agent {agent_name} timed out after {self.agent_timeout}s"
                logger.error(f"⏰ {error_msg}")
                
                return self._create_error_state(state, error_msg, agent_name)
                
            except Exception as e:
                error_msg = f"Agent {agent_name} failed: {str(e)}"
                logger.error(f"❌ {error_msg}")
                
                return self._create_error_state(state, error_msg, agent_name)
        
        return wrapped_agent
    
    def _should_handle_error(self, state: WorkflowState) -> str:
        """Determine if workflow should continue or handle error."""
        if state.get("status") == ProcessingStatus.FAILED.value:
            return "error"
        
        if state.get("error_message"):
            return "error"
        
        return "continue"
    
    async def _error_handler_node(self, state: WorkflowState) -> WorkflowState:
        """Handle workflow errors and attempt recovery."""
        try:
            logger.error(f"🔥 Error handler activated: {state.get('error_message', 'Unknown error')}")
            
            # Send error notification to user
            await self._send_error_notification(state)
            
            # Check if we should retry
            retry_count = state.get("retry_count", 0)
            if retry_count < self.max_workflow_retries:
                logger.info(f"🔄 Attempting workflow retry {retry_count + 1}/{self.max_workflow_retries}")
                
                # Reset error state for retry
                retry_state = {
                    **state,
                    "status": ProcessingStatus.PROCESSING.value,
                    "error_message": None,
                    "failed_at": None,
                    "retry_count": retry_count + 1,
                    "last_updated": datetime.now().isoformat()
                }
                
                return retry_state
            
            else:
                # Max retries reached, mark as permanently failed
                logger.error(f"💀 Workflow failed permanently after {retry_count} retries")
                
                # Clear auto-approval settings on permanent failure
                workflow_id = state.get("workflow_id")
                if self.telegram_service and workflow_id:
                    self.telegram_service.clear_workflow_auto_approval(workflow_id)
                
                final_error_state = {
                    **state,
                    "status": ProcessingStatus.FAILED.value,
                    "current_step": "failed",
                    "progress_percentage": 0,
                    "completed_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat()
                }
                
                await self._send_final_error_notification(final_error_state)
                return final_error_state
        
        except Exception as e:
            logger.error(f"❌ Error handler itself failed: {str(e)}")
            
            return {
                **state,
                "status": ProcessingStatus.FAILED.value,
                "error_message": f"Error handler failed: {str(e)}",
                "current_step": "error_handler_failed",
                "last_updated": datetime.now().isoformat()
            }
    
    async def _update_progress(self, state: WorkflowState, agent_name: str, status: str):
        """Update workflow progress and send notifications."""
        try:
            # Calculate progress percentage
            agent_progress_map = {
                "channel_parser": 15,
                "description_extractor": 30,
                "content_scraper": 45,
                "content_analyzer": 65,
                "comment_generator": 80,
                "comment_poster": 100
            }
            
            if status == "starting":
                progress = agent_progress_map.get(agent_name, 0) - 5
            else:  # completed
                progress = agent_progress_map.get(agent_name, 0)
            
            # Send progress notification
            await self._send_progress_notification(state, agent_name, status, progress)
            
        except Exception as e:
            logger.error(f"Failed to update progress: {str(e)}")
    
    async def _send_progress_notification(
        self, 
        state: WorkflowState, 
        agent_name: str, 
        status: str, 
        progress: int
    ):
        """Send live progress update to user via Telegram (single updating message)."""
        if not self.telegram_service:
            logger.debug("Telegram service not available, skipping notification")
            return
            
        try:
            agent_display_names = {
                "channel_parser": "Channel Parser",
                "description_extractor": "Description Extractor", 
                "content_scraper": "Content Scraper",
                "content_analyzer": "Content Analyzer",
                "comment_generator": "Comment Generator",
                "comment_poster": "Comment Poster"
            }
            
            agent_display = agent_display_names.get(agent_name, agent_name)
            step_number = len(state.get('completed_steps', [])) + 1
            channel_name = state.get('channel_name', 'Unknown')
            
            # Use live progress update method for single message updates
            await self.telegram_service.send_live_progress_update(
                user_id=int(state.get("user_id", "0")),
                chat_id=int(state.get("chat_id", "0")),
                agent_name=agent_display,
                status=status,
                progress=progress,
                step=step_number,
                total_steps=6,
                channel_name=channel_name,
                details=""
            )
            
        except Exception as e:
            logger.error(f"Failed to send live progress notification: {str(e)}")
    
    def _get_progress_bar(self, progress: int) -> str:
        """Generate visual progress bar."""
        filled = int(progress / 10)
        empty = 10 - filled
        return "█" * filled + "░" * empty + f" {progress}%"
    
    async def _send_error_notification(self, state: WorkflowState):
        """Send error notification to user."""
        if not self.telegram_service:
            logger.debug("Telegram service not available, skipping error notification")
            return
            
        try:
            from app.utils.validators import safe_telegram_message
            
            current_step = state.get("current_step", "unknown")
            error_message = state.get("error_message", "Unknown error")
            retry_count = state.get("retry_count", 0)
            
            message = f"""
❌ *Workflow Error*

🔧 *Step:* {current_step}
⚠️ *Error:* {error_message}
🔄 *Retry:* {retry_count}/{self.max_workflow_retries}

💭 The system will attempt to recover automatically...
            """.strip()
            
            # Make message safe for Telegram
            safe_message = safe_telegram_message(message)
            
            await self.telegram_service.send_message(
                chat_id=state.get("chat_id", ""),
                text=safe_message,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Failed to send error notification: {str(e)}")
            # Fallback: send plain text without markdown
            try:
                plain_message = f"❌ Workflow Error in step: {current_step}. Error: {error_message}. Retry: {retry_count}/{self.max_workflow_retries}. The system will attempt to recover automatically."
                await self.telegram_service.send_message(
                    chat_id=state.get("chat_id", ""),
                    text=plain_message
                )
            except:
                pass  # If even plain text fails, don't crash the workflow
    
    async def _send_final_error_notification(self, state: WorkflowState):
        """Send final error notification when workflow fails permanently."""
        if not self.telegram_service:
            logger.debug("Telegram service not available, skipping final error notification")
            return
            
        try:
            from app.utils.validators import safe_telegram_message
            
            error_message = state.get("error_message", "Unknown error")
            
            message = f"""
💀 *Workflow Failed Permanently*

⚠️ *Error:* {error_message}
🔄 *Retries Exhausted:* {self.max_workflow_retries}

😔 The YouTube comment automation workflow has failed and cannot continue.
Please try again with a different channel or contact support.
            """.strip()
            
            # Make message safe for Telegram
            safe_message = safe_telegram_message(message)
            
            await self.telegram_service.send_message(
                chat_id=state.get("chat_id", ""),
                text=safe_message,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Failed to send final error notification: {str(e)}")
            # Fallback: send plain text without markdown
            try:
                plain_message = f"💀 Workflow Failed Permanently. Error: {error_message}. Retries exhausted: {self.max_workflow_retries}. Please try again with a different channel."
                await self.telegram_service.send_message(
                    chat_id=state.get("chat_id", ""),
                    text=plain_message
                )
            except:
                pass  # If even plain text fails, don't crash the workflow
    
    def _create_error_state(
        self, 
        current_state: WorkflowState, 
        error_message: str, 
        failed_step: str
    ) -> WorkflowState:
        """Create error state for workflow failure."""
        return {
            **current_state,
            "status": ProcessingStatus.FAILED.value,
            "error_message": error_message,
            "failed_at": datetime.now().isoformat(),
            "current_step": failed_step,
            "last_updated": datetime.now().isoformat()
        }
    
    async def execute_workflow(
        self, 
        channel_url: str, 
        user_id: str, 
        chat_id: str
    ) -> Dict[str, Any]:
        """Execute the complete YouTube comment automation workflow."""
        try:
            logger.info(f"🎬 Starting YouTube comment workflow for: {channel_url}")
            
            # Clean up old temp files before starting
            from app.utils.file_handler import FileHandler
            FileHandler.cleanup_temp_files(older_than_hours=24)
            
            # Generate workflow ID
            workflow_id = f"{user_id}_{int(time.time())}"
            
            # Initialize workflow state
            initial_state: WorkflowState = {
                # Input data
                "channel_url": channel_url,
                "user_id": user_id,
                "chat_id": chat_id,
                
                # Workflow identification
                "workflow_id": workflow_id,
                
                # Channel information (to be populated)
                "channel_id": None,
                "channel_name": None,
                "channel_handle": None,
                
                # Video data
                "videos": [],
                
                # Workflow control
                "current_step": "channel_parser",
                "completed_steps": [],
                "status": ProcessingStatus.PROCESSING.value,
                "progress_percentage": 0,
                
                # Error handling
                "error_message": None,
                "failed_at": None,
                "retry_count": 0,
                
                # Statistics
                "statistics": {},
                
                # Timestamps
                "started_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "completed_at": None,
                
                # Final summary
                "workflow_summary": None
            }
            
            # Set user-workflow mapping for auto-approval functionality
            if self.telegram_service:
                from ..services.telegram_service import user_workflow_mapping
                user_workflow_mapping[int(user_id)] = workflow_id
                logger.info(f"🎯 Set user-workflow mapping: user {user_id} -> workflow {workflow_id}")

            # Save initial state to temp file
            temp_file = await FileHandler.save_temp_workflow_state(workflow_id, initial_state)
            
            # Send workflow start notification
            await self._send_workflow_start_notification(initial_state)
            
            # Execute the workflow graph
            logger.info("🔄 Executing LangGraph workflow...")
            final_state = await self.workflow_graph.ainvoke(initial_state)
            
            # Clear auto-approval settings when workflow completes
            if self.telegram_service:
                self.telegram_service.clear_workflow_auto_approval(workflow_id)
            
            # Save final state to temp file
            final_temp_file = await FileHandler.save_temp_workflow_state(f"{workflow_id}_final", final_state)
            
            # Enhanced: Save workflow results for metrics tracking
            await self._save_workflow_results_for_metrics(final_state)
            
            logger.info(f"🏁 Workflow completed with status: {final_state.get('status')}")
            
            return final_state
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(f"💥 {error_msg}")
            
            # Clear auto-approval settings on error
            if self.telegram_service and 'workflow_id' in locals():
                self.telegram_service.clear_workflow_auto_approval(workflow_id)
            
            # Send critical error notification
            try:
                if self.telegram_service:
                    await self.telegram_service.send_message(
                        chat_id=chat_id,
                        text=f"💥 **Critical Workflow Error**\n\n{error_msg}",
                        parse_mode="Markdown"
                    )
            except:
                pass  # Don't fail on notification failure
            
            return {
                "status": ProcessingStatus.FAILED.value,
                "error_message": error_msg,
                "failed_at": datetime.now().isoformat(),
                "current_step": "workflow_execution",
                "channel_url": channel_url,
                "user_id": user_id,
                "chat_id": chat_id
            }
    
    async def _send_workflow_start_notification(self, state: WorkflowState):
        """Send workflow start notification."""
        if not self.telegram_service:
            logger.debug("Telegram service not available, skipping start notification")
            return
            
        try:
            # Skip the startup notification - user doesn't want it
            # Progress updates will be sent instead
            pass
            
        except Exception as e:
            logger.error(f"Failed to send start notification: {str(e)}")
    
    async def _save_workflow_results_for_metrics(self, final_state: WorkflowState):
        """Save workflow results in a format optimized for metrics tracking."""
        try:
            from ..utils.file_handler import FileHandler
            
            # Extract channel information
            channel_id = final_state.get("channel_id")
            channel_name = final_state.get("channel_name", "Unknown Channel")
            
            if not channel_id and final_state.get("videos"):
                # Try to extract channel ID from first video
                first_video = final_state["videos"][0]
                channel_id = first_video.get("channel_id")
            
            if not channel_id:
                logger.warning("❌ No channel ID found, cannot save metrics data")
                return
            
            # Create channel directory
            await FileHandler.create_channel_directory(channel_id, channel_name)
            
            # Enhanced video data with comment posting results
            enhanced_videos = []
            total_comments_posted = 0
            
            for video in final_state.get("videos", []):
                enhanced_video = {
                    **video,
                    "channel_id": channel_id,
                    "processed_at": datetime.now().isoformat(),
                }
                
                # Enhanced comment detection and normalization
                comment_posted = False
                comment_data = {}
                
                # Check multiple possible structures for comment posting results
                if video.get("comment_posted"):
                    comment_posted = True
                    comment_data = {
                        "comment_posted": True,
                        "comment_id": video.get("comment_id", ""),
                        "comment_url": video.get("comment_url", ""),
                        "final_comment_text": video.get("generated_comment", video.get("final_comment_text", "")),
                        "posted_at": video.get("posted_at", datetime.now().isoformat()),
                        "generation_time": video.get("generation_time", 0),
                        "posting_attempts": video.get("posting_attempts", 1)
                    }
                
                elif video.get("workflow_result", {}).get("comment_posting_result"):
                    comment_posted = True
                    workflow_result = video.get("workflow_result", {})
                    comment_data = {
                        "comment_posted": True,
                        "comment_id": workflow_result.get("comment_id", ""),
                        "comment_url": workflow_result.get("comment_url", ""),
                        "final_comment_text": workflow_result.get("final_comment", video.get("generated_comment", "")),
                        "posted_at": workflow_result.get("posted_at", datetime.now().isoformat()),
                        "generation_time": video.get("generation_time", 0),
                        "posting_attempts": 1
                    }
                
                elif "posted_comments" in video:
                    # Check if any comment in posted_comments array was successful
                    for posted_comment in video["posted_comments"]:
                        if posted_comment.get("comment_posted") or posted_comment.get("success"):
                            comment_posted = True
                            comment_data = posted_comment
                            break
                
                # Add normalized comment data to video
                if comment_posted:
                    enhanced_video["comment_posted"] = True
                    enhanced_video.update(comment_data)
                    total_comments_posted += 1
                    
                    # Ensure posted_comments array exists for compatibility
                    if "posted_comments" not in enhanced_video:
                        enhanced_video["posted_comments"] = [comment_data]
                else:
                    enhanced_video["comment_posted"] = False
                
                enhanced_videos.append(enhanced_video)
            
            # Create comprehensive metrics data structure
            metrics_data = {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "channel_handle": final_state.get("channel_handle"),
                "workflow_id": final_state.get("workflow_id"),
                "processed_at": datetime.now().isoformat(),
                "workflow_started_at": final_state.get("started_at"),
                "workflow_completed_at": datetime.now().isoformat(),
                "status": final_state.get("status"),
                "videos": enhanced_videos,
                "statistics": {
                    "total_videos": len(enhanced_videos),
                    "comments_posted": total_comments_posted,
                    "success_rate": round((total_comments_posted / max(len(enhanced_videos), 1)) * 100, 1),
                    "workflow_duration_minutes": self._calculate_workflow_duration_from_state(final_state)
                },
                "workflow_metadata": {
                    "user_id": final_state.get("user_id"),
                    "chat_id": final_state.get("chat_id"),
                    "completed_steps": final_state.get("completed_steps", []),
                    "error_message": final_state.get("error_message"),
                    "retry_count": final_state.get("retry_count", 0)
                }
            }
            
            # Save to channel directory
            channel_file_path = FileHandler.get_channel_data_file(channel_id, channel_name)
            success = await FileHandler.save_json(metrics_data, channel_file_path)
            
            if success:
                logger.info(f"📊 Metrics data saved: {channel_name} ({total_comments_posted} comments posted)")
            else:
                logger.error(f"❌ Failed to save metrics data for: {channel_name}")
                
        except Exception as e:
            logger.error(f"❌ Error saving workflow results for metrics: {e}")
    
    def _calculate_workflow_duration_from_state(self, state: WorkflowState) -> float:
        """Calculate workflow duration in minutes from state."""
        try:
            start_time = state.get("started_at")
            end_time = datetime.now().isoformat()
            
            if start_time:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                duration = (end_dt - start_dt).total_seconds() / 60
                return round(duration, 2)
        except Exception:
            pass
        return 0.0


# Global workflow instance
workflow_instance = None

def get_workflow_instance() -> YouTubeCommentWorkflow:
    """Get or create the global workflow instance."""
    global workflow_instance
    if workflow_instance is None:
        workflow_instance = YouTubeCommentWorkflow()
    return workflow_instance


# Convenience functions for external use
async def execute_youtube_comment_workflow(
    channel_url: str, 
    user_id: str, 
    chat_id: str
) -> Dict[str, Any]:
    """Execute YouTube comment automation workflow."""
    workflow = get_workflow_instance()
    return await workflow.execute_workflow(channel_url, user_id, chat_id)


# Export main components
__all__ = [
    'YouTubeCommentWorkflow',
    'WorkflowState', 
    'get_workflow_instance',
    'execute_youtube_comment_workflow'
] 