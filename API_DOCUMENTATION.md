# YouTube Comment AI Agent - Comprehensive API Documentation

## Overview

The YouTube Comment AI Agent is a FastAPI-based application that automates intelligent comment generation and posting on YouTube videos using a multi-agent AI workflow. The system processes YouTube channels/videos, extracts content, analyzes it using AI models, generates contextual comments, and posts them automatically.

### Architecture
The application uses a **6-agent workflow** powered by LangGraph:
1. **Channel Parser** - Extracts channel information and video list
2. **Description Extractor** - Extracts video descriptions and metadata  
3. **Content Scraper** - Scrapes additional video content and comments
4. **Content Analyzer** - AI analysis of video content and context
5. **Comment Generator** - AI generation of contextual comments
6. **Comment Poster** - Posts comments to YouTube (requires OAuth2)

## Base URL
```
http://localhost:7844
```

## Quick Start

### 1. Environment Setup
Create a `.env` file with required credentials:

```bash
# Core APIs (Required)
OPENROUTER_API_KEY=sk-or-v1-your-key-here
YOUTUBE_API_KEY=AIzaSyB-your-youtube-api-key  
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret

# Application
PORT=7844
ENABLE_COMMENT_POSTING=true
```

### 2. Start a Workflow
```bash
curl -X POST http://localhost:7844/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/@channelname"}'
```

### 3. Check Status
```bash
curl http://localhost:7844/api/v1/workflow/{workflow_id}/status
```

---

## Table of Contents

