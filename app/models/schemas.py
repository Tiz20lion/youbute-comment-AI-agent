"""
Pydantic models and schemas for YouTube Comment Automation Bot
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator, HttpUrl

# Import settings to use configuration values
from ..config import settings


class ProcessingStatus(str, Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PROCESSING = "processing"  # Add this for workflow compatibility
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CommentStyle(str, Enum):
    """Comment style enumeration"""
    ENGAGING = "engaging"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    FUNNY = "funny"
    EDUCATIONAL = "educational"


class VideoComment(BaseModel):
    """Individual comment model"""
    comment_id: str
    author: str
    text: str
    likes: int = 0
    replies: int = 0
    published_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CommentData(BaseModel):
    """Comment data model for YouTube API interactions"""
    comment_id: str = Field(..., description="Comment ID")
    video_id: str = Field(..., description="Video ID")
    author_name: str = Field(..., description="Comment author name")
    author_channel_id: Optional[str] = Field(None, description="Author channel ID")
    text: str = Field(..., description="Comment text")
    like_count: int = Field(0, description="Comment like count")
    published_at: datetime = Field(..., description="Comment publication date")
    reply_count: int = Field(0, description="Number of replies")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DescriptionMetadata(BaseModel):
    """Video description extraction metadata"""
    success: bool = Field(..., description="Whether description extraction was successful")
    error: str = Field("", description="Error message if extraction failed")
    word_count: int = Field(0, description="Number of words in description")
    char_count: int = Field(0, description="Number of characters in description")


# Removed transcript-related models - using descriptions instead


class VideoData(BaseModel):
    """Individual video data model"""
    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    url: str = Field(..., description="Video URL")
    description: Optional[str] = Field(None, description="Video description")
    published_at: Optional[datetime] = Field(None, description="Video publication date")
    duration: Optional[str] = Field(None, description="Video duration")
    view_count: Optional[int] = Field(None, description="Video view count")
    like_count: Optional[int] = Field(None, description="Video like count")
    comment_count: Optional[int] = Field(None, description="Video comment count")
    
    # Processing data - using description instead of transcript
    description_metadata: Optional[DescriptionMetadata] = Field(None, description="Description extraction metadata")
    comments: List[VideoComment] = Field(default_factory=list, description="Video comments")
    summary: Optional[str] = Field(None, description="AI-generated summary")
    generated_comment: Optional[str] = Field(None, description="Generated comment")
    
    # Status tracking
    status: ProcessingStatus = Field(ProcessingStatus.PENDING, description="Processing status")
    comment_posted: bool = Field(False, description="Whether comment was posted")
    posted_at: Optional[datetime] = Field(None, description="When comment was posted")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChannelData(BaseModel):
    """Channel data model"""
    channel_id: str = Field(..., description="YouTube channel ID")
    channel_name: str = Field(..., description="Channel name")
    channel_url: Optional[str] = Field(None, description="Channel URL")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    status: ProcessingStatus = Field(ProcessingStatus.PENDING, description="Processing status")
    
    # Videos data
    videos: List[VideoData] = Field(default_factory=list, description="Channel videos")
    
    # Statistics
    statistics: Dict[str, int] = Field(
        default_factory=lambda: {
            "total_videos": 0,
            "processed_videos": 0,
            "failed_videos": 0,
            "comments_posted": 0
        },
        description="Processing statistics"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkflowState(BaseModel):
    """LangGraph workflow state model"""
    channel_id: str
    channel_name: str
    channel_url: str
    user_id: str
    chat_id: str
    
    # Processing data
    videos: List[VideoData] = Field(default_factory=list)
    current_step: str = "channel_parser"
    completed_steps: List[str] = Field(default_factory=list)
    
    # Configuration - now using settings
    max_videos: int = settings.CHANNEL_PARSER_MAX_VIDEOS
    max_comments: int = settings.MAX_COMMENTS_PER_VIDEO
    comment_style: CommentStyle = CommentStyle.ENGAGING
    
    # Status
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# API Request/Response Models

class ProcessChannelRequest(BaseModel):
    """Request to process a YouTube channel"""
    channel_url: str = Field(..., description="YouTube channel URL")
    user_id: str = Field(..., description="Telegram user ID")
    chat_id: str = Field(..., description="Telegram chat ID")
    max_videos: int = Field(settings.CHANNEL_PARSER_MAX_VIDEOS, ge=1, le=50, description="Maximum videos to process")
    max_comments: int = Field(settings.MAX_COMMENTS_PER_VIDEO, ge=10, le=1000, description="Maximum comments per video")
    comment_style: CommentStyle = Field(CommentStyle.ENGAGING, description="Comment generation style")
    
    @validator('channel_url')
    def validate_channel_url(cls, v):
        if not any(domain in v.lower() for domain in ['youtube.com', 'youtu.be']):
            raise ValueError('Must be a valid YouTube URL')
        return v


class ProcessChannelResponse(BaseModel):
    """Response from channel processing request"""
    workflow_id: str = Field(..., description="Workflow execution ID")
    status: ProcessingStatus = Field(..., description="Initial status")
    message: str = Field(..., description="Response message")
    estimated_completion_time: Optional[int] = Field(None, description="Estimated completion time in minutes")


class WorkflowStatusResponse(BaseModel):
    """Workflow status response"""
    workflow_id: str
    status: ProcessingStatus
    current_step: str
    completed_steps: List[str]
    progress_percentage: int = Field(ge=0, le=100)
    message: str
    error_message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None


class TelegramUpdate(BaseModel):
    """Telegram webhook update model"""
    update_id: int
    message: Optional[Dict[str, Any]] = None
    callback_query: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"


class TelegramMessage(BaseModel):
    """Telegram message model"""
    message_id: int
    chat_id: int
    user_id: int
    text: Optional[str] = None
    date: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NotificationRequest(BaseModel):
    """Notification request model"""
    user_id: str
    chat_id: str
    message: str
    message_type: str = "info"  # info, success, warning, error
    buttons: Optional[List[Dict[str, str]]] = None


class HealthCheckResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: datetime
    version: str
    environment: str
    services: Dict[str, str]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VideoEngagementResponse(BaseModel):
    video_details: List[Dict[str, Any]]
    total_likes: int
    total_replies: int
    average_engagement: Dict[str, float]


# Authentication Models
class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=4, description="Password")


class PasswordReset(BaseModel):
    username: str = Field(..., description="Username")
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")
    confirm_password: str = Field(..., description="Confirm new password")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=8, description="Password")
    is_admin: bool = Field(default=False, description="Admin privileges")


class AuthResponse(BaseModel):
    success: bool
    message: str
    redirect_url: Optional[str] = None
    requires_password_reset: Optional[bool] = None 