# 🤖 YouTube Comment AI Agent - Docker Image

<div align="center">

<img src="https://raw.githubusercontent.com/Tiz20lion/youtube-comment-AI-agent/master/file_00000000c8c46243b2a8cd8d82e35807.png" alt="Tiz Lion AI Logo" width="150">

**AI-Powered YouTube Comment Automation**

[![Docker Pulls](https://img.shields.io/docker/pulls/tiz20lion/youtube-comment-ai-agent?style=flat&logo=docker&color=2496ED)](https://hub.docker.com/r/tiz20lion/youtube-comment-ai-agent)
[![Docker Image Size](https://img.shields.io/docker/image-size/tiz20lion/youtube-comment-ai-agent/latest)](https://hub.docker.com/r/tiz20lion/youtube-comment-ai-agent)

[📂 **GitHub Repository**](https://github.com/Tiz20lion/youtube-comment-AI-agent) | [🎥 **Watch Demo**](https://www.loom.com/share/ebc1e5a6011f440f838176c306b381f9?sid=3b81e1e4-0585-4dc6-9f30-25014948885e)

</div>

## 🚀 Quick Start

### Pull the Image
```bash
docker pull tiz20lion/youtube-comment-ai-agent:latest
```

### Run with Interactive Setup
```bash
docker run -it --rm -p 7844:7844 --env-file .env tiz20lion/youtube-comment-ai-agent
```

### Run in Background (Production)
```bash
docker run -d -p 7844:7844 --env-file .env --name youtube-ai tiz20lion/youtube-comment-ai-agent
```

## 🔧 Environment Variables

Create a `.env` file with these required variables:

```bash
# YouTube API
GOOGLE_API_KEY=your_youtube_api_key
GOOGLE_CLIENT_ID=your_oauth2_client_id
GOOGLE_CLIENT_SECRET=your_oauth2_client_secret

# OpenRouter AI
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=google/gemini-2.0-flash-001

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_USERS=your_user_id

# Features
ENABLE_COMMENT_POSTING=true
```

## 🐳 Docker Configuration

### Startup Command
The container uses the uvicorn ASGI server:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 7844
```

### Ports
- **7844**: FastAPI web server (internal port)

### Volumes (Optional)
```bash
# Mount data directory for persistence
-v /host/data:/app/data

# Mount logs directory
-v /host/logs:/app/logs

# Mount custom config
-v /host/config:/app/config
```

### Complete Example
```bash
docker run -d \
  --name youtube-ai-agent \
  -p 7844:7844 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  tiz20lion/youtube-comment-ai-agent:latest
```

## ⚙️ Usage

1. **Start the container** with your `.env` file
2. **Open Telegram** and find your bot
3. **Send `/start`** to begin
4. **Send YouTube channel URL** to analyze
5. **Approve/reject** generated comments

## 🏷️ Available Tags

- `latest` - Latest stable release
- `v1.0` - Specific version release
- `develop` - Development builds (unstable)

## 📋 What's Included

- **6-Agent AI Pipeline** for content analysis
- **FastAPI REST API** server
- **LangGraph orchestration** engine
- **Telegram bot** integration
- **Interactive setup** wizard
- **OAuth2 authentication** system

## 🔗 Links & Resources

- **📚 Full Documentation**: [GitHub Repository](https://github.com/Tiz20lion/youtube-comment-AI-agent)
- **🎥 Video Demo**: [Watch on Loom](https://www.loom.com/share/ebc1e5a6011f440f838176c306b381f9?sid=3b81e1e4-0585-4dc6-9f30-25014948885e)
- **🛠 Issues & Support**: [GitHub Issues](https://github.com/Tiz20lion/youtube-comment-AI-agent/issues)
- **📺 YouTube Channel**: [@TizLionAI](https://www.youtube.com/@TizLionAI)

## 🗂️ Architecture

Built with **FastAPI**, **LangGraph**, **OpenRouter AI**, and **Python-Telegram-Bot** for enterprise-grade YouTube comment automation.

---

<div align="center">

**Developed by Tiz Lion AI** 🦁

⭐ **Star the repo if this helps you!** ⭐

</div> 