1. [Core API Endpoints](#core-api-endpoints)
2. [Workflow Management](#workflow-management) 
3. [Settings Management](#settings-management)
4. [Metrics & Analytics](#metrics--analytics)
5. [Logs & Monitoring](#logs--monitoring)
6. [Web Dashboard](#web-dashboard)
7. [WebSocket API](#websocket-api)
8. [Data Models](#data-models)
9. [Error Handling](#error-handling)

---

## Core API Endpoints

### Health & System Info

#### GET `/health`
**Quick health check**

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "telegram_bot": "running"
}
```

#### GET `/api/v1/system/info`
**Comprehensive system information**

```http
GET /api/v1/system/info
```

**Response:**
```json
{
  "status": "running",
  "active_workflows": 2,
  "telegram_bot_status": "running",
  "uptime": "2:45:30",
  "version": "1.0.0",
  "metrics": {
    "total_workflows": 15,
    "successful_workflows": 12,
    "failed_workflows": 3,
    "total_comments_posted": 45,
    "uptime": 9930
  }
}
```

---

## Workflow Management

### Start Workflow

#### POST `/api/v1/workflow/start`
**Start a new YouTube comment workflow**

```http
POST /api/v1/workflow/start
Content-Type: application/json

{
  "youtube_url": "https://www.youtube.com/@channelname",
  "user_id": 123456789,
  "chat_id": 123456789
}
```

**Supported URL Formats:**
- `https://www.youtube.com/@channelname`
- `https://www.youtube.com/c/channelname`
- `https://www.youtube.com/channel/UC123456789`
- `https://www.youtube.com/watch?v=videoid` (processes individual video + channel)
- Multiple URLs separated by spaces/commas

**Response:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "message": "Workflow started successfully"
}
```

### Workflow Status

#### GET `/api/v1/workflow/{workflow_id}/status`
**Get detailed workflow status**

```http
GET /api/v1/workflow/550e8400-e29b-41d4-a716-446655440000/status
```

**Response:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "in_progress",
  "created_at": "2024-01-15T10:30:00Z",
  "youtube_url": "https://www.youtube.com/@channelname",
  "current_step": "content_analyzer",
  "progress": {
    "channel_parser": {"status": "completed"},
    "description_extractor": {"status": "completed"},
    "content_scraper": {"status": "completed"},
    "content_analyzer": {"status": "in_progress"},
    "comment_generator": {"status": "pending"},
    "comment_poster": {"status": "pending"}
  },
  "error": null
}
```

### List Workflows

#### GET `/api/v1/workflow/list`
**List all workflows**

```http
GET /api/v1/workflow/list
```

**Response:**
```json
{
  "workflows": [
    {
      "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "created_at": "2024-01-15T10:30:00Z",
      "youtube_url": "https://www.youtube.com/@channelname",
      "current_step": "completed"
    }
  ],
  "total": 1
}
```

### Cancel Workflow

#### POST `/api/v1/workflow/{workflow_id}/cancel`
**Cancel a running workflow**

```http
POST /api/v1/workflow/550e8400-e29b-41d4-a716-446655440000/cancel
```

**Response:**
```json
{
  "status": "success",
  "message": "Workflow cancelled"
}
```

---

## Settings Management

### Configuration Status

#### GET `/api/v1/configuration/status`
**Get lightweight configuration status**

```http
GET /api/v1/configuration/status
```

**Response:**
```json
{
  "telegram_configured": true,
  "openrouter_configured": true,
  "youtube_oauth_configured": true,
  "port": 7844,
  "debug_mode": true
}
```

### Detailed Configuration

#### GET `/api/v1/configuration/details`
**Get detailed configuration information**

```http
GET /api/v1/configuration/details
```

**Response:**
```json
{
  "current_llm_model": "google/gemini-2.0-flash-exp:free",
  "available_models": {
    "google/gemini-2.0-flash-exp:free": {
      "name": "google/gemini-2.0-flash-exp:free",
      "description": "🚀 Google Gemini 2.0 Flash Experimental (FREE)",
      "cost": "$0.00/$0.00 per 1M",
      "context": "1M"
    }
  },
  "max_videos": 10,
  "telegram_bot_status": "running",
  "telegram_configured": true,
  "openrouter_configured": true,
  "youtube_oauth_configured": true,
  "comment_posting_enabled": true,
  "oauth2_authenticated": true
}
```

### Update LLM Model

#### POST `/api/v1/configuration/llm`
**Update the LLM model for agents**

```http
POST /api/v1/configuration/llm
Content-Type: application/json

{
  "model": "google/gemini-2.0-flash-exp:free"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "LLM model updated to google/gemini-2.0-flash-exp:free",
  "new_model": "google/gemini-2.0-flash-exp:free"
}
```

### Update Video Count

#### POST `/api/v1/configuration/videos`
**Update maximum number of videos to fetch**

```http
POST /api/v1/configuration/videos
Content-Type: application/json

{
  "max_videos": 15
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Max videos updated to 15",
  "new_count": 15
}
```

### Telegram Bot Control

#### POST `/api/v1/telegram/control`
**Control Telegram bot (start/stop/restart)**

```http
POST /api/v1/telegram/control
Content-Type: application/json

{
  "action": "restart"
}
```

**Actions:** `start`, `stop`, `restart`

**Response:**
```json
{
  "status": "success",
  "message": "Telegram bot restarted successfully"
}
```

### Get Settings

#### GET `/api/v1/settings`
**Get current settings and configuration status**

```http
GET /api/v1/settings
```

**Response:**
```json
{
  "api_keys": {
    "openrouter_api_key": "sk-or-v1••••1234",
    "youtube_api_key": "AIzaSyB••••abcd",
    "google_client_id": "123456789••••.apps.googleusercontent.com",
    "google_client_secret": "GOCSPX••••5678"
  },
  "telegram_settings": {
    "bot_token": "123456789:••••abcd",
    "allowed_user_ids": "123456789,987654321"
  },
  "oauth2_status": {
    "configured": true,
    "authenticated": true,
    "redirect_uri": "http://localhost:7844/oauth2callback",
    "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"]
  },
  "configuration_status": {
    "telegram_configured": true,
    "openrouter_configured": true,
    "youtube_api_configured": true,
    "oauth2_configured": true
  },
  "token_validation_states": {
    "openrouter_api_key": "valid",
    "youtube_api_key": "valid",
    "google_client_id": "valid",
    "google_client_secret": "valid",
    "telegram_token": "valid"
  }
}
```

### Update API Keys

#### POST `/api/v1/settings/api-keys`
**Update API keys configuration**

```http
POST /api/v1/settings/api-keys
Content-Type: application/json

{
  "openrouter_api_key": "sk-or-v1-new-key",
  "youtube_api_key": "AIzaSyB-new-youtube-key",
  "google_client_id": "new-client-id.apps.googleusercontent.com",
  "google_client_secret": "GOCSPX-new-client-secret"
}
```

**Response:**
```json
{
  "message": "API keys updated successfully",
  "updated_keys": ["OpenRouter API Key", "YouTube API Key"]
}
```

### Update Telegram Settings

#### POST `/api/v1/settings/telegram`
**Update Telegram settings configuration**

```http
POST /api/v1/settings/telegram
Content-Type: application/json

{
  "bot_token": "123456789:new-bot-token",
  "allowed_user_ids": "123456789,987654321,555666777"
}
```

**Response:**
```json
{
  "message": "Telegram settings updated successfully",
  "updated_settings": ["Bot Token", "Allowed User IDs", "Bot Restarted"],
  "restart_required": true
}
```

### OAuth2 Management

#### POST `/api/v1/settings/oauth2`
**Manage OAuth2 setup and authentication**

**Generate Authorization URL:**
```http
POST /api/v1/settings/oauth2
Content-Type: application/json

{
  "action": "generate_url"
}
```

**Response:**
```json
{
  "action": "authorization_url_generated",
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "redirect_uri": "http://localhost:7844/oauth2callback",
  "state": "random-state-token",
  "message": "Open the authorization URL and complete the OAuth flow..."
}
```

**Complete Authorization:**
```http
POST /api/v1/settings/oauth2
Content-Type: application/json

{
  "action": "complete_auth",
  "response_url": "http://localhost:7844/oauth2callback?code=...&state=..."
}
```

**Response:**
```json
{
  "action": "authorization_completed",
  "success": true,
  "message": "OAuth2 authentication completed successfully. Comment posting is now enabled."
}
```

### Toggle Comment Posting

#### POST `/api/v1/configuration/comment-posting`
**Enable or disable comment posting**

```http
POST /api/v1/configuration/comment-posting
Content-Type: application/json

{
  "enabled": true
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Comment posting enabled",
  "enabled": true,
  "oauth2_required": false
}
```

### Test Credentials

#### GET `/api/v1/configuration/test-credentials`
**Test API credentials validity**

```http
GET /api/v1/configuration/test-credentials
```

**Response:**
```json
{
  "openrouter": {"status": "valid", "model": "google/gemini-2.0-flash-exp:free"},
  "youtube": {"status": "valid", "quota_used": 150},
  "oauth2": {"status": "valid", "can_post_comments": true},
  "telegram": {"status": "valid", "bot_username": "@your_bot"}
}
```

---

## Metrics & Analytics

### Metrics Overview

#### GET `/api/v1/metrics/overview`
**Get comprehensive metrics overview**

```http
GET /api/v1/metrics/overview
```

**Response:**
```json
{
  "total_comments_posted": 45,
  "total_videos_processed": 67,
  "total_workflows": 15,
  "agent_statistics": {
    "channel_parser": {
      "videos_processed": 67,
      "success_rate": 98.5,
      "avg_processing_time": 12.3
    },
    "content_analyzer": {
      "videos_processed": 65,
      "success_rate": 95.4,
      "avg_processing_time": 45.2
    }
  },
  "engagement_metrics": {
    "total_likes": 156,
    "total_replies": 23,
    "avg_likes_per_comment": 3.47
  },
  "recent_activity": [
    {
      "workflow_id": "abc123",
      "channel_name": "Tech Channel",
      "completed_at": "2024-01-15T10:30:00Z",
      "videos_processed": 5,
      "comments_posted": 4
    }
  ],
  "video_details": [
    {
      "video_id": "abc123",
      "video_title": "AI Revolution 2024",
      "comment_id": "xyz789",
      "comment_url": "https://youtube.com/watch?v=abc123&lc=xyz789",
      "engagement": {
        "likes": 12,
        "replies": 3
      }
    }
  ],
  "last_updated": "2024-01-15T10:30:00Z"
}
```

### Engagement Metrics

#### GET `/api/v1/metrics/engagement`
**Get comment engagement metrics with live YouTube data**

```http
GET /api/v1/metrics/engagement
```

**Response:**
```json
{
  "video_details": [
    {
      "video_id": "abc123",
      "video_title": "AI Revolution 2024",
      "comment_id": "xyz789",
      "comment_url": "https://youtube.com/watch?v=abc123&lc=xyz789",
      "engagement": {
        "likes": 12,
        "replies": 3
      }
    }
  ],
  "total_likes": 156,
  "total_replies": 23,
  "average_engagement": {
    "likes_per_comment": 3.47,
    "replies_per_comment": 0.51
  },
  "engagement_summary": {
    "comments_with_engagement": 32,
    "top_performing_comment": {
      "video_title": "Best AI Tools",
      "engagement": {"likes": 25, "replies": 8}
    }
  }
}
```

### Agent Statistics

#### GET `/api/v1/metrics/agents`
**Get detailed agent processing statistics**

```http
GET /api/v1/metrics/agents
```

**Response:**
```json
{
  "agent_statistics": {
    "channel_parser": {
      "videos_processed": 67,
      "success_rate": 98.5,
      "avg_processing_time": 12.3,
      "performance_rating": "excellent"
    },
    "content_analyzer": {
      "videos_processed": 65,
      "success_rate": 95.4,
      "avg_processing_time": 45.2,
      "performance_rating": "excellent"
    }
  },
  "summary": {
    "total_videos_in_pipeline": 67,
    "overall_success_rate": 96.2,
    "bottleneck_agent": null
  }
}
```

### Recent Activity

#### GET `/api/v1/metrics/recent-activity`
**Get recent workflow activity and processing history**

```http
GET /api/v1/metrics/recent-activity
```

**Response:**
```json
{
  "recent_activity": [
    {
      "workflow_id": "abc123",
      "channel_name": "Tech Channel",
      "completed_at": "2024-01-15T10:30:00Z",
      "videos_processed": 5,
      "comments_posted": 4,
      "relative_time": "2 hours ago",
      "success_rate": 80.0
    }
  ],
  "activity_summary": {
    "workflows_today": 3,
    "workflows_this_week": 15,
    "total_videos_today": 18,
    "total_comments_today": 14
  }
}
```

### Smart Metrics Overview

#### GET `/api/v1/metrics/smart-overview`
**Get comprehensive metrics with enhanced debugging information**

```http
GET /api/v1/metrics/smart-overview
```

**Response:**
```json
{
  "total_comments_posted": 45,
  "total_videos_processed": 67,
  "debug_info": {
    "cache_stats": {
      "hit_rate": 85.2,
      "total_requests": 150,
      "cache_hits": 128
    },
    "processing_details": {
      "data_directory_exists": true,
      "channel_directories_found": 5,
      "workflow_temp_files": 2
    },
    "metrics_calculation": {
      "comments_detection_method": "enhanced_multi_structure",
      "data_sources_checked": ["posted_comments", "comment_posted", "workflow_result"],
      "last_cache_refresh": "2024-01-15T10:25:00Z"
    }
  },
  "recommendations": [
    "🔄 Run a test workflow to verify comment posting is working",
    "📊 Debug data structure: GET /api/v1/metrics/debug-data-structure"
  ]
}
```

### Metrics Health

#### GET `/api/v1/metrics/health`
**Get API health status for intelligent refresh decisions**

```http
GET /api/v1/metrics/health
```

**Response:**
```json
{
  "status": "excellent",
  "success_rate": 98.5,
  "avg_response_time": 245,
  "total_requests": 1500,
  "failed_requests": 23,
  "cache_hit_rate": 85.2,
  "last_update": 1705318200,
  "smart_refresh_recommendations": {
    "recommended_interval": 30000,
    "strategy": "aggressive",
    "last_analysis": "Health: excellent, Success: 98.5%, Response: 245ms"
  }
}
```

### Comment Blacklist Management

#### GET `/api/v1/metrics/blacklist`
**Get blacklisted comments**

```http
GET /api/v1/metrics/blacklist
```

**Response:**
```json
{
  "blacklisted_comments": [
    {
      "comment_id": "xyz789",
      "video_title": "Sample Video",
      "reason": "spam",
      "blacklisted_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

#### DELETE `/api/v1/metrics/blacklist/{comment_id}`
**Remove comment from blacklist**

```http
DELETE /api/v1/metrics/blacklist/xyz789
```

**Response:**
```json
{
  "status": "success",
  "message": "Comment xyz789 removed from blacklist"
}
```

---

## Logs & Monitoring

### Get Application Logs

#### GET `/api/v1/logs`
**Get recent application logs**

```http
GET /api/v1/logs?limit=50&level=info
```

**Query Parameters:**
- `limit` (optional): Number of log entries (default: 100, max: 1000)
- `level` (optional): Log level filter (`debug`, `info`, `warning`, `error`)
- `module` (optional): Filter by module name
- `since` (optional): ISO timestamp to get logs since

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "level": "info",
      "message": "Workflow started successfully",
      "module": "workflow",
      "workflow_id": "abc123"
    },
    {
      "timestamp": "2024-01-15T10:29:45Z",
      "level": "info",
      "message": "Channel parser completed",
      "module": "channel_parser"
    }
  ],
  "total": 50,
  "filtered": true
}
```

### Get Workflow Logs

#### GET `/api/v1/workflow/{workflow_id}/logs`
**Get logs for a specific workflow**

```http
GET /api/v1/workflow/550e8400-e29b-41d4-a716-446655440000/logs
```

**Response:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "logs": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "level": "info",
      "message": "Workflow 550e8400-e29b-41d4-a716-446655440000 status update",
      "module": "workflow",
      "agent": "channel_parser"
    }
  ],
  "total": 25
}
```

---

## Web Dashboard

### Dashboard Routes

#### GET `/dashboard`
**Main web dashboard interface**

```http
GET /dashboard
```

Returns HTML dashboard with:
- Workflow management interface
- Real-time agent status cards
- Start new workflow form
- Live metrics display

#### GET `/settings`
**Settings configuration page**

```http
GET /settings
```

Returns HTML settings interface with:
- API keys configuration
- Telegram bot settings
- OAuth2 setup
- Model configuration

#### GET `/metrics`
**Metrics dashboard page**

```http
GET /metrics
```

Returns HTML metrics dashboard with:
- Agent performance statistics
- Comment engagement metrics
- Recent activity
- Real-time updates via WebSocket

#### GET `/oauth2callback`
**OAuth2 callback handler**

```http
GET /oauth2callback?code=...&state=...
```

Handles OAuth2 authentication callback from Google.

#### GET `/favicon.ico`
**Application favicon**

```http
GET /favicon.ico
```

Returns the application favicon.

---

## WebSocket API

### Real-time Updates

#### WebSocket `/ws`
**WebSocket endpoint for real-time updates**

```javascript
const ws = new WebSocket('ws://localhost:7844/ws');

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    switch(message.type) {
        case 'connection':
            console.log('Connected:', message.data);
            break;
        case 'log_entry':
            console.log('New log:', message.data);
            break;
        case 'metrics_update':
            console.log('Metrics updated:', message.data);
            break;
        case 'workflow_update':
            console.log('Workflow update:', message.data);
            break;
        case 'telegram_status':
            console.log('Telegram status:', message.data);
            break;
        case 'config_update':
            console.log('Configuration changed:', message.data);
            break;
        case 'oauth2_success':
            console.log('OAuth2 authenticated:', message.data);
            break;
        case 'error':
            console.error('Error:', message.data);
            break;
    }
};

// Send ping to keep connection alive
ws.send(JSON.stringify({type: 'ping'}));
```

**Message Types:**
- `connection` - Connection established
- `log_entry` - New log entry  
- `metrics_update` - Metrics update
- `workflow_update` - Workflow status change
- `telegram_status` - Telegram bot status change
- `config_update` - Configuration change
- `oauth2_success` - OAuth2 authentication success
- `agent_update` - Individual agent status
- `error` - Error notification

---

## Data Models

### Core Workflow Models

#### WorkflowState
```typescript
interface WorkflowState {
  workflow_id: string;
  youtube_url: string;
  user_id?: number;
  chat_id?: number;
  channel_data?: ChannelData;
  videos: VideoData[];
  current_step: string;
  completed_steps: string[];
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  error_message?: string;
  progress: Record<string, {status: string}>;
  statistics: Record<string, any>;
  started_at: string;
  last_updated: string;
  completed_at?: string;
  workflow_summary?: any;
}
```

#### VideoData
```typescript
interface VideoData {
  video_id: string;
  title: string;
  url: string;
  description?: string;
  published_at?: string;
  duration?: string;
  view_count?: number;
  like_count?: number;
  comment_count?: number;
  description_metadata?: DescriptionMetadata;
  comments: VideoComment[];
  summary?: string;
  generated_comment?: string;
  status: ProcessingStatus;
  comment_posted: boolean;
  posted_at?: string;
  error_message?: string;
}
```

#### ChannelData
```typescript
interface ChannelData {
  channel_id: string;
  channel_name: string;
  channel_url?: string;
  processed_at: string;
  status: ProcessingStatus;
  videos: VideoData[];
  statistics: {
    total_videos: number;
    processed_videos: number;
    failed_videos: number;
    comments_posted: number;
  };
  metadata: Record<string, any>;
}
```

### Request/Response Models

#### StartWorkflowRequest
```typescript
interface StartWorkflowRequest {
  youtube_url: string;
  user_id?: number;
  chat_id?: number;
}
```

#### APIKeysUpdate
```typescript
interface APIKeysUpdate {
  openrouter_api_key?: string;
  youtube_api_key?: string;
  google_client_id?: string;
  google_client_secret?: string;
}
```

#### TelegramSettingsUpdate
```typescript
interface TelegramSettingsUpdate {
  bot_token?: string;
  allowed_user_ids?: string;
}
```

#### MetricsResponse
```typescript
interface MetricsResponse {
  total_comments_posted: number;
  total_videos_processed: number;
  total_workflows: number;
  agent_statistics: Record<string, AgentStats>;
  engagement_metrics: EngagementMetrics;
  recent_activity: WorkflowActivity[];
  video_details: VideoDetail[];
  last_updated: string;
}
```

### Enums

#### ProcessingStatus
```typescript
enum ProcessingStatus {
  PENDING = "pending",
  IN_PROGRESS = "in_progress", 
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
  SKIPPED = "skipped"
}
```

#### CommentStyle
```typescript
enum CommentStyle {
  ENGAGING = "engaging",
  PROFESSIONAL = "professional", 
  CASUAL = "casual",
  FUNNY = "funny",
  EDUCATIONAL = "educational"
}
```

---

## Agent Workflow Details

### Agent Pipeline
The 6-agent workflow processes videos sequentially:

1. **Channel Parser** (`channel_parser`)
   - Extracts channel information and video list
   - Supports multiple URL formats
   - Handles individual video URLs with channel discovery
   - Fetches video metadata (title, description, views, etc.)

2. **Description Extractor** (`description_extractor`) 
   - Extracts and processes video descriptions
   - Analyzes description metadata
   - Provides content for AI analysis

3. **Content Scraper** (`content_scraper`)
   - Scrapes additional video content
   - Fetches existing comments for context
   - Gathers engagement data

4. **Content Analyzer** (`content_analyzer`)
   - AI-powered analysis of video content
   - Determines content type and themes
   - Assesses engagement potential
   - Prepares data for comment generation

5. **Comment Generator** (`comment_generator`)
   - AI-powered comment generation
   - Multiple comment styles (engaging, professional, etc.)
   - Ensures minimum length requirements (120+ characters)
   - Creates video suggestions
   - Quality validation and filtering

6. **Comment Poster** (`comment_poster`)
   - Posts comments to YouTube (requires OAuth2)
   - Handles rate limiting and retries
   - Tracks posting success/failure
   - Updates engagement metrics

### Agent Status Codes
- `pending` - Agent waiting to execute
- `in_progress` - Agent currently processing
- `completed` - Agent finished successfully
- `failed` - Agent encountered an error
- `skipped` - Agent skipped due to conditions

---

## Error Handling

### HTTP Status Codes

- `200 OK` - Successful request
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Access denied
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Validation error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

### Error Response Format

```json
{
  "detail": "Error description",
  "error_code": "WORKFLOW_NOT_FOUND",
  "timestamp": "2024-01-15T10:30:00Z",
  "path": "/api/v1/workflow/invalid-id/status",
  "request_id": "req_123456789"
}
```

### Common Error Codes

- `WORKFLOW_NOT_FOUND` - Workflow ID not found
- `INVALID_YOUTUBE_URL` - Invalid YouTube URL format
- `OAUTH2_NOT_CONFIGURED` - OAuth2 credentials not set up
- `TELEGRAM_NOT_CONFIGURED` - Telegram bot not configured
- `QUOTA_EXCEEDED` - API quota limit reached
- `VALIDATION_ERROR` - Request validation failed
- `AGENT_TIMEOUT` - Agent processing timeout
- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded
- `INSUFFICIENT_PERMISSIONS` - Insufficient API permissions

### Error Recovery

The system includes automatic error recovery:
- **Retry Logic**: Failed API calls are retried up to 3 times
- **Graceful Degradation**: Agents can continue with partial data
- **Fallback Mechanisms**: Backup comment generation when AI fails
- **State Preservation**: Workflow state is preserved across failures

---

## Rate Limiting

### API Rate Limits

- **YouTube API**: 100 requests per minute, 10,000 per day
- **OpenRouter API**: 60 requests per minute, 1,000 per day
- **Telegram API**: 20 messages per minute
- **General API**: 1,000 requests per hour per IP

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705318200
X-RateLimit-Window: 3600
Retry-After: 60
```

### Rate Limiting Configuration

Rate limits can be configured via environment variables:

```bash
YOUTUBE_REQUESTS_PER_SECOND=1
OPENROUTER_REQUESTS_PER_MINUTE=60
TELEGRAM_MESSAGES_PER_SECOND=1
TELEGRAM_MESSAGES_PER_MINUTE=20
```

---

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 7844

CMD ["python", "startup.py"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  youtube-comment-agent:
    build: .
    ports:
      - "7844:7844"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```

### Environment Configuration

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-your-key-here
YOUTUBE_API_KEY=AIzaSyB-your-youtube-api-key
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret

# Optional
TELEGRAM_BOT_TOKEN=123456789:your-bot-token
TELEGRAM_ALLOWED_USERS=123456789,987654321
PORT=7844
DEBUG=false
ENABLE_COMMENT_POSTING=true

# AI Configuration
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
OPENROUTER_TEMPERATURE=0.7
CHANNEL_PARSER_MAX_VIDEOS=10
MAX_COMMENTS_PER_VIDEO=100
```

### Production Considerations

1. **Security**: Use HTTPS in production
2. **Database**: Configure persistent storage for workflows
3. **Monitoring**: Set up logging and error tracking (Sentry support available)
4. **Scaling**: Consider load balancing for high traffic
5. **Backup**: Regular backups of configuration and data
6. **SSL**: Configure SSL certificates for OAuth2 redirect URLs
7. **Firewall**: Restrict access to necessary ports only

### Health Monitoring

The application includes built-in health monitoring:
- Health check endpoint: `/health`
- Metrics endpoint: `/api/v1/metrics/health`
- WebSocket for real-time monitoring
- Automatic error recovery mechanisms
- Resource usage monitoring

---

## Support & Resources

- **API Version**: 1.0.0
- **Last Updated**: January 2024
- **License**: MIT
- **Support**: Create an issue on GitHub

### Useful Commands

```bash
# Start the application
python startup.py

# Test API health
curl http://localhost:7844/health

# Start a workflow
curl -X POST http://localhost:7844/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/@channelname"}'

# Check configuration
curl http://localhost:7844/api/v1/configuration/status

# View logs
curl http://localhost:7844/api/v1/logs?limit=10
```

---

*This documentation covers all available endpoints and functionality of the YouTube Comment AI Agent API. For additional support or feature requests, please refer to the project repository.* 