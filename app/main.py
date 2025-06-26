"""
FastAPI Application for YouTube Comment Automation

This is the main FastAPI application that orchestrates the YouTube comment automation workflow.
It provides REST API endpoints and integrates with the Telegram bot service.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.utils.logging_config import get_logger, setup_logging

# Initialize logging system
setup_logging()
from app.models.schemas import ProcessChannelRequest, ProcessChannelResponse
from app.workflow.langgraph_workflow import get_workflow_instance, WorkflowState
from app.services.telegram_service import telegram_service

# Get logger
logger = get_logger(__name__)

# Global state for active workflows
active_workflows: Dict[str, Dict[str, Any]] = {}
telegram_bot_task: Optional[asyncio.Task] = None

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

async def start_telegram_bot():
    """Start the Telegram bot in the background."""
    global telegram_bot_task
    
    try:
        logger.info("Starting Telegram bot...")
        
        # Set up workflow callback
        telegram_service.set_workflow_callback(start_workflow_from_telegram)
        
        # Start polling in background task
        telegram_bot_task = asyncio.create_task(telegram_service.start_polling())
        
        # Wait a moment for the bot to initialize, then send welcome message
        await asyncio.sleep(2)
        await telegram_service.send_startup_welcome_message()
        
        logger.info("Telegram bot started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
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
    
    # Create necessary directories
    logger.info("Creating/verifying required directories...")
    settings.create_directories()
    
    # Start Telegram bot if token is configured
    if settings.TELEGRAM_BOT_TOKEN:
        try:
            await start_telegram_bot()
        except Exception as e:
            logger.error(f"Failed to start Telegram bot during startup: {e}")
    else:
        logger.warning("Telegram bot token not configured, skipping bot startup")
    
    logger.info("Application startup completed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down YouTube Comment Bot application...")
    
    # Stop Telegram bot with timeout
    if settings.TELEGRAM_BOT_TOKEN:
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Calculate workflow success rate."""
    try:
        posting_results = final_state.get("posting_results", {})
        if not posting_results:
            return 0
        
        successful = sum(1 for result in posting_results.values() if result.get("success"))
        total = len(posting_results)
        
        return int((successful / total) * 100) if total > 0 else 0
    
    except Exception:
        return 0

# API Routes

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "YouTube Comment Bot API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "start_workflow": "/api/v1/workflow/start",
            "workflow_status": "/api/v1/workflow/{workflow_id}/status",
            "list_workflows": "/api/v1/workflow/list",
            "system_info": "/api/v1/system/info"
        }
    }

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
    state = workflow_data["state"]
    
    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status=workflow_data["status"],
        created_at=workflow_data["created_at"],
        youtube_url=state["youtube_url"],
        current_step=state.get("current_step"),
        progress=state.get("progress"),
        error=state.get("error")
    )

@app.get("/api/v1/workflow/list")
async def list_workflows():
    """List all workflows."""
    workflows = []
    
    for workflow_id, workflow_data in active_workflows.items():
        state = workflow_data["state"]
        workflows.append({
            "workflow_id": workflow_id,
            "status": workflow_data["status"],
            "created_at": workflow_data["created_at"],
            "youtube_url": state["youtube_url"],
            "current_step": state.get("current_step")
        })
    
    return {
        "workflows": workflows,
        "total": len(workflows)
    }

@app.get("/api/v1/system/info", response_model=SystemInfoResponse)
async def get_system_info():
    """Get system information."""
    return SystemInfoResponse(
        status="running",
        active_workflows=len(active_workflows),
        telegram_bot_status="running" if telegram_service.application else "stopped",
        uptime="N/A"  # TODO: Implement uptime tracking
    )

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting YouTube Comment Bot API server...")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    ) 