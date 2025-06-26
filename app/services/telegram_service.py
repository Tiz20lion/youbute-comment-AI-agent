"""
Telegram Bot Service for YouTube Comment Automation

This service handles all Telegram bot interactions using the python-telegram-bot library
with polling instead of webhooks. It provides user authentication, command handling,
and integration with the LangGraph workflow system.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
import json
import os

# Add process management imports with fallback
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None

import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application, 
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, Forbidden, BadRequest

from app.config import settings
from app.utils.logging_config import get_logger

# Get logger
logger = get_logger(__name__)

# Global callback storage for approval requests
approval_callbacks = {}

# Global batch approval storage for "Approve All" functionality
batch_approval_callbacks = {}
pending_batch_approvals = {}  # Tracks pending approvals for batch processing
auto_approval_settings = {}  # Stores auto-approval settings per user

# NEW: Global auto-approval mode for workflows
workflow_auto_approval = {}  # workflow_id -> {"user_id": int, "mode": "approve_all"|"reject_all"|None}
user_workflow_mapping = {}  # user_id -> current_workflow_id

class TelegramService:
    """
    Enhanced Telegram service with singleton management and conflict detection.
    Prevents multiple bot instances from running simultaneously.
    """
    
    _instance = None
    _lock = threading.Lock()
    _running_instances = set()
    
    def __new__(cls, *args, **kwargs):
        """Ensure singleton pattern with process conflict detection."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # Check for existing bot processes
                    cls._check_for_conflicts()
                    cls._instance = super(TelegramService, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def _check_for_conflicts(cls):
        """Check for existing Telegram bot processes and warn about conflicts."""
        if not HAS_PSUTIL:
            logger.debug("psutil not available - skipping process conflict detection")
            return
            
        try:
            current_pid = os.getpid()
            bot_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['pid'] != current_pid and proc.info['cmdline']:
                        cmdline_str = ' '.join(proc.info['cmdline'])
                        if any(indicator in cmdline_str.lower() for indicator in 
                               ['telegram', 'bot', 'main.py', 'uvicorn']):
                            bot_processes.append(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if bot_processes:
                logger.warning(f"Detected {len(bot_processes)} potential bot processes: {bot_processes}")
                logger.warning("Multiple bot instances may cause Telegram conflicts")
                
        except Exception as e:
            logger.debug(f"Could not check for process conflicts: {e}")
    
    def __init__(self):
        """Initialize the Telegram service with bot token and allowed users."""
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.allowed_users = self._parse_allowed_users()
        self.application: Optional[Application] = None
        self.active_workflows: Dict[int, str] = {}  # user_id -> workflow_id
        self.progress_messages: Dict[int, Message] = {}  # user_id -> message for live updates
        self.progress_message_ids: Dict[int, List[int]] = {}  # user_id -> [message_ids] for deletion
        self.workflow_callback = None  # Will be set by main app
        
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        logger.info(f"Telegram service initialized with {len(self.allowed_users)} allowed users")
    
    def _parse_allowed_users(self) -> List[int]:
        """Parse allowed user IDs from settings."""
        if not settings.TELEGRAM_ALLOWED_USERS:
            logger.warning("No allowed users configured for Telegram bot")
            return []
        
        try:
            user_ids = []
            for user_id in settings.TELEGRAM_ALLOWED_USERS.split(','):
                user_ids.append(int(user_id.strip()))
            return user_ids
        except ValueError as e:
            logger.error(f"Invalid user ID format in TELEGRAM_ALLOWED_USERS: {e}")
            return []
    
    def set_workflow_callback(self, callback):
        """Set the callback function to start workflows."""
        self.workflow_callback = callback
    
    def set_workflow_auto_approval(self, workflow_id: str, user_id: int, mode: str):
        """Set auto-approval mode for a workflow."""
        workflow_auto_approval[workflow_id] = {"user_id": user_id, "mode": mode}
        user_workflow_mapping[user_id] = workflow_id
        logger.info(f"🎯 Set auto-approval mode '{mode}' for workflow {workflow_id} by user {user_id}")
    
    def get_workflow_auto_approval(self, workflow_id: str) -> Optional[str]:
        """Get auto-approval mode for a workflow."""
        return workflow_auto_approval.get(workflow_id, {}).get("mode")
    
    def clear_workflow_auto_approval(self, workflow_id: str):
        """Clear auto-approval mode for a workflow."""
        if workflow_id in workflow_auto_approval:
            user_id = workflow_auto_approval[workflow_id].get("user_id")
            if user_id and user_id in user_workflow_mapping:
                del user_workflow_mapping[user_id]
            del workflow_auto_approval[workflow_id]
            logger.info(f"🧹 Cleared auto-approval mode for workflow {workflow_id}")
    
    def is_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot."""
        if not self.allowed_users:
            logger.warning(f"User {user_id} attempted to use bot but no allowed users configured")
            return False
        
        is_authorized = user_id in self.allowed_users
        if not is_authorized:
            logger.warning(f"Unauthorized user {user_id} attempted to use bot")
        
        return is_authorized
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user_id = update.effective_user.id
        
        if not self.is_user_authorized(user_id):
            await update.message.reply_text(
                "❌ You are not authorized to use this bot."
            )
            return
        
        welcome_message = """
🤖 **AI YouTube Comment Agent** by **Tiz Lion**

🔗 **GitHub**: [Tiz Lion](https://github.com/Tiz20lion)

✨ **What I can do:**
• Analyze YouTube channels & videos using AI
• Generate engaging, contextual comments
• Auto-post comments with smart timing
• Follow YouTube community guidelines

🚀 **Quick Start:**
Just send me YouTube URLs and I'll start working!

**Examples:**
• `https://www.youtube.com/@channelname` (Channel)
• `https://www.youtube.com/watch?v=VIDEO_ID` (Video)
• Multiple URLs separated by commas or newlines

**Commands:**
• `/help` - Detailed guide
• `/process <URL>` - Start processing
• `/status` - Check progress
• `/cancel` - Stop workflow

Ready to boost your YouTube engagement? 🎯
        """
        
        await update.message.reply_text(
            welcome_message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        user_id = update.effective_user.id
        
        if not self.is_user_authorized(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        help_message = """
🔧 **Detailed Help**

**How it works:**
1. Send me YouTube URLs (channels or individual videos)
2. For channels: I'll analyze the top videos from that channel
3. For videos: I'll analyze the specific video AND discover the channel's latest videos
4. Extract transcripts and analyze content
5. Generate engaging comments using AI
6. Post comments to the videos (with your approval)

**Supported URL formats:**
• `https://www.youtube.com/@channelname` (Channel)
• `https://www.youtube.com/c/channelname` (Channel)
• `https://www.youtube.com/channel/UCxxxxx` (Channel)
• `https://www.youtube.com/user/username` (Channel)
• `https://www.youtube.com/watch?v=VIDEO_ID` (Video)
• `https://youtu.be/VIDEO_ID` (Video)
• Multiple URLs separated by commas or newlines

**Workflow Steps:**
1. **Channel Parser** - Extract channel info and top videos
2. **Transcript Extractor** - Download video transcripts
3. **Content Scraper** - Analyze video content and comments
4. **Content Analyzer** - AI-powered content analysis
5. **Comment Generator** - Generate engaging comments
6. **Comment Poster** - Post comments to videos

**Features:**
• AI-powered content analysis
• Video URL processing with channel discovery
• Multiple comment styles (engaging, professional, educational)
• YouTube community guidelines compliance
• Rate limiting and error handling
• Progress tracking and notifications

**Tips:**
• Works with both channels and individual videos
• For videos: I'll also process the channel's latest videos
• The bot works best with channels that have transcripts
• You'll receive notifications at each step
• You can cancel the workflow anytime with `/cancel`
        """
        
        await update.message.reply_text(
            help_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def process_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /process command with YouTube URL."""
        user_id = update.effective_user.id
        
        if not self.is_user_authorized(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        # Check if user already has an active workflow
        if user_id in self.active_workflows:
            await update.message.reply_text(
                "⚠️ You already have an active workflow. Use `/cancel` to stop it first."
            )
            return
        
        # Get YouTube URL from command arguments
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a YouTube channel URL.\n\n"
                "Example: `/process https://www.youtube.com/@channelname`"
            )
            return
        
        youtube_url = context.args[0]
        await self._start_workflow(update, youtube_url)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        user_id = update.effective_user.id
        
        if not self.is_user_authorized(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        if user_id not in self.active_workflows:
            await update.message.reply_text("📊 No active workflow.")
            return
        
        workflow_id = self.active_workflows[user_id]
        await update.message.reply_text(
            f"📊 **Workflow Status**\n\n"
            f"Workflow ID: `{workflow_id}`\n"
            f"Status: Running\n"
            f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Use `/cancel` to stop the workflow.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command."""
        user_id = update.effective_user.id
        
        if not self.is_user_authorized(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        if user_id not in self.active_workflows:
            await update.message.reply_text("❌ No active workflow to cancel.")
            return
        
        workflow_id = self.active_workflows.pop(user_id)
        await update.message.reply_text(
            f"✅ Workflow `{workflow_id}` has been cancelled.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular messages (YouTube URLs)."""
        user_id = update.effective_user.id
        
        if not self.is_user_authorized(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        message_text = update.message.text
        
        # Check if message contains a YouTube URL
        if self._is_youtube_url(message_text):
            # Check if user already has an active workflow
            if user_id in self.active_workflows:
                await update.message.reply_text(
                    "⚠️ You already have an active workflow. Use `/cancel` to stop it first."
                )
                return
            
            await self._start_workflow(update, message_text)
        else:
            await update.message.reply_text(
                "🤔 I can only process YouTube URLs (channels or videos).\n\n"
                "Please send me a YouTube URL or use `/help` for more information."
            )
    
    def _is_youtube_url(self, text: str) -> bool:
        """Check if text contains a YouTube URL."""
        youtube_patterns = [
            'youtube.com/@',
            'youtube.com/c/',
            'youtube.com/channel/',
            'youtube.com/user/',
            'youtube.com/watch?v=',  # Video URLs
            'youtube.com/embed/',    # Embed URLs
            'youtu.be/'              # Short URLs
        ]
        
        return any(pattern in text.lower() for pattern in youtube_patterns)
    
    async def _start_workflow(self, update: Update, youtube_url: str) -> None:
        """Start workflow and send initial progress message."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Send initial progress message
        initial_message = await update.message.reply_text(
            "🚀 **YouTube Comment Bot Starting...**\n\n"
            "📊 Progress: 0%\n"
            "📺 Channel: Analyzing...\n"
            "⏱️ Step: 0/6\n"
            "░░░░░░░░░░ 0%\n\n"
            "🔍 Initializing workflow...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Store the message for live updates
        self.progress_messages[user_id] = initial_message
        
        # Store initial message ID for later deletion
        self.progress_message_ids[user_id] = [initial_message.message_id]
        
        # Generate workflow ID
        workflow_id = f"workflow_{user_id}_{int(datetime.now().timestamp())}"
        
        # Store active workflow
        self.active_workflows[user_id] = workflow_id
                
        try:
            # Use the callback to start the workflow
            if self.workflow_callback:
                await self.workflow_callback(workflow_id, youtube_url, user_id, chat_id)
            else:
                logger.error("No workflow callback set")
                await update.message.reply_text("❌ Bot configuration error. Please contact admin.")
        
        except Exception as e:
            logger.error(f"Error starting workflow: {e}")
            await update.message.reply_text(f"❌ Failed to start workflow: {str(e)}")
            
            # Clean up on error
            if user_id in self.active_workflows:
                del self.active_workflows[user_id]
            if user_id in self.progress_messages:
                del self.progress_messages[user_id]
            if hasattr(self, 'progress_message_ids') and user_id in self.progress_message_ids:
                del self.progress_message_ids[user_id]
    
    async def send_live_progress_update(self, user_id: int, chat_id: int, agent_name: str, 
                                       status: str, progress: int, step: int, total_steps: int,
                                       channel_name: str = "Unknown", details: str = "") -> None:
        """Send live progress update by deleting previous message and sending new one."""
        try:
            # DELETE ALL PREVIOUS INTERMEDIATE MESSAGES FIRST
            await self._delete_all_intermediate_messages(user_id, chat_id)
            
            # DELETE PREVIOUS PROGRESS MESSAGE (if exists)
            if user_id in self.progress_messages:
                try:
                    await self.progress_messages[user_id].delete()
                    logger.debug(f"🗑️ Deleted previous progress message for user {user_id}")
                except Exception as e:
                    logger.debug(f"Could not delete previous progress message: {e}")
            
            # Create status emoji
            status_emoji = {
                "starting": "🔄",
                "completed": "✅",
                "error": "❌",
                "processing": "⚙️"
            }.get(status.lower(), "📊")
            
            # Create progress bar
            progress_bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
            
            # Format timestamp
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            
            # Create the message
            message = f"""
🤖 **YouTube Comment Bot**
{status_emoji} **{agent_name} {status.title()}**
📊 **Progress:** {progress}%
📺 **Channel:** {channel_name}
⏱️ **Step:** {step}/{total_steps}
{progress_bar} {progress}%
🕐 **Updated:** {timestamp}
{f"📋 **Details:** {details}" if details else ""}
            """.strip()
            
            # Send new progress message
            new_message = await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Store the new message for future updates
            self.progress_messages[user_id] = new_message
            
        except Exception as e:
            logger.error(f"Failed to send live progress update: {e}")
    
    async def _delete_all_intermediate_messages(self, user_id: int, chat_id: int) -> None:
        """Delete all stored intermediate messages (auto-approval, auto-approved, comment success messages)."""
        try:
            if user_id in self.progress_message_ids:
                message_ids = self.progress_message_ids[user_id].copy()
                
                # Delete all stored intermediate messages
                for message_id in message_ids:
                    try:
                        await self.application.bot.delete_message(
                            chat_id=chat_id,
                            message_id=message_id
                        )
                        logger.debug(f"🗑️ Deleted intermediate message {message_id} for user {user_id}")
                    except Exception as e:
                        logger.debug(f"Could not delete intermediate message {message_id}: {e}")
                
                # Clear the stored message IDs
                self.progress_message_ids[user_id] = []
                
        except Exception as e:
            logger.debug(f"Error deleting intermediate messages: {e}")

    async def send_progress_update(self, user_id: int, chat_id: int, agent_name: str, 
                                   status: str, details: str = "") -> None:
        """Send progress update to user (fallback method)."""
        try:
            # Create status emoji
            status_emoji = {
                "starting": "🔄",
                "completed": "✅",
                "failed": "❌",
                "in_progress": "⏳"
            }.get(status.lower(), "📝")
            
            message = f"{status_emoji} **{agent_name}**\n\n"
            message += f"Status: {status.title()}\n"
            
            if details:
                message += f"Details: {details}\n"
            
            message += f"\nTime: {datetime.now().strftime('%H:%M:%S')}"
            
            progress_msg = await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
            # Store message ID for deletion
            if user_id not in self.progress_message_ids:
                self.progress_message_ids[user_id] = []
            self.progress_message_ids[user_id].append(progress_msg.message_id)
            
        except Exception as e:
            logger.error(f"Error sending progress update to user {user_id}: {e}")
    
    async def send_workflow_completion(self, user_id: int, chat_id: int, 
                                       workflow_id: str, success: bool, 
                                       summary: Dict[str, Any]) -> None:
        """Send workflow completion notification with comment links."""
        try:
            # COMPREHENSIVE MESSAGE CLEANUP - DELETE ALL PREVIOUS MESSAGES
            await self._delete_all_messages_comprehensively(user_id, chat_id)
            
            # Remove from active workflows
            if user_id in self.active_workflows:
                del self.active_workflows[user_id]
            
            # Clean up progress message references
            if user_id in self.progress_messages:
                del self.progress_messages[user_id]
            
            # Clear auto-approval mode for this workflow
            self.clear_workflow_auto_approval(workflow_id)
            
            if success:
                message = "🎉 **Workflow Completed Successfully!**\n\n"
                message += f"🆔 Workflow ID: `{workflow_id}`\n"
                message += f"📺 Channel: {summary.get('channel_name', 'Unknown')}\n"
                message += f"🎬 Videos processed: {summary.get('videos_processed', 0)}\n"
                message += f"💬 Comments generated: {summary.get('comments_generated', 0)}\n"
                message += f"📝 Comments posted: {summary.get('comments_posted', 0)}\n"
                message += f"📊 Success rate: {summary.get('success_rate', 0)}%\n\n"
                
                # Add comment links if available
                posted_comments = summary.get('posted_comments', [])
                if posted_comments:
                    message += "🔗 **Posted Comments:**\n"
                    for i, comment_info in enumerate(posted_comments, 1):
                        video_title = comment_info.get('video_title', f'Video {i}')[:30]
                        comment_url = comment_info.get('comment_url', '')
                        if comment_url:
                            message += f"• [{video_title}...]({comment_url})\n"
                        else:
                            message += f"• {video_title}... (URL unavailable)\n"
                    message += "\n"
                
                message += "Thank you for using the YouTube Comment Bot! 🤖"
            else:
                message = "❌ **Workflow Failed**\n\n"
                message += f"🆔 Workflow ID: `{workflow_id}`\n"
                message += f"❗ Error: {summary.get('error', 'Unknown error')}\n\n"
                message += "Please try again or contact support if the problem persists."
            
            # Send the final completion message (this is the ONLY message that should remain)
            final_message = await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
            logger.info(f"🎉 Final completion message sent to user {user_id}. All previous messages deleted.")
            
        except Exception as e:
            logger.error(f"Error sending completion notification to user {user_id}: {e}")
    
    async def _delete_all_messages_comprehensively(self, user_id: int, chat_id: int) -> None:
        """Delete ALL previous messages comprehensively - progress, intermediate, and final cleanup."""
        try:
            logger.info(f"🗑️ Starting comprehensive message cleanup for user {user_id}")
            
            # 1. Delete the current progress message (if exists)
            if user_id in self.progress_messages:
                try:
                    await self.progress_messages[user_id].delete()
                    logger.debug(f"🗑️ Deleted current progress message for user {user_id}")
                except Exception as e:
                    logger.debug(f"Could not delete current progress message: {e}")
            
            # 2. Delete all stored intermediate messages (auto-approval, comment success, etc.)
            if user_id in self.progress_message_ids:
                message_ids = self.progress_message_ids[user_id].copy()
                logger.info(f"🗑️ Deleting {len(message_ids)} stored intermediate messages for user {user_id}")
                
                for message_id in message_ids:
                    try:
                        await self.application.bot.delete_message(
                            chat_id=chat_id,
                            message_id=message_id
                        )
                        logger.debug(f"🗑️ Deleted intermediate message {message_id}")
                    except Exception as e:
                        logger.debug(f"Could not delete intermediate message {message_id}: {e}")
                
                # Clear the stored message IDs
                self.progress_message_ids[user_id] = []
            
            # 3. Additional cleanup for any remaining references
            cleanup_count = 0
            
            # Clean up progress message references
            if user_id in self.progress_messages:
                del self.progress_messages[user_id]
                cleanup_count += 1
            
            # Clean up progress message IDs
            if user_id in self.progress_message_ids:
                del self.progress_message_ids[user_id]
                cleanup_count += 1
            
            logger.info(f"🧹 Comprehensive cleanup completed for user {user_id}. Cleaned {cleanup_count} references.")
            
        except Exception as e:
            logger.error(f"Error in comprehensive message cleanup for user {user_id}: {e}")
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all callback queries and route to appropriate handlers."""
        query = update.callback_query
        
        # Check if this is an approval callback
        if query.data and (query.data.startswith("approve_") or query.data.startswith("reject_")):
            await self.handle_approval_callback(update, context)
        else:
            # Handle other callback types here if needed
            await query.answer("Unknown callback action")
            logger.warning(f"Unknown callback query: {query.data}")

    async def handle_approval_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle approval button callbacks."""
        query = update.callback_query
        await query.answer()
        
        logger.info(f"🔔 Received approval callback: {query.data}")
        
        user_id = update.effective_user.id
        if not self.is_user_authorized(user_id):
            logger.warning(f"❌ Unauthorized user {user_id} tried to use approval callback")
            await query.edit_message_text("❌ You are not authorized to use this bot.")
            return
        
        callback_data = query.data
        logger.info(f"📝 Processing callback data: {callback_data}")
        
        # Handle batch approval actions
        if callback_data == "approve_all":
            await self._handle_approve_all(query, user_id)
            return
        elif callback_data == "reject_all":
            await self._handle_reject_all(query, user_id)
            return
        
        # Handle individual approval responses
        if callback_data.startswith("approve_") or callback_data.startswith("reject_"):
            callback_id = callback_data.split("_", 1)[1]
            action = callback_data.split("_", 1)[0]
            
            logger.info(f"🎯 Callback ID: {callback_id}, Action: {action}")
            logger.info(f"📋 Available callbacks: {list(approval_callbacks.keys())}")
            
            if callback_id in approval_callbacks:
                callback_future = approval_callbacks[callback_id]
                
                logger.info(f"✅ Found matching callback future for ID: {callback_id}")
                
                if action == "approve":
                    updated_message = await query.edit_message_text("✅ **Comment Approved!** Posting now...")
                    # Store this updated message ID for deletion
                    if user_id not in self.progress_message_ids:
                        self.progress_message_ids[user_id] = []
                    self.progress_message_ids[user_id].append(updated_message.message_id)
                    logger.debug(f"📝 Stored approval response message ID {updated_message.message_id} for deletion")
                    
                    callback_future.set_result(True)
                    logger.info(f"👍 Comment approved by user {user_id}")
                else:  # reject
                    updated_message = await query.edit_message_text("❌ **Comment Rejected** - Skipping post")
                    # Store this updated message ID for deletion
                    if user_id not in self.progress_message_ids:
                        self.progress_message_ids[user_id] = []
                    self.progress_message_ids[user_id].append(updated_message.message_id)
                    logger.debug(f"📝 Stored rejection response message ID {updated_message.message_id} for deletion")
                    
                    callback_future.set_result(False)
                    logger.info(f"👎 Comment rejected by user {user_id}")
                
                # Clean up callback
                del approval_callbacks[callback_id]
                logger.info(f"🧹 Cleaned up callback ID: {callback_id}")
            else:
                logger.warning(f"⚠️ No matching callback found for ID: {callback_id}")
                await query.edit_message_text("⚠️ This approval request has expired.")
        else:
            logger.warning(f"⚠️ Invalid callback data format: {callback_data}")
    
    async def _handle_approve_all(self, query, user_id: int):
        """Handle approve all button press."""
        try:
            # Get all pending approvals for this user
            user_pending = pending_batch_approvals.get(user_id, [])
            
            # Set global auto-approval mode for this user's current workflow
            current_workflow_id = user_workflow_mapping.get(user_id)
            if current_workflow_id:
                self.set_workflow_auto_approval(current_workflow_id, user_id, "approve_all")
            
            if not user_pending:
                # Even if no pending approvals, set auto-approval mode for future comments
                updated_message = await query.edit_message_text(
                    "✅ **Auto-Approval Mode Activated!**\n\n"
                    "🎯 **All future comments** in this workflow will be **automatically approved**.\n"
                    "🚀 **No more approval requests** - full automation enabled!"
                )
                
                # Store this message ID for deletion
                if user_id not in self.progress_message_ids:
                    self.progress_message_ids[user_id] = []
                if hasattr(updated_message, 'message_id'):
                    self.progress_message_ids[user_id].append(updated_message.message_id)
                return
            
            approved_count = 0
            for callback_id in user_pending[:]:  # Copy list to avoid modification during iteration
                if callback_id in approval_callbacks:
                    callback_future = approval_callbacks[callback_id]
                    callback_future.set_result(True)
                    del approval_callbacks[callback_id]
                    user_pending.remove(callback_id)
                    approved_count += 1
                    logger.info(f"✅ Auto-approved callback ID: {callback_id}")
            
            # Clear user's pending approvals
            if user_id in pending_batch_approvals:
                del pending_batch_approvals[user_id]
            
            updated_message = await query.edit_message_text(
                f"✅ **Auto-Approval Mode Activated!**\n\n"
                f"📊 **{approved_count} comments** approved immediately.\n"
                f"🎯 **All future comments** will be **automatically approved**.\n"
                f"🚀 **Full automation enabled** - no more approval requests!"
            )
            
            # Store this message ID for deletion
            if user_id not in self.progress_message_ids:
                self.progress_message_ids[user_id] = []
            if hasattr(updated_message, 'message_id'):
                self.progress_message_ids[user_id].append(updated_message.message_id)
            
            logger.info(f"🎉 User {user_id} approved all {approved_count} pending comments and enabled auto-approval")
            
        except Exception as e:
            logger.error(f"❌ Error handling approve all: {e}")
            await query.edit_message_text("❌ Error processing approve all request.")
    
    async def _handle_reject_all(self, query, user_id: int):
        """Handle reject all button press."""
        try:
            # Get all pending approvals for this user
            user_pending = pending_batch_approvals.get(user_id, [])
            
            # Set global auto-rejection mode for this user's current workflow
            current_workflow_id = user_workflow_mapping.get(user_id)
            if current_workflow_id:
                self.set_workflow_auto_approval(current_workflow_id, user_id, "reject_all")
            
            if not user_pending:
                # Even if no pending approvals, set auto-rejection mode for future comments
                updated_message = await query.edit_message_text(
                    "❌ **Auto-Rejection Mode Activated!**\n\n"
                    "🚫 **All future comments** in this workflow will be **automatically rejected**.\n"
                    "⏭️ **No more approval requests** - skipping all remaining comments!"
                )
                
                # Store this message ID for deletion
                if user_id not in self.progress_message_ids:
                    self.progress_message_ids[user_id] = []
                if hasattr(updated_message, 'message_id'):
                    self.progress_message_ids[user_id].append(updated_message.message_id)
                    logger.debug(f"📝 Stored 'reject all' activation message ID {updated_message.message_id} for deletion")
                return
            
            rejected_count = 0
            for callback_id in user_pending[:]:  # Copy list to avoid modification during iteration
                if callback_id in approval_callbacks:
                    callback_future = approval_callbacks[callback_id]
                    callback_future.set_result(False)
                    del approval_callbacks[callback_id]
                    user_pending.remove(callback_id)
                    rejected_count += 1
                    logger.info(f"❌ Auto-rejected callback ID: {callback_id}")
            
            # Clear user's pending approvals
            if user_id in pending_batch_approvals:
                del pending_batch_approvals[user_id]
            
            updated_message = await query.edit_message_text(
                f"❌ **Auto-Rejection Mode Activated!**\n\n"
                f"📊 **{rejected_count} comments** rejected immediately.\n"
                f"🚫 **All future comments** will be **automatically rejected**.\n"
                f"⏭️ **Skipping all remaining comments** - workflow continuing!"
            )
            
            # Store this message ID for deletion
            if user_id not in self.progress_message_ids:
                self.progress_message_ids[user_id] = []
            if hasattr(updated_message, 'message_id'):
                self.progress_message_ids[user_id].append(updated_message.message_id)
                logger.debug(f"📝 Stored 'reject all' batch message ID {updated_message.message_id} for deletion")
            
            logger.info(f"🚫 User {user_id} rejected all {rejected_count} pending comments and enabled auto-rejection")
            
        except Exception as e:
            logger.error(f"❌ Error handling reject all: {e}")
            await query.edit_message_text("❌ Error processing reject all request.")
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors that occur during bot operation."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # If we have an update with a message, try to inform the user
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ An error occurred while processing your request. "
                    "Please try again or contact support if the problem persists."
                )
            except Exception as e:
                logger.error(f"Error sending error message to user: {e}")
    
    async def setup_application(self) -> Application:
        """Set up the Telegram application with handlers."""
        # Build application
        application = ApplicationBuilder().token(self.bot_token).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("process", self.process_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("cancel", self.cancel_command))
        
        # Add message handler for YouTube URLs
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Add callback query handler
        application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        # Add error handler
        application.add_error_handler(self.error_handler)
        
        self.application = application
        logger.info("Telegram application setup completed")
        
        return application
    
    async def start_polling(self) -> None:
        """Start the bot with polling."""
        if not self.application:
            await self.setup_application()
        
        logger.info("Starting Telegram bot polling...")
        
        try:
            # Initialize and start the application
            await self.application.initialize()
            await self.application.start()
            
            # Start polling in a way that's compatible with FastAPI
            # Use the updater directly for non-blocking polling
            updater = self.application.updater
            await updater.start_polling(drop_pending_updates=True)
            
            logger.info("Telegram bot is now running and polling for updates")
            
        except Exception as e:
            logger.error(f"Error during bot polling: {e}")
            raise
    
    async def stop_polling(self) -> None:
        """Stop the bot polling gracefully."""
        if self.application:
            logger.info("Stopping Telegram bot polling...")
            
            try:
                # Stop the updater first with timeout
                if self.application.updater:
                    logger.info("Stopping updater...")
                    await asyncio.wait_for(self.application.updater.stop(), timeout=5.0)
                    logger.info("Updater stopped")
                
                # Stop the application with timeout
                logger.info("Stopping application...")
                await asyncio.wait_for(self.application.stop(), timeout=5.0)
                logger.info("Application stopped")
                
                # Shutdown the application with timeout
                logger.info("Shutting down application...")
                await asyncio.wait_for(self.application.shutdown(), timeout=5.0)
                logger.info("Application shutdown complete")
                
            except asyncio.TimeoutError:
                logger.warning("Telegram bot shutdown timed out, forcing shutdown")
            except Exception as e:
                logger.error(f"Error during Telegram bot shutdown: {e}")
            finally:
                self.application = None
            logger.info("Telegram bot stopped")
        else:
            logger.info("Telegram bot was not running")
    
    # Legacy methods for backward compatibility
    async def send_message(self, chat_id: int, text: str, **kwargs):
        """Send a message to a chat and return the message object."""
        if not self.application:
            logger.error("Telegram application not initialized")
            return None
        
        try:
            # Set default parse_mode if not provided
            if 'parse_mode' not in kwargs:
                kwargs['parse_mode'] = ParseMode.MARKDOWN
            
            message = await self.application.bot.send_message(
                chat_id=chat_id,
                text=text,
                **kwargs
            )
            return message
        except Exception as e:
            logger.error(f"Error sending message to chat {chat_id}: {e}")
            return None
    
    async def send_notification(self, user_id: int, message: str) -> None:
        """Send notification to a specific user."""
        await self.send_message(chat_id=user_id, text=message)

    async def send_startup_welcome_message(self) -> None:
        """Send welcome message to all authorized users when bot starts."""
        if not self.application or not self.allowed_users:
            return
        
        startup_message = """
🎉 **AI YouTube Comment Agent is ONLINE!**

🤖 **Tizlion's AI Agent** is ready to supercharge your YouTube engagement!

🔗 **GitHub**: [Tiz Lion](https://github.com/Tiz20lion)

✨ **Ready to:**
• Process YouTube channels with AI
• Generate smart, engaging comments  
• Auto-post with perfect timing

🚀 **Just send me 1-2 YouTube URLs to get started!**

Type `/help` for the complete guide 📖
        """
        
        for user_id in self.allowed_users:
            try:
                welcome_msg = await self.application.bot.send_message(
                    chat_id=user_id,
                    text=startup_message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
                # Store startup message ID for potential deletion
                if user_id not in self.progress_message_ids:
                    self.progress_message_ids[user_id] = []
                self.progress_message_ids[user_id].append(welcome_msg.message_id)
                logger.info(f"Startup welcome message sent to user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to send startup message to user {user_id}: {e}")

    async def request_comment_approval(
        self, 
        user_id: int, 
        video_title: str, 
        video_url: str, 
        comment_text: str,
        timeout: int = 300,  # 5 minutes timeout
        auto_approve_on_timeout: bool = True,  # New parameter for auto-approval
        workflow_id: str = None  # Add workflow_id parameter
    ) -> bool:
        """
        Request user approval for posting a comment.
        
        Args:
            user_id: Telegram user ID to send approval request to
            video_title: Title of the video
            video_url: URL of the video
            comment_text: Generated comment text
            timeout: Timeout in seconds (default 5 minutes)
            auto_approve_on_timeout: If True, auto-approve on timeout (default True)
            workflow_id: Current workflow ID for auto-approval mode checking
            
        Returns:
            True if approved, False if rejected, True if auto-approved on timeout
        """
        try:
            # Check for auto-approval mode first
            if workflow_id:
                auto_mode = self.get_workflow_auto_approval(workflow_id)
                if auto_mode == "approve_all":
                    logger.info(f"🎯 Auto-approving comment for '{video_title}' due to workflow auto-approval mode")
                    try:
                        auto_approve_msg = await self.application.bot.send_message(
                            chat_id=user_id,
                            text=f"✅ **Auto-Approved** (Mode: Approve All)\n\n📹 **Video:** {video_title[:80]}...\n💬 **Comment:** \"{comment_text[:100]}...\"\n\n🚀 **Posting automatically...**",
                            parse_mode="Markdown"
                        )
                        
                        # Store this message ID for deletion
                        if user_id not in self.progress_message_ids:
                            self.progress_message_ids[user_id] = []
                        self.progress_message_ids[user_id].append(auto_approve_msg.message_id)
                        logger.debug(f"📝 Stored auto-approval message ID {auto_approve_msg.message_id} for deletion")
                        
                    except Exception as e:
                        logger.error(f"Failed to send auto-approval notification: {e}")
                    return True
                elif auto_mode == "reject_all":
                    logger.info(f"🚫 Auto-rejecting comment for '{video_title}' due to workflow auto-approval mode")
                    try:
                        await self.application.bot.send_message(
                            chat_id=user_id,
                            text=f"❌ **Auto-Rejected** (Mode: Reject All)\n\n📹 **Video:** {video_title[:80]}...\n💬 **Comment:** \"{comment_text[:100]}...\"\n\n⏭️ **Skipping automatically...**",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send auto-rejection notification: {e}")
                    return False
            
            # Check if Telegram application is properly initialized
            if not self.application:
                logger.error("Telegram application not initialized - cannot request approval")
                return False
            
            import uuid
            callback_id = str(uuid.uuid4())
            
            # Add to user's pending approvals for batch processing
            if user_id not in pending_batch_approvals:
                pending_batch_approvals[user_id] = []
            pending_batch_approvals[user_id].append(callback_id)
            
            # Check if this is the first approval request - if so, include batch buttons
            is_first_request = len(pending_batch_approvals[user_id]) == 1
            
            # Create inline keyboard with approve/reject buttons and batch options
            if is_first_request:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{callback_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{callback_id}")
                    ],
                    [
                        InlineKeyboardButton("🎯 Approve All", callback_data="approve_all"),
                        InlineKeyboardButton("🚫 Reject All", callback_data="reject_all")
                    ]
                ]
            else:
                # For subsequent requests, just show individual buttons
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{callback_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{callback_id}")
                    ]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Create approval message with enhanced information
            pending_count = len(pending_batch_approvals[user_id])
            timeout_action = "auto-approve" if auto_approve_on_timeout else "skip"
            
            message = f"""
🤖 **Comment Approval Required** ({pending_count} pending)

📹 **Video:** {video_title[:80]}...
🔗 **Link:** [Open Video]({video_url})

💬 **Generated Comment:**
"{comment_text}"

⏰ **Timeout:** {timeout//60} minutes (will {timeout_action})
{"🎯 **Batch Options:** Use 'Approve All' or 'Reject All' for multiple comments" if is_first_request else ""}

**Do you want to post this comment?**
            """.strip()
            
            # Send approval request
            try:
                approval_message_obj = await self.application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                
                # Store this message ID for deletion
                if user_id not in self.progress_message_ids:
                    self.progress_message_ids[user_id] = []
                self.progress_message_ids[user_id].append(approval_message_obj.message_id)
                
            except Exception as e:
                logger.error(f"Failed to send approval request message: {e}")
                # Clean up on failure
                if callback_id in pending_batch_approvals.get(user_id, []):
                    pending_batch_approvals[user_id].remove(callback_id)
                return False
            
            # Create future for callback result
            callback_future = asyncio.Future()
            approval_callbacks[callback_id] = callback_future
            
            # Wait for response with timeout
            try:
                result = await asyncio.wait_for(callback_future, timeout=timeout)
                
                # Clean up pending approval
                if callback_id in pending_batch_approvals.get(user_id, []):
                    pending_batch_approvals[user_id].remove(callback_id)
                
                return result
                
            except asyncio.TimeoutError:
                # Clean up expired callback
                if callback_id in approval_callbacks:
                    del approval_callbacks[callback_id]
                
                # Clean up pending approval
                if callback_id in pending_batch_approvals.get(user_id, []):
                    pending_batch_approvals[user_id].remove(callback_id)
                
                # Handle timeout based on auto_approve_on_timeout setting
                if auto_approve_on_timeout:
                    # Send auto-approval message
                    try:
                        await self.application.bot.send_message(
                            chat_id=user_id,
                            text=f"⏰ **Auto-Approved (Timeout)**\n\nNo response received for comment on '{video_title[:50]}...' - Auto-approving and posting comment.",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send auto-approval message: {e}")
                    
                    logger.info(f"⏰ Auto-approved comment on timeout for user {user_id}")
                    return True
                else:
                    # Send timeout message
                    try:
                        await self.application.bot.send_message(
                            chat_id=user_id,
                            text=f"⏰ **Approval Timeout**\n\nNo response received for comment on '{video_title[:50]}...' - Skipping post.",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send timeout message: {e}")
                    
                    logger.info(f"⏰ Comment approval timed out for user {user_id}")
                    return False
                
        except Exception as e:
            logger.error(f"Failed to request comment approval: {e}")
            # Clean up on error
            if callback_id in approval_callbacks:
                del approval_callbacks[callback_id]
            if user_id in pending_batch_approvals and callback_id in pending_batch_approvals[user_id]:
                pending_batch_approvals[user_id].remove(callback_id)
            return False

    async def request_batch_comment_approval(
        self,
        user_id: int,
        videos_with_comments: List[Dict[str, Any]],
        timeout: int = 600,  # 10 minutes for batch approval
        auto_approve_on_timeout: bool = True
    ) -> List[bool]:
        """
        Request batch approval for multiple comments.
        
        Args:
            user_id: Telegram user ID to send approval request to
            videos_with_comments: List of video dictionaries with generated comments
            timeout: Timeout in seconds (default 10 minutes)
            auto_approve_on_timeout: If True, auto-approve on timeout
            
        Returns:
            List of approval results (True/False for each video)
        """
        try:
            if not self.application:
                logger.error("Telegram application not initialized - cannot request batch approval")
                return [False] * len(videos_with_comments)
            
            if not videos_with_comments:
                return []
            
            # Send batch approval summary message
            summary_message = f"""
🎯 **Batch Comment Approval Required**

📊 **Total Comments:** {len(videos_with_comments)}
⏰ **Timeout:** {timeout//60} minutes (will {'auto-approve all' if auto_approve_on_timeout else 'skip all'})

**Videos to Comment On:**
"""
            
            for i, video in enumerate(videos_with_comments[:5], 1):  # Show first 5 videos
                title = video.get('title', 'Unknown')[:40]
                summary_message += f"{i}. {title}...\n"
            
            if len(videos_with_comments) > 5:
                summary_message += f"... and {len(videos_with_comments) - 5} more videos\n"
            
            summary_message += f"""
🎯 **Options:**
• **Approve All** - Post all {len(videos_with_comments)} comments
• **Reject All** - Skip all comments
• **Individual** - Review each comment separately

**Choose your approach:**
            """
            
            # Create batch approval keyboard
            keyboard = [
                [
                    InlineKeyboardButton("🎯 Approve All", callback_data="approve_all"),
                    InlineKeyboardButton("🚫 Reject All", callback_data="reject_all")
                ],
                [
                    InlineKeyboardButton("📝 Review Individual", callback_data="review_individual")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send batch summary message
            try:
                batch_message = await self.application.bot.send_message(
                    chat_id=user_id,
                    text=summary_message,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                
                # Store this message ID for deletion
                if user_id not in self.progress_message_ids:
                    self.progress_message_ids[user_id] = []
                self.progress_message_ids[user_id].append(batch_message.message_id)
                
            except Exception as e:
                logger.error(f"Failed to send batch approval summary: {e}")
                return [False] * len(videos_with_comments)
            
            # Set up batch approval tracking
            import uuid
            batch_id = str(uuid.uuid4())
            batch_approval_callbacks[batch_id] = {
                "user_id": user_id,
                "videos": videos_with_comments,
                "results": [None] * len(videos_with_comments),
                "timeout": timeout,
                "auto_approve": auto_approve_on_timeout
            }
            
            # For now, fall back to individual approvals
            # This will be enhanced based on user choice
            results = []
            for video in videos_with_comments:
                video_title = video.get('title', 'Unknown')
                video_url = video.get('url', '')
                comment_text = video.get('generated_comment', '')
                
                if comment_text:
                    approval = await self.request_comment_approval(
                        user_id=user_id,
                        video_title=video_title,
                        video_url=video_url,
                        comment_text=comment_text,
                        timeout=timeout,
                        auto_approve_on_timeout=auto_approve_on_timeout
                    )
                    results.append(approval)
                else:
                    results.append(False)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to request batch comment approval: {e}")
            return [False] * len(videos_with_comments)


# Global instance
telegram_service = TelegramService() 