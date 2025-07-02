"""
FastAPI Application for YouTube Comment Automation

This is the main FastAPI application that orchestrates the YouTube comment automation workflow.
It provides REST API endpoints, web dashboard, and integrates with the Telegram bot service.
"""

import asyncio
import uuid
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import time
from pathlib import Path
import glob

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.utils.logging_config import get_logger, setup_logging

# Initialize logging system
setup_logging()
from app.models.schemas import ProcessChannelRequest, ProcessChannelResponse, UserLogin, PasswordReset, AuthResponse
from app.workflow.langgraph_workflow import get_workflow_instance, WorkflowState
from app.services.telegram_service import telegram_service
from app.services.metrics_service import metrics_service
from app.services.auth_service import auth_service
from app.middleware.auth_middleware import AuthMiddleware

# Get logger
logger = get_logger(__name__)

# Global state for active workflows and application metrics
active_workflows: Dict[str, Dict[str, Any]] = {}
telegram_bot_task: Optional[asyncio.Task] = None
websocket_connections: List[WebSocket] = []
app_start_time = time.time()

# Application metrics
app_metrics = {
    "total_workflows": 0,
    "successful_workflows": 0,
    "failed_workflows": 0,
    "total_comments_posted": 0,
    "uptime": 0
}

# Recent logs storage for live streaming
recent_logs: List[Dict[str, Any]] = []

# Store OAuth2 flows in memory (in production, use database or persistent storage)
oauth2_flows = {}

class WebSocketLogHandler(logging.Handler):
    """Custom log handler to broadcast logs via WebSocket."""
    
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname.lower(),
                "message": self.format(record),
                "module": record.module or "main"
            }
            
            # Add to recent logs (keep last 100)
            recent_logs.append(log_entry)
            if len(recent_logs) > 100:
                recent_logs.pop(0)
            
            # Broadcast to websocket clients
            asyncio.create_task(broadcast_log_entry(log_entry))
            
        except Exception:
            # Avoid infinite recursion if logging the error fails
            pass

async def broadcast_log_entry(log_entry: Dict[str, Any]):
    """Broadcast a single log entry to all WebSocket clients."""
    try:
        await broadcast_to_websockets({
            "type": "log_entry",
            "data": log_entry
        })
    except Exception:
        # Silently fail to avoid logging loops
        pass

# Request/Response models
class StartWorkflowRequest(BaseModel):
    youtube_url: str = Field(..., description="YouTube channel URL to process")
    user_id: Optional[int] = Field(None, description="Telegram user ID")
    chat_id: Optional[int] = Field(None, description="Telegram chat ID")

class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    created_at: str
    youtube_url: str
    current_step: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SystemInfoResponse(BaseModel):
    status: str
    active_workflows: int
    telegram_bot_status: str
    uptime: str
    version: str = "1.0.0"
    metrics: Dict[str, Any]

class ConfigurationResponse(BaseModel):
    telegram_configured: bool
    openrouter_configured: bool
    youtube_oauth_configured: bool
    port: int
    debug_mode: bool

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    module: str

# New models for configuration updates
class LLMConfigUpdate(BaseModel):
    model: str = Field(..., description="OpenRouter model name")

class VideoCountUpdate(BaseModel):
    max_videos: int = Field(..., ge=1, le=50, description="Maximum videos to fetch (1-50)")

class BotControlRequest(BaseModel):
    action: str = Field(..., description="Bot action: start, stop, restart")

class CommentPostingToggle(BaseModel):
    enabled: bool = Field(..., description="Enable or disable comment posting")

class ConfigurationDetailsResponse(BaseModel):
    current_llm_model: str
    available_models: List[str]
    max_videos: int
    telegram_bot_status: str
    telegram_configured: bool
    openrouter_configured: bool
    youtube_oauth_configured: bool
    comment_posting_enabled: bool
    oauth2_authenticated: bool

# New Settings Management Models
class APIKeysUpdate(BaseModel):
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter API key")
    youtube_api_key: Optional[str] = Field(None, description="YouTube Data API key")
    google_client_id: Optional[str] = Field(None, description="Google OAuth2 Client ID")
    google_client_secret: Optional[str] = Field(None, description="Google OAuth2 Client Secret")

class TelegramSettingsUpdate(BaseModel):
    bot_token: Optional[str] = Field(None, description="Telegram Bot Token")
    allowed_user_ids: Optional[str] = Field(None, description="Comma-separated list of allowed user IDs (user ID = chat ID)")

class OAuth2Setup(BaseModel):
    action: str = Field(..., description="OAuth2 action: generate_url, complete_auth, disconnect")
    response_url: Optional[str] = Field(None, description="OAuth2 response URL for completion")

class SettingsResponse(BaseModel):
    api_keys: Dict[str, Optional[str]]
    telegram_settings: Dict[str, Optional[str]]
    oauth2_status: Dict[str, Any]
    configuration_status: Dict[str, bool]
    # Enhanced: Add detailed token validation states
    token_validation_states: Dict[str, str]

class MetricsResponse(BaseModel):
    total_comments_posted: int
    total_videos_processed: int
    total_workflows: int
    agent_statistics: Dict[str, Any]
    engagement_metrics: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]
    video_details: List[Dict[str, Any]]
    last_updated: str

class VideoEngagementResponse(BaseModel):
    video_details: List[Dict[str, Any]]
    total_likes: int
    total_replies: int
    average_engagement: Dict[str, float]

async def start_telegram_bot():
    """Start the Telegram bot in the background."""
    global telegram_bot_task
    
    try:
        logger.info("Starting Telegram bot...")
        
        # First, check if the service is properly configured
        if not telegram_service.is_configured():
            # Check for specific configuration issues to provide detailed error messages
            from app.config import settings
            
            if not settings.TELEGRAM_BOT_TOKEN or any(placeholder in settings.TELEGRAM_BOT_TOKEN.lower() for placeholder in [
                'your_telegram_bot_token_here', 'your_bot_token_here', 
                'enter_your_bot_token', 'bot_token_placeholder'
            ]):
                raise Exception("Placeholder bot token detected - please configure your actual Telegram Bot Token in Settings")
            
            if not settings.TELEGRAM_ALLOWED_USERS or any(placeholder in settings.TELEGRAM_ALLOWED_USERS.lower() for placeholder in [
                'your_telegram_user_id_here', 'your_user_id_here', 
                'enter_your_user_id', 'user_id_placeholder'
            ]):
                raise Exception("Placeholder user ID detected - please configure your actual Telegram User ID in Settings")
            
            # Generic configuration error
            raise Exception("Telegram bot not configured - please check your Bot Token and User IDs in Settings")
        
        # Check for configuration errors stored during initialization
        if hasattr(telegram_service, '_config_error') and telegram_service._config_error:
            raise Exception(telegram_service._config_error)
        
        # Set up workflow callback
        telegram_service.set_workflow_callback(start_workflow_from_telegram)
        
        # Start polling in background task
        telegram_bot_task = asyncio.create_task(telegram_service.start_polling())
        
        # Wait a moment for the bot to initialize
        await asyncio.sleep(2)
        
        # Check if the bot is actually running after start_polling
        if not telegram_service.running:
            raise Exception("Bot failed to start polling - check your bot token and configuration")
        
        # Try to send welcome message (this will also validate the bot works)
        await telegram_service.send_welcome_message_to_users()
        
        logger.info("Telegram bot started successfully")
        
        # Broadcast successful start status
        try:
            await broadcast_to_websockets({
                "type": "telegram_status",
                "data": {
                    "status": "running",
                    "message": "Telegram bot started successfully"
                }
            })
        except:
            pass
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to start Telegram bot: {error_msg}")
        
        # Determine specific error type and create user-friendly message
        user_friendly_message = "Failed to start Telegram bot"
        if "rejected by the server" in error_msg.lower() or "unauthorized" in error_msg.lower():
            user_friendly_message = "Invalid bot token - please check your Telegram Bot Token in Settings"
        elif "invalid user id format" in error_msg.lower():
            user_friendly_message = "Invalid user IDs configured - please check your Allowed User IDs in Settings"
        elif "no users" in error_msg.lower():
            user_friendly_message = "No authorized users configured - please add your Telegram User ID in Settings"
        elif "placeholder bot token" in error_msg.lower():
            user_friendly_message = "Placeholder bot token detected - please configure your actual Telegram Bot Token in Settings"
        elif "placeholder user id" in error_msg.lower():
            user_friendly_message = "Placeholder user ID detected - please configure your actual Telegram User ID in Settings"
        elif "not configured" in error_msg.lower():
            user_friendly_message = "Telegram bot not configured - please check your Bot Token and User IDs in Settings"
        
        # Broadcast error status via WebSocket
        try:
            await broadcast_to_websockets({
                "type": "telegram_status",
                "data": {
                    "status": "failed",
                    "message": user_friendly_message,
                    "error_details": error_msg,
                    "suggestion": "Go to Settings → Configure your Telegram Bot Token and User ID"
                }
            })
        except:
            pass
        
        raise

async def stop_telegram_bot():
    """Stop the Telegram bot gracefully."""
    global telegram_bot_task
    
    try:
        logger.info("Stopping Telegram bot...")
        
        # Cancel the background task with timeout
        if telegram_bot_task and not telegram_bot_task.done():
            telegram_bot_task.cancel()
            try:
                await asyncio.wait_for(telegram_bot_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Telegram bot task cancellation timed out")
            except asyncio.CancelledError:
                logger.info("Telegram bot task cancelled")
        
        # Stop the service with timeout
        try:
            await asyncio.wait_for(telegram_service.stop_polling(), timeout=10.0)
            logger.info("Telegram bot stopped successfully")
        except asyncio.TimeoutError:
            logger.warning("Telegram bot stop_polling timed out")
        
    except Exception as e:
        logger.error(f"Error stopping Telegram bot: {e}")
    finally:
        telegram_bot_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown events."""
    # Startup
    logger.info("Starting YouTube Comment Bot application...")
    
    # First, ensure .env file exists
    logger.info("Checking environment configuration...")
    from app.utils.file_handler import ensure_env_file_exists, validate_env_credentials
    
    # Create .env from example.env if it doesn't exist
    env_created = ensure_env_file_exists()
    if not env_created:
        logger.error("❌ Failed to create .env file. Application may not work properly.")
    
    # Validate current credentials
    credential_status = validate_env_credentials()
    logger.info(f"📊 Credential Status: {credential_status}")
    
    # Show informative messages about configuration
    if not any(credential_status.values()):
        logger.warning("⚠️  No valid credentials found. Please configure your API keys through the settings page at http://localhost:7844/settings")
    else:
        configured_services = [service for service, configured in credential_status.items() if configured]
        logger.info(f"✅ Configured services: {', '.join(configured_services)}")
    
    # Set up WebSocket log handler for live streaming
    websocket_handler = WebSocketLogHandler()
    websocket_handler.setLevel(logging.INFO)
    logger.addHandler(websocket_handler)
    
    # Create necessary directories
    logger.info("Creating/verifying required directories...")
    settings.create_directories()
    
    # Start Telegram bot if token is configured
    if telegram_service.is_configured():
        try:
            await start_telegram_bot()
        except Exception as e:
            logger.error(f"Failed to start Telegram bot during startup: {e}")
    else:
        logger.warning("⚠️  Telegram bot token not configured - bot service disabled")
        logger.info("💡 Configure your bot token through the settings page to enable Telegram integration")
    
    logger.info("✅ Application startup completed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down YouTube Comment Bot application...")
    
    # Stop Telegram bot with timeout
    if telegram_service.is_configured():
        try:
            await asyncio.wait_for(stop_telegram_bot(), timeout=15.0)
        except asyncio.TimeoutError:
            logger.warning("Application shutdown timed out waiting for Telegram bot")
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
    
    logger.info("Application shutdown completed")

# Create FastAPI app with lifespan
app = FastAPI(
    title="YouTube Comment Bot API",
    description="Automated YouTube comment generation and posting system",
    version="1.0.0",
    lifespan=lifespan
)

# Setup templates and static files
templates = Jinja2Templates(directory="app/templates")
try:
    # Mount static files directory  
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers middleware to fix COOP issues
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # More permissive COOP policy for OAuth2 popups
        if request.url.path in ["/settings", "/oauth2callback"]:
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        else:
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
            
        # CSP header - allow popups for OAuth2 and external resources for UI
        if request.url.path == "/settings":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; "
                "script-src-elem 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                "style-src-elem 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' wss: ws:; "
                "frame-src 'none'; "
                "object-src 'none'; "
                "base-uri 'self'"
            )
        
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Add authentication middleware to protect all routes
app.add_middleware(AuthMiddleware)

# WebSocket connection manager
async def broadcast_to_websockets(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    if websocket_connections:
        disconnected = []
        for websocket in websocket_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected.append(websocket)
        
        # Remove disconnected WebSockets
        for ws in disconnected:
            if ws in websocket_connections:
                websocket_connections.remove(ws)

async def update_metrics():
    """Update application metrics."""
    global app_metrics
    app_metrics["uptime"] = int(time.time() - app_start_time)
    
    # Count workflow statuses
    completed_workflows = sum(1 for w in active_workflows.values() if w["status"] == "completed")
    failed_workflows = sum(1 for w in active_workflows.values() if w["status"] == "failed")
    
    app_metrics.update({
        "total_workflows": len(active_workflows),
        "successful_workflows": completed_workflows,
        "failed_workflows": failed_workflows,
    })
    
    # Broadcast metrics update
    await broadcast_to_websockets({
        "type": "metrics_update",
        "data": app_metrics
    })

async def start_workflow_from_telegram(workflow_id: str, youtube_url: str, user_id: int, chat_id: int) -> str:
    """Start a workflow from Telegram bot."""
    try:
        # Create workflow request
        request = StartWorkflowRequest(
            youtube_url=youtube_url,
            user_id=user_id,
            chat_id=chat_id
        )
        
        # Start workflow using the provided workflow_id
        actual_workflow_id = await start_workflow_internal(request, workflow_id)
        
        logger.info(f"Workflow {actual_workflow_id} started from Telegram for user {user_id}")
        return actual_workflow_id
        
    except Exception as e:
        logger.error(f"Error starting workflow from Telegram: {e}")
        raise

async def start_workflow_internal(request: StartWorkflowRequest, workflow_id: str = None) -> str:
    """Internal method to start a workflow."""
    # Use provided workflow ID or generate unique one
    if workflow_id is None:
        workflow_id = str(uuid.uuid4())
    
    # Initialize workflow state
    initial_state: WorkflowState = {
        "workflow_id": workflow_id,
        "youtube_url": request.youtube_url,
        "user_id": request.user_id,
        "chat_id": request.chat_id,
        "channel_data": None,
        "videos": [],
        "transcripts": {},
        "scraped_content": {},
        "analysis_results": {},
        "generated_comments": {},
        "posting_results": {},
        "current_step": "channel_parser",
        "status": "in_progress",
        "error": None,
        "progress": {
            "channel_parser": {"status": "pending"},
            "description_extractor": {"status": "pending"},
            "content_scraper": {"status": "pending"},
            "content_analyzer": {"status": "pending"},
            "comment_generator": {"status": "pending"},
            "comment_poster": {"status": "pending"}
        },
        "created_at": datetime.now().isoformat(),
        "completed_at": None
    }
    
    # Store workflow
    active_workflows[workflow_id] = {
        "state": initial_state,
        "created_at": datetime.now().isoformat(),
        "status": "running"
    }
    
    # Create and run workflow
    workflow_instance = get_workflow_instance()
    
    # Run workflow in background
    asyncio.create_task(run_workflow_background(workflow_instance, initial_state, workflow_id))
    
    return workflow_id

async def run_workflow_background(workflow_instance, initial_state: WorkflowState, workflow_id: str):
    """Run workflow in background and handle updates."""
    try:
        logger.info(f"Starting workflow execution for {workflow_id}")
        
        # Extract parameters from initial state
        channel_url = initial_state.get("youtube_url")
        chat_id = initial_state.get("chat_id")
        user_id = initial_state.get("user_id")
        
        # Execute workflow using the workflow instance method
        final_state = await workflow_instance.execute_workflow(
            channel_url=channel_url,
            user_id=str(user_id) if user_id else "",
            chat_id=str(chat_id) if chat_id else ""
        )
        
        # Update stored workflow
        active_workflows[workflow_id]["state"] = final_state
        active_workflows[workflow_id]["status"] = "completed"
        
        # Send completion notification
        if chat_id and user_id:
            success = final_state.get("status") == "completed"
            
            # Extract videos data
            videos = final_state.get("videos", [])
            
            # Count successful comment generations and postings
            comments_generated = sum(1 for video in videos if video.get("generated_comment"))
            comments_posted = sum(1 for video in videos if video.get("comment_posted", False))
            
            # Get posted comment details for links
            posted_comments = []
            for video in videos:
                if video.get("comment_posted", False):
                    posted_comments.append({
                        "video_title": video.get("title", "Unknown"),
                        "comment_url": video.get("comment_url", ""),
                        "comment_id": video.get("comment_id", ""),
                        "video_url": video.get("url", "")
                    })
            
            summary = {
                "channel_name": final_state.get("channel_name", "Unknown"),
                "videos_processed": len(videos),
                "comments_generated": comments_generated,
                "comments_posted": comments_posted,
                "success_rate": int((comments_posted / len(videos) * 100)) if videos else 0,
                "posted_comments": posted_comments,
                "error": final_state.get("error_message")
            }
            
            await telegram_service.send_workflow_completion(
                user_id=user_id,
                chat_id=chat_id,
                workflow_id=workflow_id,
                success=success,
                summary=summary
            )
        
        logger.info(f"Workflow {workflow_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error in workflow {workflow_id}: {e}")
        
        # Update workflow with error
        if workflow_id in active_workflows:
            active_workflows[workflow_id]["status"] = "failed"
            active_workflows[workflow_id]["state"]["status"] = "failed"
            active_workflows[workflow_id]["state"]["error"] = str(e)
        
        # Send error notification
        if chat_id and user_id:
            await telegram_service.send_workflow_completion(
                user_id=user_id,
                chat_id=chat_id,
                workflow_id=workflow_id,
                success=False,
                summary={"error": str(e)}
            )

def calculate_success_rate(final_state: WorkflowState) -> int:
    """Calculate success rate based on workflow state."""
    total_steps = 6  # Number of agents in the workflow
    completed_steps = 0
    
    # Count successful agent executions
    for agent_name in ["channel_parser", "content_scraper", "content_analyzer", "comment_generator", "comment_poster"]:
        if final_state.get(f"{agent_name}_success", False):
            completed_steps += 1
    
    return int((completed_steps / total_steps) * 100)

# API Routes



@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "telegram_bot": "running" if telegram_service.application else "stopped"
    }

@app.post("/api/v1/workflow/start", response_model=Dict[str, str])
async def start_workflow(request: StartWorkflowRequest, background_tasks: BackgroundTasks):
    """Start a new YouTube comment workflow."""
    try:
        workflow_id = await start_workflow_internal(request)
        
        logger.info(f"Workflow {workflow_id} started via API")
        
        return {
            "workflow_id": workflow_id,
            "status": "started",
            "message": "Workflow started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/workflow/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """Get the status of a specific workflow."""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow_data = active_workflows[workflow_id]
    state = workflow_data.get("state", {})
    
    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status=workflow_data.get("status", "unknown"),
        created_at=workflow_data.get("created_at", "unknown"),
        youtube_url=state.get("youtube_url", "Unknown"),
        current_step=state.get("current_step"),
        progress=state.get("progress"),
        error=state.get("error")
    )

@app.get("/api/v1/workflow/list")
async def list_workflows():
    """List all workflows."""
    workflows = []
    for workflow_id, workflow_data in active_workflows.items():
        try:
            state = workflow_data.get("state", {})
            workflows.append({
                "workflow_id": workflow_id,
                "status": workflow_data.get("status", "unknown"),
                "created_at": workflow_data.get("created_at", "unknown"),
                "youtube_url": state.get("youtube_url", "Unknown"),
                "current_step": state.get("current_step", "unknown")
            })
        except Exception as e:
            logger.error(f"Error processing workflow {workflow_id}: {e}")
            # Skip problematic workflows rather than failing the entire request
            continue
    
    return {
        "workflows": workflows,
        "total": len(workflows)
    }

@app.get("/api/v1/system/info", response_model=SystemInfoResponse)
async def get_system_info():
    """Get system information."""
    # Update metrics
    global app_metrics
    app_metrics["uptime"] = int(time.time() - app_start_time)
    
    # Count workflow statuses
    completed_workflows = sum(1 for w in active_workflows.values() if w["status"] == "completed")
    failed_workflows = sum(1 for w in active_workflows.values() if w["status"] == "failed")
    
    app_metrics.update({
        "total_workflows": len(active_workflows),
        "successful_workflows": completed_workflows,
        "failed_workflows": failed_workflows,
    })
    
    return SystemInfoResponse(
        status="running",
        active_workflows=len([w for w in active_workflows.values() if w["status"] == "running"]),
        telegram_bot_status="running" if telegram_service.application else "stopped",
        uptime=str(timedelta(seconds=app_metrics["uptime"])),
        metrics=app_metrics
    )

# Web Dashboard Routes
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the web dashboard."""
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        logger.error(f"Error serving dashboard: {e}")
        return HTMLResponse("""
        <html>
            <head><title>Tiz Lion AI Agent</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; background: #1f2937; color: white;">
                <h1>🤖 Tiz Lion AI Agent Dashboard</h1>
                <p>Dashboard template not found. The API is running successfully.</p>
                <p><a href="/health" style="color: #60a5fa;">Check API Health</a></p>
                <p><a href="/api/v1/system/info" style="color: #60a5fa;">System Information</a></p>
                <p><a href="/metrics" style="color: #60a5fa;">📊 Metrics Dashboard</a></p>
            </body>
        </html>
        """)

@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    """Serve the metrics dashboard page."""
    try:
        return templates.TemplateResponse("metrics.html", {"request": request})
    except Exception as e:
        logger.error(f"Error serving metrics page: {e}")
        # Fallback with embedded metrics dashboard
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>📊 Metrics Dashboard - YouTube Comment AI Agent</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; color: #333; }
                .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
                .header { text-align: center; margin-bottom: 30px; background: white; border-radius: 20px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
                .header h1 { font-size: 2.5em; color: #4a5568; margin-bottom: 10px; }
                .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }
                .stat-card { background: white; border-radius: 15px; padding: 25px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); transition: all 0.3s ease; }
                .stat-card:hover { transform: translateY(-5px); }
                .stat-number { font-size: 2.5em; font-weight: bold; color: #4a5568; margin-bottom: 10px; }
                .stat-label { color: #718096; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
                .loading { text-align: center; padding: 40px; color: white; }
                .loading-spinner { border: 3px solid #e2e8f0; border-top: 3px solid #667eea; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 20px; }
                .section { background: white; border-radius: 15px; padding: 30px; margin-bottom: 30px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); }
                .section h2 { color: #4a5568; margin-bottom: 20px; font-size: 1.8em; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
                .video-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
                .video-card { background: #f7fafc; border-radius: 12px; padding: 20px; border-left: 4px solid #667eea; }
                .video-title { font-weight: bold; color: #2d3748; margin-bottom: 10px; font-size: 1.1em; }
                .video-stats { display: flex; gap: 15px; margin-bottom: 15px; }
                .video-stat { background: white; padding: 8px 12px; border-radius: 20px; font-size: 0.85em; }
                .comment-link { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 8px 16px; border-radius: 20px; text-decoration: none; font-size: 0.85em; }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                .refresh-button { position: fixed; bottom: 30px; right: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 50%; width: 60px; height: 60px; font-size: 1.5em; cursor: pointer; }
                @media (max-width: 768px) { .container { padding: 15px; } .stats-grid { grid-template-columns: 1fr; } .video-grid { grid-template-columns: 1fr; } }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Metrics Dashboard</h1>
                    <p>Real-time analytics for your YouTube Comment AI Agent</p>
                </div>
                <div id="loading" class="loading">
                    <div class="loading-spinner"></div>
                    <p>Loading metrics...</p>
                </div>
                <div id="metrics-content" style="display: none;">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-label">Total Comments Posted</div>
                            <div class="stat-number" id="total-comments">0</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Videos Processed</div>
                            <div class="stat-number" id="total-videos">0</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Workflows Completed</div>
                            <div class="stat-number" id="total-workflows">0</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Total Engagement</div>
                            <div class="stat-number" id="total-engagement">0</div>
                        </div>
                    </div>
                    <div class="section">
                        <h2>🎯 Posted Comments & Engagement</h2>
                        <div id="videos-container" class="video-grid">
                            <!-- Videos will be populated here -->
                        </div>
                    </div>
                </div>
            </div>
            <button class="refresh-button" onclick="loadMetrics()">🔄</button>
            <script>
                async function loadMetrics() {
                    try:
                        const overviewResponse = await fetch('/api/v1/metrics/overview');
                        const overview = await overviewResponse.json();
                        const engagementResponse = await fetch('/api/v1/metrics/engagement');
                        const engagement = await engagementResponse.json();
                        
                        document.getElementById('total-comments').textContent = overview.total_comments_posted;
                        document.getElementById('total-videos').textContent = overview.total_videos_processed;
                        document.getElementById('total-workflows').textContent = overview.total_workflows;
                        document.getElementById('total-engagement').textContent = engagement.total_likes + engagement.total_replies;
                        
                        const videosContainer = document.getElementById('videos-container');
                        videosContainer.innerHTML = '';
                        
                        if (engagement.video_details && engagement.video_details.length > 0) {
                            engagement.video_details.forEach(video => {
                                const videoCard = document.createElement('div');
                                videoCard.className = 'video-card';
                                const engagement = video.engagement || { likes: 0, replies: 0 };
                                const commentUrl = video.comment_url || '#';
                                videoCard.innerHTML = `
                                    <div class="video-title">${video.video_title || 'Unknown Video'}</div>
                                    <div class="video-stats">
                                        <div class="video-stat">❤️ ${engagement.likes} Likes</div>
                                        <div class="video-stat">💬 ${engagement.replies} Replies</div>
                                    </div>
                                    <a href="${commentUrl}" target="_blank" class="comment-link">📝 View Comment</a>
                                `;
                                videosContainer.appendChild(videoCard);
                            });
                        } else {
                            videosContainer.innerHTML = '<p style="text-align: center; color: #718096;">No videos with posted comments found.</p>';
                        }
                        
                        document.getElementById('loading').style.display = 'none';
                        document.getElementById('metrics-content').style.display = 'block';
                    } catch (error) {
                        console.error('Error loading metrics:', error);
                        document.getElementById('loading').innerHTML = '<p>Error loading metrics. Please refresh.</p>';
                    }
                }
                
                setInterval(loadMetrics, 30000);
                document.addEventListener('DOMContentLoaded', loadMetrics);
            </script>
            </body>
        </html>
        """)

def is_valid_credential(value: str) -> bool:
    """Check if a credential value is valid (not a placeholder)."""
    if not value:
        logger.debug(f"🔍 Credential validation failed: empty value")
        return False
    
    value_lower = value.lower()
    
    # Check for EXACT placeholder patterns (not substrings)
    exact_placeholder_patterns = [
        "your_key", "your_token", "your_api", "your_secret", 
        "your_id", "your_hash", "placeholder", "not_configured",
        "replace_with", "add_your", "example", "test_key",
        "demo_key", "sample_key", "api_key_here", "token_here",
        "your_telegram_bot_token_here", "your_openrouter_api_key_here",
        "your_google_client_id_here", "your_google_client_secret_here",
        "your_youtube_api_key_here"
    ]
    
    # Check for exact matches or values that are clearly placeholders
    if value_lower in exact_placeholder_patterns:
        logger.debug(f"🔍 Credential validation failed: exact placeholder match '{value_lower}'")
        return False
    
    # Check for obvious placeholder patterns with "here" at the end
    if value_lower.endswith("_here") or value_lower.endswith("_token_here") or value_lower.endswith("_key_here"):
        logger.debug(f"🔍 Credential validation failed: ends with placeholder pattern '{value_lower}'")
        return False
    
    # Check for values that are obviously placeholders (start with common placeholder text)
    placeholder_starts = [
        "enter_your", "replace_with_your", "add_your", "put_your", 
        "insert_your", "paste_your", "your_actual"
    ]
    
    for start_pattern in placeholder_starts:
        if value_lower.startswith(start_pattern):
            logger.debug(f"🔍 Credential validation failed: starts with placeholder pattern '{start_pattern}'")
            return False
    
    # Check minimum length for real API keys (most are at least 15 characters)
    if len(value) < 15:
        logger.debug(f"🔍 Credential validation failed: too short (length: {len(value)}, minimum: 15)")
        return False
        
    # Special case for Telegram bot tokens - they should be much longer (typically 45+ chars)
    if len(value) < 30 and any(keyword in value_lower for keyword in ['bot', 'telegram', 'tg']):
        logger.debug(f"🔍 Credential validation failed: Telegram token too short (length: {len(value)}, expected: 30+)")
        return False
        
    logger.debug(f"🔍 Credential validation passed: length {len(value)}")
    return True

def check_openrouter_connection() -> bool:
    """Test OpenRouter API connection."""
    try:
        openrouter_key = getattr(settings, 'OPENROUTER_API_KEY', '')
        if not is_valid_credential(openrouter_key):
            return False
        
        # Simple test API call to validate key
        import requests
        headers = {
            'Authorization': f'Bearer {openrouter_key}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            'https://openrouter.ai/api/v1/models',
            headers=headers,
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

def check_youtube_api_connection() -> bool:
    """Test YouTube Data API connection."""
    try:
        youtube_key = getattr(settings, 'YOUTUBE_API_KEY', '') or getattr(settings, 'GOOGLE_API_KEY', '')
        if not is_valid_credential(youtube_key):
            return False
        
        # Simple test API call to validate key
        import requests
        response = requests.get(
            f'https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true&key={youtube_key}',
            timeout=5
        )
        # 403 means key is valid but no OAuth, 400 means invalid key
        return response.status_code in [200, 403]
    except:
        return False

def check_telegram_bot_connection() -> bool:
    """Test Telegram Bot API connection."""
    try:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not is_valid_credential(bot_token):
            return False
        
        # Simple test API call to validate bot token
        import requests
        response = requests.get(
            f'https://api.telegram.org/bot{bot_token}/getMe',
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

@app.get("/api/v1/configuration/status", response_model=ConfigurationResponse)
async def get_configuration_status():
    """Get configuration status with lightweight credential validation (no external API calls)."""
    return ConfigurationResponse(
        telegram_configured=is_valid_credential(getattr(settings, 'TELEGRAM_BOT_TOKEN', '')),
        openrouter_configured=is_valid_credential(getattr(settings, 'OPENROUTER_API_KEY', '')), 
        youtube_oauth_configured=bool(check_oauth2_authentication()),
        port=getattr(settings, 'PORT', 7844),
        debug_mode=getattr(settings, 'DEBUG', False)
    )

# New configuration management endpoints
@app.get("/api/v1/configuration/details")
async def get_configuration_details():
    """Get detailed configuration information."""
    # Available OpenRouter models with detailed information
    available_models = {
        # FREE MODELS
        "google/gemini-2.0-flash-exp:free": {
            "name": "google/gemini-2.0-flash-exp:free",
            "description": "🚀 Google Gemini 2.0 Flash Experimental (FREE)",
            "cost": "$0.00/$0.00 per 1M",
            "context": "1M",
            "category": "free",
            "details": "Latest experimental Gemini model with multimodal capabilities, code generation, and analysis"
        },
        "qwen/qwen-3-30b-a3b": {
            "name": "qwen/qwen-3-30b-a3b",
            "description": "🧠 Qwen3 30B A3B (FREE MoE)",
            "cost": "$0.00/$0.00 per 1M",
            "context": "32K",
            "category": "free",
            "details": "Mixture of Experts model with strong reasoning and multilingual capabilities"
        },
        "meta-llama/llama-3.3-70b-instruct": {
            "name": "meta-llama/llama-3.3-70b-instruct",
            "description": "🦙 Meta Llama 3.3 70B Instruct (FREE)",
            "cost": "$0.00/$0.00 per 1M",
            "context": "131K",
            "category": "free",
            "details": "Meta's flagship open-source model with excellent instruction following and reasoning"
        },
        "moonshot/moonshot-kimi-vl-a3b": {
            "name": "moonshot/moonshot-kimi-vl-a3b",
            "description": "🌙 Moonshot Kimi VL A3B (FREE Multimodal)",
            "cost": "$0.00/$0.00 per 1M",
            "context": "200K",
            "category": "free",
            "details": "Vision-language model for image analysis, OCR, and multimodal understanding"
        },
        "huggingface/qwen2.5-72b-instruct": {
            "name": "huggingface/qwen2.5-72b-instruct",
            "description": "🔬 Qwen2.5 72B Instruct (FREE)",
            "cost": "$0.00/$0.00 per 1M",
            "context": "131K",
            "category": "free",
            "details": "Advanced reasoning model with strong performance in math, coding, and analysis"
        },
        "nvidia/llama-3.1-nemotron-70b-instruct": {
            "name": "nvidia/llama-3.1-nemotron-70b-instruct",
            "description": "⚡ NVIDIA Nemotron 70B (FREE)",
            "cost": "$0.00/$0.00 per 1M",
            "context": "131K",
            "category": "free",
            "details": "NVIDIA-optimized Llama model with enhanced performance and efficiency"
        },
        "openchat/openchat-8b": {
            "name": "openchat/openchat-8b",
            "description": "💬 OpenChat 8B (FREE)",
            "cost": "$0.00/$0.00 per 1M",
            "context": "8K",
            "category": "free",
            "details": "Compact conversational model optimized for dialogue and chat applications"
        },

        # BUDGET PREMIUM MODELS
        "google/gemini-2.5-flash-preview": {
            "name": "google/gemini-2.5-flash-preview",
            "description": "💡 Google Gemini 2.5 Flash Preview (PREMIUM)",
            "cost": "$0.075/$0.30 per 1M",
            "context": "1M",
            "category": "premium",
            "details": "Latest Gemini model with improved reasoning, multimodal support, and enhanced code capabilities"
        },
        "mistralai/mistral-nemo": {
            "name": "mistralai/mistral-nemo",
            "description": "💰 Mistral Nemo (CHEAPEST PREMIUM)",
            "cost": "$0.15/$0.15 per 1M",
            "context": "128K",
            "category": "premium",
            "details": "Cost-effective model with strong performance in reasoning and code generation"
        },
        "openai/gpt-4o-mini": {
            "name": "openai/gpt-4o-mini",
            "description": "🔧 GPT-4o Mini (PREMIUM)",
            "cost": "$0.15/$0.60 per 1M",
            "context": "128K",
            "category": "premium",
            "details": "Compact GPT-4 variant with multimodal capabilities and efficient performance"
        },
        "google/gemini-flash-1.5": {
            "name": "google/gemini-flash-1.5",
            "description": "⚡ Gemini 1.5 Flash (PREMIUM)",
            "cost": "$0.075/$0.30 per 1M",
            "context": "1M",
            "category": "premium",
            "details": "Fast Gemini model optimized for speed with excellent multimodal understanding"
        },

        # MID-TIER PREMIUM MODELS
        "deepseek/deepseek-chat-v3-0324": {
            "name": "deepseek/deepseek-chat-v3-0324",
            "description": "🔬 DeepSeek V3 0324 (PREMIUM)",
            "cost": "$0.30/$0.88 per 1M",
            "context": "163K",
            "category": "premium",
            "details": "Advanced Chinese AI model with strong mathematical and coding capabilities"
        },
        "microsoft/wizardlm-2-8x22b": {
            "name": "microsoft/wizardlm-2-8x22b",
            "description": "🧙 WizardLM-2 8x22B (PREMIUM MoE)",
            "cost": "$0.50/$0.50 per 1M",
            "context": "65K",
            "category": "premium",
            "details": "Mixture of Experts model with excellent instruction following and complex reasoning"
        },
        "anthropic/claude-3-haiku": {
            "name": "anthropic/claude-3-haiku",
            "description": "🌸 Claude 3 Haiku (PREMIUM)",
            "cost": "$0.25/$1.25 per 1M",
            "context": "200K",
            "category": "premium",
            "details": "Fast and efficient Claude model optimized for quick responses and analysis"
        },
        "openai/gpt-4-turbo": {
            "name": "openai/gpt-4-turbo",
            "description": "🚄 GPT-4 Turbo (PREMIUM)",
            "cost": "$10.00/$30.00 per 1M",
            "context": "128K",
            "category": "premium",
            "details": "Advanced GPT-4 with improved speed, knowledge cutoff, and multimodal capabilities"
        },

        # HIGH-END PREMIUM MODELS
        "anthropic/claude-3.5-sonnet": {
            "name": "anthropic/claude-3.5-sonnet",
            "description": "🎭 Claude 3.5 Sonnet (PREMIUM)",
            "cost": "$3.00/$15.00 per 1M",
            "context": "200K",
            "category": "premium",
            "details": "Anthropic's flagship model with exceptional reasoning, analysis, and creative capabilities"
        },
        "openai/gpt-4o": {
            "name": "openai/gpt-4o",
            "description": "🧠 GPT-4o (PREMIUM)",
            "cost": "$2.50/$10.00 per 1M",
            "context": "128K",
            "category": "premium",
            "details": "OpenAI's omni-modal model with vision, audio, and text understanding capabilities"
        },
        "anthropic/claude-3-opus": {
            "name": "anthropic/claude-3-opus",
            "description": "🎨 Claude 3 Opus (PREMIUM)",
            "cost": "$15.00/$75.00 per 1M",
            "context": "200K",
            "category": "premium",
            "details": "Most capable Claude model with superior performance in complex reasoning and creative tasks"
        },

        # EXPERIMENTAL & SPECIALIZED MODELS
        "x-ai/grok-beta": {
            "name": "x-ai/grok-beta",
            "description": "🤖 Grok Beta (EXPERIMENTAL)",
            "cost": "$5.00/$15.00 per 1M",
            "context": "131K",
            "category": "premium",
            "details": "X.AI's conversational model with real-time information and unique personality"
        },
        "perplexity/llama-3.1-sonar-large-128k-online": {
            "name": "perplexity/llama-3.1-sonar-large-128k-online",
            "description": "🌐 Perplexity Sonar Large (WEB-CONNECTED)",
            "cost": "$1.00/$1.00 per 1M",
            "context": "127K",
            "category": "premium",
            "details": "Web-connected model with real-time search and information retrieval capabilities"
        },
        "cohere/command-r-plus": {
            "name": "cohere/command-r-plus",
            "description": "📊 Cohere Command R+ (ENTERPRISE)",
            "cost": "$3.00/$15.00 per 1M",
            "context": "128K",
            "category": "premium",
            "details": "Enterprise-grade model optimized for business applications and document analysis"
        }
    }
    
    # Determine actual functional status
    telegram_configured = is_valid_credential(getattr(settings, 'TELEGRAM_BOT_TOKEN', ''))
    telegram_functional = telegram_service.application and telegram_configured
    
    oauth2_authenticated = check_oauth2_authentication()
    youtube_configured = is_valid_credential(getattr(settings, 'GOOGLE_CLIENT_ID', '')) and is_valid_credential(getattr(settings, 'GOOGLE_CLIENT_SECRET', ''))
    comment_posting_functional = oauth2_authenticated and youtube_configured
    
    return {
        "current_llm_model": getattr(settings, 'OPENROUTER_MODEL', 'google/gemini-2.0-flash-001'),
        "available_models": available_models,
        "max_videos": getattr(settings, 'CHANNEL_PARSER_MAX_VIDEOS', 10),
        "telegram_bot_status": "running" if telegram_functional else "stopped",
        "telegram_configured": telegram_configured,
        "openrouter_configured": is_valid_credential(getattr(settings, 'OPENROUTER_API_KEY', '')),
        "youtube_oauth_configured": youtube_configured,
        "comment_posting_enabled": comment_posting_functional,
        "oauth2_authenticated": oauth2_authenticated
    }

@app.post("/api/v1/configuration/llm")
async def update_llm_model(config: Dict[str, str]):
    """Update the LLM model for agents."""
    try:
        model = config.get("model")
        if not model:
            raise HTTPException(status_code=400, detail="Model is required")
        
        # Validate model
        valid_models = [
            # FREE MODELS
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen-3-30b-a3b", 
            "meta-llama/llama-3.3-70b-instruct",
            "moonshot/moonshot-kimi-vl-a3b",
            "huggingface/qwen2.5-72b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "openchat/openchat-8b",
            # PREMIUM MODELS
            "google/gemini-2.5-flash-preview",
            "mistralai/mistral-nemo",
            "openai/gpt-4o-mini",
            "google/gemini-flash-1.5",
            "deepseek/deepseek-chat-v3-0324",
            "microsoft/wizardlm-2-8x22b",
            "anthropic/claude-3-haiku",
            "openai/gpt-4-turbo",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "anthropic/claude-3-opus",
            # EXPERIMENTAL & SPECIALIZED
            "x-ai/grok-beta",
            "perplexity/llama-3.1-sonar-large-128k-online",
            "cohere/command-r-plus"
        ]
        
        if model not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model. Must be one of: {', '.join(valid_models)}")
        
        # Update .env file
        success = await update_env_file("OPENROUTER_MODEL", model)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update configuration file")
        
        # Reload settings to get new value
        from importlib import reload
        from app import config
        reload(config)
        global settings
        from app.config import settings
        
        # Broadcast update to WebSocket clients
        try:
            await broadcast_to_websockets({
                "type": "config_update",
                "data": {
                    "setting": "llm_model",
                    "value": model,
                    "message": f"LLM model updated to {model}"
                }
            })
        except:
            pass
        
        logger.info(f"LLM model updated to: {model}")
        return {"status": "success", "message": f"LLM model updated to {model}", "new_model": model}
        
    except Exception as e:
        logger.error(f"Error updating LLM model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/configuration/videos")
async def update_video_count(config: Dict[str, int]):
    """Update the maximum number of videos to fetch."""
    try:
        max_videos = config.get("max_videos")
        if max_videos is None:
            raise HTTPException(status_code=400, detail="max_videos is required")
        
        if not isinstance(max_videos, int) or max_videos < 1 or max_videos > 50:
            raise HTTPException(status_code=400, detail="max_videos must be an integer between 1 and 50")
        
        # Update .env file
        success = await update_env_file("CHANNEL_PARSER_MAX_VIDEOS", str(max_videos))
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update configuration file")
        
        # Reload settings to get new value
        from importlib import reload
        from app import config
        reload(config)
        global settings
        from app.config import settings
        
        # Broadcast update to WebSocket clients
        try:
            await broadcast_to_websockets({
                "type": "config_update",
                "data": {
                    "setting": "max_videos",
                    "value": max_videos,
                    "message": f"Max videos updated to {max_videos}"
                }
            })
        except:
            pass
        
        logger.info(f"Max videos updated to: {max_videos}")
        return {"status": "success", "message": f"Max videos updated to {max_videos}", "new_count": max_videos}
        
    except Exception as e:
        logger.error(f"Error updating video count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/telegram/control")
async def control_telegram_bot(config: Dict[str, str]):
    """Control Telegram bot (start/stop/restart)."""
    try:
        action = config.get("action", "").lower()
        if action not in ["start", "stop", "restart"]:
            raise HTTPException(status_code=400, detail="Action must be 'start', 'stop', or 'restart'")
        
        if action == "start":
            if telegram_service.application:
                return {"status": "info", "message": "Telegram bot is already running"}
            await start_telegram_bot()
            message = "Telegram bot started successfully"
            
        elif action == "stop":
            if not telegram_service.application:
                return {"status": "info", "message": "Telegram bot is already stopped"}
            await stop_telegram_bot()
            message = "Telegram bot stopped successfully"
            
        elif action == "restart":
            await stop_telegram_bot()
            await start_telegram_bot()
            message = "Telegram bot restarted successfully"
        
        # Broadcast status update
        try:
            await broadcast_to_websockets({
                "type": "telegram_status",
                "data": {
                    "status": "running" if telegram_service.application else "stopped",
                    "action": action,
                    "message": message
                }
            })
        except:
            pass
        
        logger.info(f"Telegram bot {action} completed")
        return {"status": "success", "message": message}
        
    except Exception as e:
        logger.error(f"Error controlling Telegram bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to update .env file
async def update_env_file(key: str, value: str) -> bool:
    """Update a key-value pair in the .env file."""
    try:
        from pathlib import Path
        env_file = Path(".env")
        
        # Read existing content
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Update or add the key
        key_found = False
        updated_lines = []
        
        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                if '=' in line:
                    env_key = line.split('=')[0].strip()
                    if env_key == key:
                        updated_lines.append(f"{key}={value}\n")
                        key_found = True
                        continue
            updated_lines.append(line)
        
        # Add key if not found
        if not key_found:
            updated_lines.append(f"{key}={value}\n")
        
        # Write back to file
        with open(env_file, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating .env file: {e}")
        return False

@app.get("/api/v1/logs")
async def get_logs(limit: int = 100):
    """Get recent application logs."""
    try:
        # Return recent logs from memory
        if recent_logs:
            return {
                "logs": recent_logs[-limit:] if limit > 0 else recent_logs,
                "total": len(recent_logs)
            }
        
        # If no logs in memory, create sample logs
        now = datetime.now()
        sample_logs = [
            {
                "timestamp": now.isoformat(),
                "level": "info",
                "message": "Application is running normally",
                "module": "main"
            },
            {
                "timestamp": (now - timedelta(seconds=30)).isoformat(),
                "level": "info",
                "message": f"System has {len(active_workflows)} active workflows",
                "module": "workflow"
            },
            {
                "timestamp": (now - timedelta(seconds=60)).isoformat(),
                "level": "info",
                "message": f"Telegram bot status: {'running' if telegram_service.application else 'stopped'}",
                "module": "telegram"
            }
        ]
        
        return {
            "logs": sample_logs,
            "total": len(sample_logs)
        }
        
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return {
            "logs": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": "error",
                    "message": f"Error fetching logs: {str(e)}",
                    "module": "main"
                }
            ],
            "total": 1
        }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    try:
        # Send initial data
        await websocket.send_text(json.dumps({
            "type": "connection",
            "data": {"status": "connected", "timestamp": datetime.now().isoformat()}
        }))
        
        # Send current metrics
        await websocket.send_text(json.dumps({
            "type": "metrics_update", 
            "data": app_metrics
        }))
        
        # Send initial logs
        logs_response = await get_logs(limit=10)
        await websocket.send_text(json.dumps({
            "type": "logs_update",
            "data": logs_response["logs"]
        }))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)

@app.get("/api/v1/workflow/{workflow_id}/logs")
async def get_workflow_logs(workflow_id: str):
    """Get logs for a specific workflow."""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Return workflow-specific logs
    return {
        "workflow_id": workflow_id,
        "logs": [
            {
                "timestamp": datetime.now().isoformat(),
                "level": "info",
                "message": f"Workflow {workflow_id} status update",
                "module": "workflow"
            }
        ]
    }

@app.post("/api/v1/workflow/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow."""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow_data = active_workflows[workflow_id]
    if workflow_data["status"] == "running":
        workflow_data["status"] = "cancelled"
        
        # Broadcast workflow update
        await broadcast_to_websockets({
            "type": "workflow_update",
            "data": {
                "workflow_id": workflow_id,
                "status": "cancelled"
            }
        })
        
        return {"status": "success", "message": "Workflow cancelled"}
    else:
        raise HTTPException(status_code=400, detail="Workflow is not running")

# Redirect root to dashboard
@app.get("/", response_class=HTMLResponse)
async def root_redirect():
    """Root endpoint - show login page."""
    return HTMLResponse("""
    <html>
        <head>
            <title>Tiz Lion AI Agent - Login</title>
            <meta http-equiv="refresh" content="0; url=/login">
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; background: #1f2937; color: white; text-align: center; }
                .loader { border: 4px solid #374151; border-top: 4px solid #60a5fa; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            </style>
        </head>
        <body>
            <h1>🔐 Tiz Lion AI Agent</h1>
            <div class="loader"></div>
            <p>Redirecting to login...</p>
            <p><a href="/login" style="color: #60a5fa;">Click here if not redirected automatically</a></p>
        </body>
    </html>
    """)

# Enhanced error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    
    # Try to broadcast error to WebSocket clients
    try:
        await broadcast_to_websockets({
            "type": "error",
            "data": {
                "message": str(exc),
                "timestamp": datetime.now().isoformat()
            }
        })
    except:
        pass
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Settings Management Endpoints
@app.get("/api/v1/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current settings and configuration status."""
    try:
        # Test comment posting capability  
        can_post = settings.can_post_comments()
        logger.info(f"🔍 Final comment posting result: {can_post}")
        
        def mask_key(key: str) -> str:
            if not is_valid_credential(key):
                return "Not configured"
            if len(key) < 12:
                return "••••••••"
            return f"{key[:8]}••••{key[-4:]}"
            
        # Get current values from settings with error handling
        try:
            openrouter_key = getattr(settings, 'OPENROUTER_API_KEY', '') or ''
            youtube_key = getattr(settings, 'YOUTUBE_API_KEY', '') or getattr(settings, 'GOOGLE_API_KEY', '') or ''
            google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '') or ''
            google_client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '') or ''
            telegram_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or ''
        except Exception as e:
            logger.error(f"Error accessing settings attributes: {e}")
            # Fallback to empty strings
            openrouter_key = youtube_key = google_client_id = google_client_secret = telegram_token = ''
        
        # Debug logging to track validation results
        logger.info(f"🔍 Settings validation debug:")
        logger.info(f"   - OpenRouter key length: {len(openrouter_key)}, valid: {is_valid_credential(openrouter_key)}")
        logger.info(f"   - YouTube key length: {len(youtube_key)}, valid: {is_valid_credential(youtube_key)}")
        logger.info(f"   - Google Client ID length: {len(google_client_id)}, valid: {is_valid_credential(google_client_id)}")
        logger.info(f"   - Google Client Secret length: {len(google_client_secret)}, valid: {is_valid_credential(google_client_secret)}")
        logger.info(f"   - Telegram token length: {len(telegram_token)}, valid: {is_valid_credential(telegram_token)}")
        
        # Special debug for Telegram token
        if telegram_token:
            logger.info(f"🔍 Telegram token debug:")
            logger.info(f"   - First 10 chars: '{telegram_token[:10]}...'")
            logger.info(f"   - Last 10 chars: '...{telegram_token[-10:]}'")
            logger.info(f"   - Contains 'bot': {'bot' in telegram_token.lower()}")
            logger.info(f"   - Contains 'telegram': {'telegram' in telegram_token.lower()}")
            logger.info(f"   - Typical format (xxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx): {':' in telegram_token and len(telegram_token.split(':')) == 2}")
            
            # Test validation step by step
            is_valid_credential(telegram_token)
            
        # API Keys status
        api_keys = {
            "openrouter_api_key": mask_key(openrouter_key),
            "youtube_api_key": mask_key(youtube_key),
            "google_client_id": mask_key(google_client_id),
            "google_client_secret": mask_key(google_client_secret)
        }
        
        # Enhanced function to get detailed token validation state
        def get_token_validation_state(token: str, token_type: str = "generic") -> str:
            """Get detailed validation state for a token"""
            try:
                if not token or not token.strip():
                    return "empty"
                
                # Check for placeholder patterns
                placeholder_patterns = [
                    'your_telegram_bot_token_here',
                    'your_token',
                    'placeholder',
                    'example',
                    'token_here',
                    'bot_token_here',
                    'enter_your',
                    'your_api_key',
                    'api_key_here'
                ]
                
                token_lower = token.lower().strip()
                if any(pattern in token_lower for pattern in placeholder_patterns):
                    return "placeholder"
                
                # Use existing validation for format check
                if is_valid_credential(token):
                    return "valid"
                else:
                    return "invalid"
            except Exception as e:
                logger.error(f"Error validating token: {e}")
                return "invalid"
        
        # Telegram settings
        try:
            telegram_allowed_users = getattr(settings, 'TELEGRAM_ALLOWED_USERS', '') or ''
        except Exception:
            telegram_allowed_users = ''
            
        telegram_settings = {
            "bot_token": mask_key(telegram_token),
            "allowed_user_ids": telegram_allowed_users
        }
        
        # OAuth2 status - use dynamic redirect URI detection with error handling
        try:
            oauth2_authenticated = check_oauth2_authentication()
        except Exception as e:
            logger.warning(f"Error checking OAuth2 authentication: {e}")
            oauth2_authenticated = False
        
        try:
            redirect_uri = settings.get_oauth2_redirect_uri()
        except Exception as e:
            logger.warning(f"Error getting OAuth2 redirect URI: {e}")
            redirect_uri = "http://localhost:7844/oauth2callback"  # Fallback
        
        try:
            oauth2_scopes = getattr(settings, 'GOOGLE_OAUTH2_SCOPES', 'https://www.googleapis.com/auth/youtube.force-ssl')
            if oauth2_scopes:
                scopes_list = oauth2_scopes.split(',')
            else:
                scopes_list = ['https://www.googleapis.com/auth/youtube.force-ssl']
        except Exception:
            scopes_list = ['https://www.googleapis.com/auth/youtube.force-ssl']
        
        oauth2_status = {
            "configured": is_valid_credential(google_client_id) and is_valid_credential(google_client_secret),
            "authenticated": oauth2_authenticated,
            "redirect_uri": redirect_uri,
            "scopes": scopes_list
        }
        
        # Configuration status - using is_valid_credential to prevent placeholder values showing as configured
        configuration_status = {
            "telegram_configured": is_valid_credential(telegram_token),
            "openrouter_configured": is_valid_credential(openrouter_key),
            "youtube_api_configured": is_valid_credential(youtube_key),
            "oauth2_configured": oauth2_status["configured"]
        }
        
        # Log final status for debugging
        logger.info(f"📊 Configuration status: {configuration_status}")
            
        return SettingsResponse(
            api_keys=api_keys,
            telegram_settings=telegram_settings,
            oauth2_status=oauth2_status,
            configuration_status=configuration_status,
            # Enhanced: Add detailed token validation states
            token_validation_states={
                "openrouter_api_key": get_token_validation_state(openrouter_key),
                "youtube_api_key": get_token_validation_state(youtube_key),
                "google_client_id": get_token_validation_state(google_client_id),
                "google_client_secret": get_token_validation_state(google_client_secret),
                "telegram_token": get_token_validation_state(telegram_token, "telegram")
            }
        )
        
    except Exception as e:
        logger.error(f"Error in get_settings endpoint: {e}")
        # Return a safe fallback response
        return SettingsResponse(
            api_keys={
                "openrouter_api_key": "Error loading",
                "youtube_api_key": "Error loading",
                "google_client_id": "Error loading",
                "google_client_secret": "Error loading"
            },
            telegram_settings={
                "bot_token": "Error loading",
                "allowed_user_ids": ""
            },
            oauth2_status={
                "configured": False,
                "authenticated": False,
                "redirect_uri": "http://localhost:7844/oauth2callback",
                "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"]
            },
            configuration_status={
                "telegram_configured": False,
                "openrouter_configured": False,
                "youtube_api_configured": False,
                "oauth2_configured": False
            },
            token_validation_states={
                "openrouter_api_key": "error",
                "youtube_api_key": "error",
                "google_client_id": "error",
                "google_client_secret": "error",
                "telegram_token": "error"
            }
        )

@app.post("/api/v1/settings/api-keys")
async def update_api_keys(config: APIKeysUpdate):
    """Update API keys configuration."""
    global settings  # MUST be at the top before any usage
    try:
        updated_keys = []
        
        # DEBUG: Log received configuration
        logger.info(f"🔍 DEBUG: Received API keys update request with:")
        logger.info(f"   - OpenRouter key: {'✅ PROVIDED' if config.openrouter_api_key else '❌ NOT PROVIDED'}")
        logger.info(f"   - YouTube key: {'✅ PROVIDED' if config.youtube_api_key else '❌ NOT PROVIDED'}")
        logger.info(f"   - Google Client ID: {'✅ PROVIDED' if config.google_client_id else '❌ NOT PROVIDED'}")
        logger.info(f"   - Google Client Secret: {'✅ PROVIDED' if config.google_client_secret else '❌ NOT PROVIDED'}")
        
        # Update OpenRouter API key
        if config.openrouter_api_key is not None and config.openrouter_api_key.strip():
            logger.info(f"🔧 Updating OpenRouter API key...")
            success = await update_env_file("OPENROUTER_API_KEY", config.openrouter_api_key.strip())
            if success:
                updated_keys.append("OpenRouter API Key")
                settings.OPENROUTER_API_KEY = config.openrouter_api_key.strip()
                logger.info(f"✅ OpenRouter API key updated successfully")
            else:
                logger.error(f"❌ Failed to update OpenRouter API key in .env file")
        else:
            logger.info(f"⏭️ Skipping OpenRouter API key (not provided or empty)")
        
        # Update YouTube API key
        if config.youtube_api_key is not None and config.youtube_api_key.strip():
            logger.info(f"🔧 Updating YouTube API key...")
            success = await update_env_file("YOUTUBE_API_KEY", config.youtube_api_key.strip())
            if success:
                updated_keys.append("YouTube API Key")
                settings.YOUTUBE_API_KEY = config.youtube_api_key.strip()
                logger.info(f"✅ YouTube API key updated successfully")
            else:
                logger.error(f"❌ Failed to update YouTube API key in .env file")
        else:
            logger.info(f"⏭️ Skipping YouTube API key (not provided or empty)")
        
        # Update Google Client ID
        if config.google_client_id is not None and config.google_client_id.strip():
            logger.info(f"🔧 Updating Google Client ID...")
            success = await update_env_file("GOOGLE_CLIENT_ID", config.google_client_id.strip())
            if success:
                updated_keys.append("Google Client ID")
                settings.GOOGLE_CLIENT_ID = config.google_client_id.strip()
                logger.info(f"✅ Google Client ID updated successfully")
            else:
                logger.error(f"❌ Failed to update Google Client ID in .env file")
        else:
            logger.info(f"⏭️ Skipping Google Client ID (not provided or empty)")
        
        # Update Google Client Secret
        if config.google_client_secret is not None and config.google_client_secret.strip():
            logger.info(f"🔧 Updating Google Client Secret...")
            success = await update_env_file("GOOGLE_CLIENT_SECRET", config.google_client_secret.strip())
            if success:
                updated_keys.append("Google Client Secret")
                settings.GOOGLE_CLIENT_SECRET = config.google_client_secret.strip()
                logger.info(f"✅ Google Client Secret updated successfully")
            else:
                logger.error(f"❌ Failed to update Google Client Secret in .env file")
        else:
            logger.info(f"⏭️ Skipping Google Client Secret (not provided or empty)")
        
        # CRITICAL FIX: Reload settings to ensure changes take effect
        if updated_keys:
            try:
                # Force reload the settings from the updated .env file
                from app.config import reload_settings
                settings = reload_settings()
                logger.info("🔄 Settings reloaded from .env file")
                
            except Exception as e:
                logger.error(f"Error reloading settings: {e}")
        
        # Broadcast configuration update
        await broadcast_to_websockets({
            "type": "settings_update",
            "message": f"Updated API keys: {', '.join(updated_keys)}"
        })
        
        logger.info(f"API keys updated: {', '.join(updated_keys)}")
        
        return {
            "message": "API keys updated successfully",
            "updated_keys": updated_keys
        }
        
    except Exception as e:
        logger.error(f"Error updating API keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/settings/telegram")
async def update_telegram_settings(config: TelegramSettingsUpdate):
    """Update Telegram settings configuration."""
    global settings  # MUST be at the top before any usage
    try:
        updated_settings = []
        restart_required = False
        
        # Update Telegram Bot Token
        if config.bot_token is not None:
            old_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
            success = await update_env_file("TELEGRAM_BOT_TOKEN", config.bot_token)
            if success:
                updated_settings.append("Bot Token")
                settings.TELEGRAM_BOT_TOKEN = config.bot_token
                if old_token != config.bot_token:
                    restart_required = True
        
        # Update Allowed User IDs (user ID = chat ID in Telegram)
        if config.allowed_user_ids is not None:
            success = await update_env_file("TELEGRAM_ALLOWED_USERS", config.allowed_user_ids)
            if success:
                updated_settings.append("Allowed User IDs")
                settings.TELEGRAM_ALLOWED_USERS = config.allowed_user_ids
        
        # CRITICAL FIX: Reload settings to ensure changes take effect
        if updated_settings:
            try:
                # Force reload the settings from the updated .env file
                from app.config import reload_settings
                settings = reload_settings()
                logger.info("🔄 Settings reloaded from .env file")
                
                # Force reinitialize telegram service with new settings
                telegram_service.force_reinitialize()
                logger.info("🔄 Telegram service reinitialized with new settings")
                
            except Exception as e:
                logger.error(f"Error reloading settings: {e}")
        
        # Restart Telegram bot if token changed or settings were updated
        if updated_settings and telegram_service.is_configured():
            try:
                await stop_telegram_bot()
                await asyncio.sleep(2)
                await start_telegram_bot()
                updated_settings.append("Bot Restarted")
                
                # Send welcome message to configured users after successful connection
                if config.allowed_user_ids:
                    # Parse user IDs from string to list of integers
                    try:
                        user_id_list = [int(uid.strip()) for uid in config.allowed_user_ids.split(',') if uid.strip()]
                        await telegram_service.send_welcome_message_to_users(user_id_list)
                    except ValueError as e:
                        logger.error(f"Error parsing user IDs for welcome message: {e}")
                    
            except Exception as e:
                logger.error(f"Error restarting Telegram bot: {e}")
        
        # Broadcast configuration update
        await broadcast_to_websockets({
            "type": "settings_update",
            "message": f"Updated Telegram settings: {', '.join(updated_settings)}"
        })
        
        logger.info(f"Telegram settings updated: {', '.join(updated_settings)}")
        
        return {
            "message": "Telegram settings updated successfully",
            "updated_settings": updated_settings,
            "restart_required": restart_required
        }
        
    except Exception as e:
        logger.error(f"Error updating Telegram settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/settings/oauth2")
async def manage_oauth2_setup(config: OAuth2Setup, request: Request):
    """Manage OAuth2 setup and authentication."""
    try:
        if config.action == "generate_url":
            # Generate OAuth2 authorization URL
            try:
                from app.services.youtube_service import YouTubeService
                
                # Get the current port from the request
                port = request.url.port or 7844  # Fallback to 7844 if not detected
                
                youtube_service = YouTubeService()
                auth_url = youtube_service.get_oauth2_authorization_url(port=port)
                
                if not auth_url:
                    raise HTTPException(status_code=400, detail="Failed to generate authorization URL. Check OAuth2 credentials.")
                
                # Get the dynamic redirect URI
                redirect_uri = settings.get_oauth2_redirect_uri(port=port)
                
                # Store the OAuth2 flow state
                import secrets
                state_token = secrets.token_urlsafe(32)
                oauth2_flows[state_token] = {
                    "created_at": datetime.now().isoformat(),
                    "youtube_service": youtube_service
                }
                
                return {
                    "success": True,
                    "action": "authorization_url_generated",
                    "authorization_url": auth_url,
                    "redirect_uri": redirect_uri,
                    "state": state_token,
                    "message": f"Open the authorization URL and complete the OAuth flow. Make sure your Google Console has redirect URI: {redirect_uri}"
                }
                
            except ImportError as e:
                logger.error(f"YouTube service import error: {e}")
                raise HTTPException(status_code=500, detail="YouTube service not available")
            except Exception as e:
                logger.error(f"Error generating authorization URL: {e}")
                raise HTTPException(status_code=500, detail=f"Error generating authorization URL: {str(e)}")
        
        elif config.action == "complete_auth":
            # Complete OAuth2 authorization
            if not config.response_url:
                raise HTTPException(status_code=400, detail="Response URL is required for completing authorization")
            
            try:
                from app.services.youtube_service import YouTubeService
                
                youtube_service = YouTubeService()
                success = youtube_service.complete_oauth2_authorization(config.response_url)
                
                if success:
                    # Update environment to enable comment posting
                    await update_env_file("ENABLE_COMMENT_POSTING", "true")
                    
                    # Broadcast success
                    await broadcast_to_websockets({
                        "type": "oauth2_success",
                        "message": "OAuth2 authentication completed successfully"
                    })
                    
                    logger.info("OAuth2 authentication completed successfully")
                    
                    return {
                        "action": "authorization_completed",
                        "success": True,
                        "message": "OAuth2 authentication completed successfully. Comment posting is now enabled."
                    }
                else:
                    raise HTTPException(status_code=400, detail="OAuth2 authorization failed")
                    
            except ImportError as e:
                logger.error(f"YouTube service import error: {e}")
                raise HTTPException(status_code=500, detail="YouTube service not available")
            except Exception as e:
                logger.error(f"Error completing authorization: {e}")
                raise HTTPException(status_code=500, detail=f"Error completing authorization: {str(e)}")
        
        elif config.action == "disconnect":
            # Disconnect/clear OAuth2 credentials
            try:
                from app.services.youtube_service import YouTubeService
                
                youtube_service = YouTubeService()
                
                # Use the service's clear credentials method
                success = youtube_service.clear_oauth2_credentials()
                if not success:
                    logger.warning("Failed to clear some OAuth2 credentials")
                
                # Disable comment posting in environment
                await update_env_file("ENABLE_COMMENT_POSTING", "false")
                
                # Broadcast disconnect success
                await broadcast_to_websockets({
                    "type": "oauth2_disconnect",
                    "message": "YouTube account disconnected successfully"
                })
                
                logger.info("YouTube OAuth2 credentials cleared successfully")
                
                return {
                    "action": "credentials_cleared",
                    "success": True,
                    "message": "YouTube account disconnected successfully. You can connect a different account or reconnect the same account."
                }
                
            except ImportError as e:
                logger.error(f"YouTube service import error: {e}")
                raise HTTPException(status_code=500, detail="YouTube service not available")
            except Exception as e:
                logger.error(f"Error disconnecting OAuth2: {e}")
                raise HTTPException(status_code=500, detail=f"Error disconnecting OAuth2: {str(e)}")
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'generate_url', 'complete_auth', or 'disconnect'")
            
    except Exception as e:
        logger.error(f"Error managing OAuth2 setup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Serve the settings page."""
    try:
        return templates.TemplateResponse("settings.html", {"request": request})
    except Exception as e:
        logger.error(f"Error serving settings page: {e}")
        return HTMLResponse("""
        <html>
            <head><title>Settings - Tiz Lion AI Agent</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; background: #1f2937; color: white;">
                <h1>⚙️ Settings</h1>
                <p>Settings template not found. The API is running successfully.</p>
                <p><a href="/dashboard" style="color: #60a5fa;">Back to Dashboard</a></p>
            </body>
        </html>
        """)

@app.get("/oauth2callback")
async def oauth2_callback(request: Request):
    """Handle OAuth2 callback from Google with improved countdown timer."""
    try:
        # Get the authorization code and state from the callback
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        error = request.query_params.get('error')
        
        if error:
            logger.error(f"OAuth2 error: {error}")
            error_escaped = str(error).replace("'", "\\'").replace('"', '\\"')
            return HTMLResponse("""
            <html>
                <head><title>OAuth2 Error</title></head>
                <body style="font-family: Arial, sans-serif; padding: 20px; background: #1f2937; color: white;">
                    <h1>⌘ OAuth2 Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p><a href="/settings" style="color: #60a5fa;">Return to Settings</a></p>
                    <script>
                        // Notify parent window and close popup
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'oauth2_complete',
                                success: false,
                                error: '{error_escaped}'
                            }}, window.location.origin);
                        }}
                        
                        // Simple popup closing for errors - don't send conflicting success messages
                        setTimeout(() => {
                            if (window.opener) {
                                try {
                                    window.opener.focus();
                                    window.close();
                                    
                                    // If popup doesn't close, redirect after delay
                                    setTimeout(() => {
                                        if (!window.closed) {
                                            window.location.href = '/settings';
                                        }
                                    }, 3000);
                                } catch (e) {
                                    window.location.href = '/settings';
                                }
                            } else {
                                window.location.href = '/settings';
                            }
                        }, 2000); // Give user time to read error message
                    </script>
                </body>
            </html>
            """.format(error=error, error_escaped=error_escaped))
        
        # Complete the OAuth2 flow
        try:
            from app.services.youtube_service import YouTubeService
            
            # Create a new YouTube service instance for the callback
            youtube_service = YouTubeService()
            
            # Build the full callback URL for the service
            callback_url = str(request.url)
            
            # Complete OAuth2 authorization using the callback URL
            success = youtube_service.complete_oauth2_authorization(callback_url)
            
            if success:
                # Update environment to enable comment posting
                await update_env_file("ENABLE_COMMENT_POSTING", "true")
                
                # Broadcast success
                await broadcast_to_websockets({
                    "type": "oauth2_success",
                    "message": "OAuth2 authentication completed successfully"
                })
                
                logger.info("OAuth2 authentication completed successfully via callback")
                
                return HTMLResponse("""
                <!DOCTYPE html>
                <html lang="en">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>🎉 YouTube Connected Successfully!</title>
                        <link rel="icon" type="image/x-icon" href="/favicon.ico">
                        <style>
                            * {
                                margin: 0;
                                padding: 0;
                                box-sizing: border-box;
                            }
                            
                            body {
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                min-height: 100vh;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                color: white;
                                overflow: hidden;
                            }
                            
                            .container {
                                text-align: center;
                                padding: 3rem;
                                background: rgba(255, 255, 255, 0.1);
                                backdrop-filter: blur(20px);
                                border-radius: 20px;
                                border: 1px solid rgba(255, 255, 255, 0.2);
                                box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
                                max-width: 500px;
                                width: 90%;
                                position: relative;
                                animation: slideIn 0.6s ease-out;
                            }
                            
                            @keyframes slideIn {
                                from {
                                    opacity: 0;
                                    transform: translateY(-30px) scale(0.9);
                                }
                                to {
                                    opacity: 1;
                                    transform: translateY(0) scale(1);
                                }
                            }
                            
                            .success-icon {
                                font-size: 4rem;
                                margin-bottom: 1.5rem;
                                animation: bounce 0.8s ease-in-out;
                                display: block;
                            }
                            
                            @keyframes bounce {
                                0%, 20%, 50%, 80%, 100% {
                                    transform: translateY(0);
                                }
                                40% {
                                    transform: translateY(-10px);
                                }
                                60% {
                                    transform: translateY(-5px);
                                }
                            }
                            
                            .app-icon {
                                width: 48px;
                                height: 48px;
                                margin: 0 auto 1rem;
                                background: url('/favicon.ico') no-repeat center;
                                background-size: contain;
                                opacity: 0.9;
                            }
                            
                            h1 {
                                font-size: 2rem;
                                font-weight: 700;
                                margin-bottom: 1rem;
                                text-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
                            }
                            
                            .subtitle {
                                font-size: 1.1rem;
                                margin-bottom: 1.5rem;
                                opacity: 0.9;
                                line-height: 1.6;
                            }
                            
                            .features {
                                background: rgba(255, 255, 255, 0.1);
                                border-radius: 12px;
                                padding: 1.5rem;
                                margin: 1.5rem 0;
                                border: 1px solid rgba(255, 255, 255, 0.1);
                            }
                            
                            .feature-item {
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                margin: 0.8rem 0;
                                font-size: 0.95rem;
                            }
                            
                            .feature-item .icon {
                                margin-right: 0.8rem;
                                font-size: 1.2rem;
                            }
                            
                            .countdown {
                                font-size: 0.9rem;
                                opacity: 0.8;
                                margin-top: 1.5rem;
                                padding: 1rem;
                                background: rgba(0, 0, 0, 0.2);
                                border-radius: 8px;
                                border: 1px solid rgba(255, 255, 255, 0.1);
                            }
                            
                            .countdown-number {
                                font-weight: bold;
                                color: #fbbf24;
                                font-size: 1.1rem;
                            }
                            
                            .particles {
                                position: fixed;
                                top: 0;
                                left: 0;
                                width: 100%;
                                height: 100%;
                                pointer-events: none;
                                z-index: -1;
                            }
                            
                            .particle {
                                position: absolute;
                                width: 4px;
                                height: 4px;
                                background: rgba(255, 255, 255, 0.6);
                                border-radius: 50%;
                                animation: float 6s infinite linear;
                            }
                            
                            @keyframes float {
                                0% {
                                    transform: translateY(100vh) rotate(0deg);
                                    opacity: 0;
                                }
                                10% {
                                    opacity: 1;
                                }
                                90% {
                                    opacity: 1;
                                }
                                100% {
                                    transform: translateY(-10px) rotate(360deg);
                                    opacity: 0;
                                }
                            }
                            
                            @media (max-width: 480px) {
                                .container {
                                    padding: 2rem 1.5rem;
                                    margin: 1rem;
                                }
                                
                                h1 {
                                    font-size: 1.6rem;
                                }
                                
                                .success-icon {
                                    font-size: 3rem;
                                }
                                
                                .features {
                                    padding: 1rem;
                                }
                                
                                .feature-item {
                                    font-size: 0.9rem;
                                }
                            }
                        </style>
                    </head>
                    <body>
                        <div class="particles"></div>
                        
                        <div class="container">
                            <div class="app-icon"></div>
                            <span class="success-icon">🎉</span>
                            <h1>YouTube Connected!</h1>
                            <p class="subtitle">Your YouTube account has been successfully connected and authenticated.</p>
                            
                            <div class="features">
                                <div class="feature-item">
                                    <span class="icon">✅</span>
                                    OAuth2 authentication complete
                                </div>
                                <div class="feature-item">
                                    <span class="icon">🔒</span>
                                    Secure connection established
                                </div>
                                <div class="feature-item">
                                    <span class="icon">💬</span>
                                    Comment posting now enabled
                                </div>
                            </div>
                            
                            <div class="countdown">
                                🚀 Redirecting to settings in <span id="countdown" class="countdown-number">3</span> seconds...
                            </div>
                        </div>
                        
                        <script>
                            // Notify parent window about successful authentication
                            if (window.opener) {
                                window.opener.postMessage({
                                    type: 'oauth2_complete',
                                    success: true
                                }, window.location.origin);
                            }
                            
                            // Countdown timer with proper 3-second display
                            let countdownValue = 3;
                            const countdownElement = document.getElementById('countdown');
                            
                            function updateCountdown() {
                                // Display current countdown value immediately
                                if (countdownElement) {
                                    countdownElement.textContent = countdownValue;
                                    console.log(`Countdown: ${countdownValue}`);
                                }
                                
                                if (countdownValue > 0) {
                                    // Wait exactly 1 second, then decrement and update
                                    setTimeout(() => {
                                        countdownValue--;
                                        updateCountdown();
                                    }, 1000);
                                } else {
                                    // Countdown finished, change message and try to close popup
                                    if (countdownElement) {
                                        countdownElement.parentElement.innerHTML = "🚀 Closing popup and returning to settings...";
                                    }
                                    
                                    // SUCCESS: Simple popup closing after countdown
                                    setTimeout(() => {
                                        if (window.opener) {
                                            try {
                                                // Notify parent of success (this is correct for success case)
                                                window.opener.postMessage({
                                                    type: 'oauth2_complete',
                                                    success: true,
                                                    timestamp: Date.now()
                                                }, window.location.origin);
                                                
                                                window.opener.focus();
                                                window.close();
                                            } catch (e) {
                                                console.log('Popup close failed:', e);
                                            }
                                            
                                            // Simplified fallback - only redirect if close failed
                                            setTimeout(() => {
                                                if (!window.closed) {
                                                    window.location.href = '/settings';
                                                }
                                            }, 1000);
                                        } else {
                                            window.location.href = '/settings';
                                        }
                                    }, 200); // Quick action after countdown
                                }
                            }
                            
                            // Start countdown immediately
                            updateCountdown();
                            
                            // Create floating particles effect
                            function createParticle() {
                                const particle = document.createElement('div');
                                particle.className = 'particle';
                                particle.style.left = Math.random() * 100 + '%';
                                particle.style.animationDelay = Math.random() * 6 + 's';
                                particle.style.animationDuration = (Math.random() * 3 + 3) + 's';
                                document.querySelector('.particles').appendChild(particle);
                                
                                // Remove particle after animation
                                setTimeout(() => {
                                    if (particle.parentNode) {
                                        particle.parentNode.removeChild(particle);
                                    }
                                }, 6000);
                            }
                            
                            // Generate particles periodically
                            setInterval(createParticle, 300);
                            
                            // Mobile-specific enhancements
                            if (/Mobi|Android/i.test(navigator.userAgent)) {
                                // Add mobile-specific handling
                                document.body.style.overscroll = 'none';
                                
                                // Remove the conflicting mobile override - let main logic handle it
                                console.log('Mobile browser detected - using main popup closing logic');
                            }
                        </script>
                    </body>
                </html>
                """)
            else:
                # Authentication failed - show error with fallback
                error_msg = "OAuth2 authentication failed. Please try again."
                logger.error(f"OAuth2 authentication failed via callback")
                error_msg_escaped = str(error_msg).replace("'", "\\'").replace('"', '\\"')
                return HTMLResponse("""
                <html>
                    <head><title>OAuth2 Error</title></head>
                    <body style="font-family: Arial, sans-serif; padding: 20px; background: #1f2937; color: white;">
                        <h1>⚠️ YouTube Authentication Failed</h1>
                        <p>Authentication process could not be completed: {error_msg}</p>
                        <p><a href="/settings" style="color: #60a5fa;">Return to Settings and try again</a></p>
                        <script>
                            // Notify parent window about the error
                            if (window.opener) {{
                                window.opener.postMessage({{
                                    type: 'oauth2_complete',
                                    success: false,
                                    error: '{error_msg_escaped}'
                                }}, window.location.origin);
                            }}
                            
                            // ERROR HANDLER: Simple popup closing for authentication failures
                            setTimeout(() => {
                                if (window.opener) {
                                    try {
                                        window.opener.focus();
                                        window.close();
                                    } catch (e) {
                                        console.log('Popup close failed:', e);
                                    }
                                    
                                    // Only redirect if close truly failed after reasonable wait
                                    setTimeout(() => {
                                        if (!window.closed) {
                                            window.location.href = '/settings';
                                        }
                                    }, 2000);
                                } else {
                                    window.location.href = '/settings';
                                }
                            }, 1000);
                        </script>
                    </body>
                </html>
                """.format(error_msg=error_msg, error_msg_escaped=error_msg_escaped))
                
        except Exception as e:
            logger.error(f"Error in OAuth2 callback: {e}")
            error_msg = str(e)
            error_msg_escaped = error_msg.replace("'", "\\'").replace('"', '\\"')  # Escape quotes for JavaScript
            return HTMLResponse("""
            <html>
                <head><title>OAuth2 Error</title></head>
                <body style="font-family: Arial, sans-serif; padding: 20px; background: #1f2937; color: white;">
                    <h1>⚠️ OAuth2 Authentication Error</h1>
                    <p>Error: {error_msg}</p>
                    <p><a href="/settings" style="color: #60a5fa;">Return to Settings</a></p>
                    <script>
                        // Notify parent window about the error
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'oauth2_complete',
                                success: false,
                                error: '{error_msg_escaped}'
                            }}, window.location.origin);
                        }}
                        
                        // Simplified and focused popup closing logic
                        setTimeout(() => {
                            if (window.opener) {
                                try {
                                    // Notify parent window of success
                                    window.opener.postMessage({
                                        type: 'oauth2_complete',
                                        success: true,
                                        timestamp: Date.now()
                                    }, window.location.origin);
                                    
                                    // Focus parent and close popup
                                    window.opener.focus();
                                    
                                    // Try to close - simple and direct
                                    window.close();
                                    
                                    // Final fallback - only redirect if window really didn't close after longer wait
                                    setTimeout(() => {
                                        // Give a longer time for close to work, then check if still open
                                        try {
                                            if (!window.closed) {
                                                window.location.href = '/settings';
                                            }
                                        } catch (e) {
                                            // Even error checking window.closed failed - just redirect
                                            window.location.href = '/settings';
                                        }
                                    }, 5000); // Give 5 seconds for close to work
                                    
                                } catch (e) {
                                    // Don't redirect immediately on errors - popup might still close
                                    console.log('Popup closing error:', e);
                                    // Give window time to close naturally before redirecting
                                    setTimeout(() => {
                                        window.location.href = '/settings';
                                    }, 3000);
                                }
                            } else {
                                // Not a popup window - redirect normally
                                window.location.href = '/settings';
                            }
                        }, 500); // Shorter delay for faster response
                    </script>
                </body>
            </html>
            """.format(error_msg=error_msg, error_msg_escaped=error_msg_escaped))
            
    except Exception as e:
        logger.error(f"Error handling OAuth2 callback: {e}")
        error_msg = str(e)
        error_msg_escaped = error_msg.replace("'", "\\'").replace('"', '\\"')  # Escape quotes for JavaScript
        return HTMLResponse("""
        <html>
            <head><title>OAuth2 Error</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; background: #1f2937; color: white;">
                <h1>⚠️ OAuth2 Authentication Error</h1>
                <p>Unexpected error: {error_msg}</p>
                <p><a href="/settings" style="color: #60a5fa;">Return to Settings</a></p>
                <script>
                    // Notify parent window about the error
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'oauth2_complete',
                            success: false,
                            error: '{error_msg_escaped}'
                        }}, window.location.origin);
                    }}
                    
                    // ERROR HANDLER: Simple popup closing for exceptions
                    setTimeout(() => {
                        if (window.opener) {
                            try {
                                window.opener.focus();
                                window.close();
                            } catch (e) {
                                console.log('Popup close failed:', e);
                            }
                            
                            // Only redirect if close truly failed after reasonable wait
                            setTimeout(() => {
                                if (!window.closed) {
                                    window.location.href = '/settings';
                                }
                            }, 2000);
                        } else {
                            window.location.href = '/settings';
                        }
                    }, 1000);
                </script>
            </body>
        </html>
        """.format(error_msg=error_msg, error_msg_escaped=error_msg_escaped))

def check_oauth2_authentication() -> bool:
    """Check if OAuth2 is properly authenticated by verifying credentials."""
    try:
        from app.services.youtube_service import YouTubeService
        youtube_service = YouTubeService()
        return youtube_service.is_authenticated_for_posting()
    except Exception:
        return False

@app.post("/api/v1/configuration/comment-posting")
async def toggle_comment_posting(config: CommentPostingToggle):
    """Toggle comment posting on/off."""
    try:
        # Declare global settings at the beginning
        global settings
        
        enabled = config.enabled
        
        # Check if OAuth2 is configured and authenticated when enabling
        if enabled:
            if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
                raise HTTPException(
                    status_code=400, 
                    detail="OAuth2 credentials not configured. Please set up OAuth2 in Settings first.",
                    headers={"X-Redirect": "/settings"}
                )
            
            if not check_oauth2_authentication():
                raise HTTPException(
                    status_code=400,
                    detail="OAuth2 not authenticated. Please complete OAuth2 setup in Settings first.",
                    headers={"X-Redirect": "/settings"}
                )
        
        # Update .env file
        success = await update_env_file("ENABLE_COMMENT_POSTING", str(enabled).lower())
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update configuration file")
        
        # Reload settings to get new value
        from importlib import reload
        from app import config
        reload(config)
        from app.config import settings
        
        # Broadcast update to WebSocket clients
        try:
            await broadcast_to_websockets({
                "type": "config_update",
                "data": {
                    "setting": "comment_posting",
                    "value": enabled,
                    "message": f"Comment posting {'enabled' if enabled else 'disabled'}"
                }
            })
        except:
            pass
        
        status_msg = "enabled" if enabled else "disabled"
        logger.info(f"Comment posting {status_msg}")
        return {
            "status": "success", 
            "message": f"Comment posting {status_msg}", 
            "enabled": enabled,
            "oauth2_required": enabled and not check_oauth2_authentication()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling comment posting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def check_openrouter_connection() -> bool:
    """Test OpenRouter API connection."""
    try:
        openrouter_key = getattr(settings, 'OPENROUTER_API_KEY', '')
        if not is_valid_credential(openrouter_key):
            return False
        
        # Simple test API call to validate key
        import requests
        headers = {
            'Authorization': f'Bearer {openrouter_key}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            'https://openrouter.ai/api/v1/models',
            headers=headers,
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

def check_youtube_api_connection() -> bool:
    """Test YouTube Data API connection."""
    try:
        youtube_key = getattr(settings, 'YOUTUBE_API_KEY', '') or getattr(settings, 'GOOGLE_API_KEY', '')
        if not is_valid_credential(youtube_key):
            return False
        
        # Simple test API call to validate key
        import requests
        response = requests.get(
            f'https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true&key={youtube_key}',
            timeout=5
        )
        # 403 means key is valid but no OAuth, 400 means invalid key
        return response.status_code in [200, 403]
    except:
        return False

def check_telegram_bot_connection() -> bool:
    """Test Telegram Bot API connection."""
    try:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not is_valid_credential(bot_token):
            return False
        
        # Simple test API call to validate bot token
        import requests
        response = requests.get(
            f'https://api.telegram.org/bot{bot_token}/getMe',
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

# Add new endpoint for API credential testing
@app.get("/api/v1/configuration/test-credentials")
async def test_credentials():
    """Test credentials by making actual API calls (slower but thorough)."""
    return {
        "telegram_api_connected": check_telegram_bot_connection(),
        "openrouter_api_connected": check_openrouter_connection(),
        "youtube_api_connected": check_youtube_api_connection(),
        "note": "This endpoint tests actual API connectivity and may be slower"
    }

# Import metrics service
from app.services.metrics_service import metrics_service

# Add metrics response models
class MetricsResponse(BaseModel):
    total_comments_posted: int
    total_videos_processed: int
    total_workflows: int
    agent_statistics: Dict[str, Any]
    engagement_metrics: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]
    video_details: List[Dict[str, Any]]
    last_updated: str

class VideoEngagementResponse(BaseModel):
    video_details: List[Dict[str, Any]]
    total_likes: int
    total_replies: int
    average_engagement: Dict[str, float]

# Metrics API endpoints
@app.get("/api/v1/metrics/overview", response_model=MetricsResponse)
async def get_metrics_overview():
    """Get comprehensive metrics overview"""
    try:
        metrics = await metrics_service.get_overall_metrics()
        return MetricsResponse(**metrics)
    except Exception as e:
        logger.error(f"Error getting metrics overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/metrics/engagement")
async def get_engagement_metrics():
    """Get comment engagement metrics with live YouTube data"""
    try:
        # Get base metrics
        metrics = await metrics_service.get_overall_metrics()
        video_details = metrics.get("video_details", [])
        
        # Update with live engagement data
        updated_details = await metrics_service.update_video_engagement(video_details)
        
        # Calculate totals
        total_likes = sum(v.get("engagement", {}).get("likes", 0) for v in updated_details)
        total_replies = sum(v.get("engagement", {}).get("replies", 0) for v in updated_details)
        
        # Calculate averages
        posted_comments = len([v for v in updated_details if v.get("comment_id")])
        avg_likes = round(total_likes / max(posted_comments, 1), 2)
        avg_replies = round(total_replies / max(posted_comments, 1), 2)
        
        return {
            "video_details": updated_details,
            "total_likes": total_likes,
            "total_replies": total_replies,
            "average_engagement": {
                "likes_per_comment": avg_likes,
                "replies_per_comment": avg_replies
            },
            "engagement_summary": {
                "comments_with_engagement": len([v for v in updated_details if v.get("engagement", {}).get("likes", 0) > 0]),
                "top_performing_comment": max(updated_details, key=lambda x: x.get("engagement", {}).get("likes", 0)) if updated_details else None
            }
        }
    except Exception as e:
        logger.error(f"Error getting engagement metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/metrics/agents")
async def get_agent_statistics():
    """Get detailed agent processing statistics"""
    try:
        metrics = await metrics_service.get_overall_metrics()
        agent_stats = metrics.get("agent_statistics", {})
        
        # Add performance insights
        insights = {}
        for agent_name, stats in agent_stats.items():
            videos_processed = stats.get("videos_processed", 0)
            if videos_processed > 0:
                insights[agent_name] = {
                    **stats,
                    "performance_rating": "excellent" if stats.get("success_rate", 0) >= 95 else
                                        "good" if stats.get("success_rate", 0) >= 80 else
                                        "needs_improvement"
                }
        
        return {
            "agent_statistics": insights,
            "summary": {
                "total_videos_in_pipeline": sum(s.get("videos_processed", 0) for s in agent_stats.values()),
                "overall_success_rate": round(sum(s.get("success_rate", 0) for s in agent_stats.values()) / max(len(agent_stats), 1), 2),
                "bottleneck_agent": min(agent_stats.items(), key=lambda x: x[1].get("success_rate", 100))[0] if agent_stats else None
            }
        }
    except Exception as e:
        logger.error(f"Error getting agent statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/metrics/recent-activity")
async def get_recent_activity():
    """Get recent workflow activity and processing history"""
    try:
        metrics = await metrics_service.get_overall_metrics()
        recent_activity = metrics.get("recent_activity", [])
        
        # Enhance activity with additional context
        enhanced_activity = []
        for activity in recent_activity[:20]:  # Last 20 activities
            enhanced = {
                **activity,
                "relative_time": _format_relative_time(activity.get("completed_at", "")),
                "success_rate": round((activity.get("comments_posted", 0) / max(activity.get("videos_processed", 1), 1)) * 100, 1)
            }
            enhanced_activity.append(enhanced)
        
        return {
            "recent_activity": enhanced_activity,
            "activity_summary": {
                "workflows_today": len([a for a in recent_activity if _is_today(a.get("completed_at", ""))]),
                "workflows_this_week": len([a for a in recent_activity if _is_this_week(a.get("completed_at", ""))]),
                "total_videos_today": sum(a.get("videos_processed", 0) for a in recent_activity if _is_today(a.get("completed_at", ""))),
                "total_comments_today": sum(a.get("comments_posted", 0) for a in recent_activity if _is_today(a.get("completed_at", "")))
            }
        }
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _format_relative_time(iso_string: str) -> str:
    """Format ISO timestamp as relative time"""
    try:
        if not iso_string:
            return "Unknown"
        
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"
    except Exception:
        return "Unknown"

def _is_today(iso_string: str) -> bool:
    """Check if ISO timestamp is from today"""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.date() == datetime.now().date()
    except Exception:
        return False

def _is_this_week(iso_string: str) -> bool:
    """Check if ISO timestamp is from this week"""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        return dt.date() >= start_of_week.date()
    except Exception:
        return False

@app.get("/api/v1/metrics/smart-overview", tags=["metrics"])
async def get_smart_metrics_overview():
    """Get comprehensive metrics with enhanced debugging information"""
    try:
        from app.services.metrics_service import MetricsService
        
        metrics_service = MetricsService()
        
        # Get overall metrics
        overall_metrics = await metrics_service.get_overall_metrics()
        
        # Enhanced metrics with debugging info
        smart_metrics = {
            **overall_metrics,
            "debug_info": {
                "cache_stats": metrics_service.get_cache_stats(),
                "processing_details": {
                    "data_directory_exists": Path("./data/channels").exists(),
                    "channel_directories_found": len([d for d in Path("./data/channels").iterdir() if d.is_dir()]) if Path("./data/channels").exists() else 0,
                    "workflow_temp_files": len(list(Path("./temp").glob("workflow_*.json"))) if Path("./temp").exists() else 0,
                    "state_cache_files": len(list(Path("./state_cache").glob("*.json"))) if Path("./state_cache").exists() else 0
                },
                "metrics_calculation": {
                    "comments_detection_method": "enhanced_multi_structure",
                    "data_sources_checked": ["posted_comments", "comment_posted", "workflow_result", "comment_id", "comment_url"],
                    "last_cache_refresh": metrics_service._cache.get("overall_metrics_timestamp", "never"),
                    "performance_stats": metrics_service._performance_stats
                }
            },
            "recommendations": []
        }
        
        # Add recommendations based on metrics
        if smart_metrics["total_comments_posted"] == 0 and smart_metrics["total_videos_processed"] > 0:
            smart_metrics["recommendations"].extend([
                "🔍 0 comments detected despite processing videos - check data structure compatibility",
                "🛠️ Try refreshing metrics cache: POST /api/v1/metrics/refresh-cache",
                "📊 Debug data structure: GET /api/v1/metrics/debug-data-structure",
                "🔄 Run a test workflow to verify comment posting is working"
            ])
        
        if smart_metrics["debug_info"]["processing_details"]["channel_directories_found"] == 0:
            smart_metrics["recommendations"].append(
                "📁 No channel directories found - workflow results may not be saving to expected location"
            )
        
        return smart_metrics
        
    except Exception as e:
        logger.error(f"Error getting smart metrics overview: {e}")
        return {"status": "error", "message": str(e)}

# Test endpoint removed - was interfering with real engagement data

@app.get("/api/v1/metrics/health")
async def get_metrics_health():
    """Get API health status for intelligent refresh decisions"""
    try:
        from app.services.metrics_service import MetricsService
        
        metrics_service = MetricsService()
        
        # Calculate health metrics
        current_time = time.time()
        
        # Check recent API performance
        performance_stats = metrics_service._performance_stats
        cache_stats = metrics_service.get_cache_stats()
        
        # Calculate success rate and response time
        total_requests = performance_stats.get("total_requests", 0)
        successful_requests = performance_stats.get("successful_requests", 0)
        failed_requests = performance_stats.get("failed_requests", 0)
        avg_response_time = performance_stats.get("avg_response_time", 0)
        
        success_rate = (successful_requests / max(total_requests, 1)) * 100
        
        # Determine health status
        if success_rate >= 95 and avg_response_time < 1000:
            status = "excellent"
        elif success_rate >= 80 and avg_response_time < 2000:
            status = "good"
        elif success_rate >= 60:
            status = "degraded"
        else:
            status = "unhealthy"
        
        return {
            "status": status,
            "success_rate": round(success_rate, 2),
            "avg_response_time": round(avg_response_time, 0),
            "total_requests": total_requests,
            "failed_requests": failed_requests,
            "cache_hit_rate": cache_stats.get("hit_rate", 0),
            "last_update": current_time,
            "smart_refresh_recommendations": {
                "recommended_interval": 30000 if status == "excellent" else 
                                       20000 if status == "good" else 
                                       15000 if status == "degraded" else 10000,
                "strategy": "conservative" if status in ["degraded", "unhealthy"] else 
                           "adaptive" if status == "good" else "aggressive",
                "last_analysis": f"Health: {status}, Success: {success_rate:.1f}%, Response: {avg_response_time:.0f}ms"
            }
        }
    except Exception as e:
        logger.error(f"Error getting metrics health: {e}")
        return {
            "status": "error",
            "success_rate": 0,
            "avg_response_time": 0,
            "error": str(e),
            "smart_refresh_recommendations": {
                "recommended_interval": 60000,
                "strategy": "conservative",
                "last_analysis": f"Error getting health metrics: {str(e)[:100]}"
            }
        }

@app.get("/favicon.ico")
async def get_favicon():
    """Serve the favicon"""
    from fastapi.responses import FileResponse
    import os
    
    favicon_path = "favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    else:
        # Return a default empty response if favicon doesn't exist
        raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/api/v1/metrics/blacklist")
async def get_comment_blacklist():
    """Get current comment blacklist for monitoring and debugging"""
    try:
        from app.services.metrics_service import metrics_service
        
        blacklist = metrics_service._comment_blacklist
        
        # Add statistics
        stats = {
            "total_blacklisted": len(blacklist),
            "reasons": {},
            "recent_additions": []
        }
        
        # Analyze blacklist entries
        for comment_id, entry in blacklist.items():
            reason = entry.get("reason", "unknown")
            stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1
            
            # Check if added recently (last 24 hours)
            try:
                first_failed = datetime.fromisoformat(entry["first_failed"])
                if (datetime.now() - first_failed).total_seconds() < 86400:
                    stats["recent_additions"].append({
                        "comment_id": comment_id,
                        "reason": reason,
                        "first_failed": entry["first_failed"],
                        "failure_count": entry.get("failure_count", 1)
                    })
            except:
                pass
        
        return {
            "blacklist": blacklist,
            "statistics": stats,
            "performance_impact": {
                "api_calls_saved": metrics_service._performance_stats.get('smart_skips', 0),
                "quota_preserved": f"{len(blacklist)} potential API calls avoided per metrics refresh"
            },
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting blacklist: {e}")
        return {"error": str(e)}

@app.delete("/api/v1/metrics/blacklist/{comment_id}")
async def remove_from_blacklist(comment_id: str):
    """Remove a comment from blacklist (for testing/debugging)"""
    try:
        from app.services.metrics_service import metrics_service
        
        if comment_id in metrics_service._comment_blacklist:
            removed_entry = metrics_service._comment_blacklist[comment_id]
            del metrics_service._comment_blacklist[comment_id]
            metrics_service._save_comment_blacklist()
            logger.info(f"🗑️ Removed {comment_id} from blacklist")
            return {
                "success": True, 
                "message": f"Comment {comment_id} removed from blacklist",
                "removed_entry": removed_entry
            }
        else:
            return {
                "success": False, 
                "message": f"Comment {comment_id} not found in blacklist"
            }
            
    except Exception as e:
        logger.error(f"Error removing from blacklist: {e}")
        return {"success": False, "error": str(e)}

# Authentication Routes
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, info: str = None):
    """Display login page."""
    try:
        # Set up Jinja2 templates
        templates = Jinja2Templates(directory="app/templates")
        
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": error,
            "info": info
        })
    except Exception as e:
        logger.error(f"Error rendering login page: {e}")
        return HTMLResponse("""
            <html>
                <head><title>Login Error</title></head>
                <body>
                    <h1>Error Loading Login Page</h1>
                    <p>Please check the application logs.</p>
                </body>
            </html>
        """, status_code=500)

@app.post("/auth/login", response_class=HTMLResponse)
async def login_user(request: Request):
    """Handle user login."""
    try:
        form_data = await request.form()
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        
        if not username or not password:
            return await login_page(request, error="Please enter both username and password")
        
        # Authenticate user
        auth_result = auth_service.authenticate_user(username, password)
        
        if not auth_result["success"]:
            return await login_page(request, error=auth_result["message"])
        
        # Check if password reset is required
        if auth_result.get("requires_password_reset", False):
            # Create session for password reset
            session_id = auth_service.create_session(
                auth_result["user_id"], 
                auth_result["username"], 
                auth_result["is_admin"]
            )
            
            # Redirect to password reset with session
            response = HTMLResponse("""
                <html>
                    <head>
                        <title>Password Reset Required</title>
                        <meta http-equiv="refresh" content="0; url=/auth/reset-password">
                    </head>
                    <body>
                        <h1>Password Reset Required</h1>
                        <p>Redirecting to password reset...</p>
                    </body>
                </html>
            """)
            response.set_cookie("session_id", session_id, httponly=True, secure=False, max_age=86400)
            return response
        
        # Create session
        session_id = auth_service.create_session(
            auth_result["user_id"], 
            auth_result["username"], 
            auth_result["is_admin"]
        )
        
        logger.info(f"✅ User {username} logged in successfully")
        
        # Redirect to dashboard
        response = HTMLResponse("""
            <html>
                <head>
                    <title>Login Successful</title>
                    <meta http-equiv="refresh" content="0; url=/dashboard">
                </head>
                <body>
                    <h1>Login Successful</h1>
                    <p>Redirecting to dashboard...</p>
                </body>
            </html>
        """)
        response.set_cookie("session_id", session_id, httponly=True, secure=False, max_age=86400)
        return response
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return await login_page(request, error="Login system error. Please try again.")

@app.get("/auth/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, error: str = None):
    """Display password reset page."""
    try:
        # Check if user is authenticated
        session_id = request.cookies.get("session_id")
        if not session_id:
            return HTMLResponse("""
                <html>
                    <head>
                        <title>Access Denied</title>
                        <meta http-equiv="refresh" content="2; url=/login">
                    </head>
                    <body>
                        <h1>Access Denied</h1>
                        <p>Please login first. Redirecting...</p>
                    </body>
                </html>
            """)
        
        session = auth_service.validate_session(session_id)
        if not session:
            return HTMLResponse("""
                <html>
                    <head>
                        <title>Session Expired</title>
                        <meta http-equiv="refresh" content="2; url=/login">
                    </head>
                    <body>
                        <h1>Session Expired</h1>
                        <p>Please login again. Redirecting...</p>
                    </body>
                </html>
            """)
        
        # Check if user needs password reset
        user_info = auth_service.get_user_info(session["username"])
        is_first_time = user_info and user_info.get("requires_password_reset", False)
        
        # Set up Jinja2 templates
        templates = Jinja2Templates(directory="app/templates")
        
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "error": error,
            "username": session["username"],
            "is_first_time": is_first_time
        })
        
    except Exception as e:
        logger.error(f"Error rendering reset password page: {e}")
        return HTMLResponse("""
            <html>
                <head><title>Reset Password Error</title></head>
                <body>
                    <h1>Error Loading Reset Password Page</h1>
                    <p>Please check the application logs.</p>
                </body>
            </html>
        """, status_code=500)

@app.post("/auth/reset-password", response_class=HTMLResponse)
async def reset_user_password(request: Request):
    """Handle password reset."""
    try:
        # Check session
        session_id = request.cookies.get("session_id")
        if not session_id:
            return await login_page(request, error="Session expired. Please login again.")
        
        session = auth_service.validate_session(session_id)
        if not session:
            return await login_page(request, error="Session expired. Please login again.")
        
        form_data = await request.form()
        username = form_data.get("username", "").strip()
        current_password = form_data.get("current_password", "")
        new_password = form_data.get("new_password", "")
        confirm_password = form_data.get("confirm_password", "")
        
        # Validate form data
        if not all([username, current_password, new_password, confirm_password]):
            return await reset_password_page(request, error="All fields are required")
        
        if new_password != confirm_password:
            return await reset_password_page(request, error="New passwords do not match")
        
        if len(new_password) < 8:
            return await reset_password_page(request, error="New password must be at least 8 characters long")
        
        # Reset password
        reset_result = auth_service.reset_password(username, current_password, new_password)
        
        if not reset_result["success"]:
            return await reset_password_page(request, error=reset_result["message"])
        
        logger.info(f"✅ Password reset successfully for user: {username}")
        
        # Logout current session (force re-login with new password)
        auth_service.logout_session(session_id)
        
        # Redirect to login with success message
        response = HTMLResponse("""
            <html>
                <head>
                    <title>Password Reset Successful</title>
                    <meta http-equiv="refresh" content="3; url=/login">
                </head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f8ff;">
                    <h1 style="color: #28a745;">🎉 Password Reset Successful!</h1>
                    <p>Your password has been updated successfully.</p>
                    <p>Please login with your new password.</p>
                    <p>Redirecting to login page in 3 seconds...</p>
                    <a href="/login" style="color: #007bff;">Click here to login now</a>
                </body>
            </html>
        """)
        response.delete_cookie("session_id")
        return response
        
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        return await reset_password_page(request, error="Password reset system error. Please try again.")

@app.get("/auth/logout")
async def logout_user(request: Request):
    """Handle user logout."""
    try:
        session_id = request.cookies.get("session_id")
        if session_id:
            auth_service.logout_session(session_id)
        
        response = HTMLResponse("""
            <html>
                <head>
                    <title>Logged Out</title>
                    <meta http-equiv="refresh" content="2; url=/login">
                </head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f8ff;">
                    <h1>👋 Logged Out</h1>
                    <p>You have been logged out successfully.</p>
                    <p>Redirecting to login page...</p>
                    <a href="/login" style="color: #007bff;">Click here to login again</a>
                </body>
            </html>
        """)
        response.delete_cookie("session_id")
        return response
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return HTMLResponse("""
            <html>
                <head><title>Logout Error</title></head>
                <body>
                    <h1>Logout Error</h1>
                    <p>There was an error during logout.</p>
                    <a href="/login">Return to Login</a>
                </body>
            </html>
        """)
