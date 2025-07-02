"""
Configuration settings for YouTube Comment Automation Bot
"""

import os
from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import validator, Field
from pathlib import Path
import logging
import requests

# Create logger for this module
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application Configuration
    APP_NAME: str = "youtube-comment-bot"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # FastAPI Configuration
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=7844, env="PORT")
    RELOAD: bool = Field(default=True, env="RELOAD")
    
    # Google Cloud / YouTube API Configuration
    # Either GOOGLE_API_KEY or YOUTUBE_API_KEY is required for YouTube Data API v3
    GOOGLE_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None
    
    # OAuth2 credentials (REQUIRED for comment posting)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_OAUTH2_SCOPES: str = "https://www.googleapis.com/auth/youtube.force-ssl"
    GOOGLE_OAUTH2_REDIRECT_URI: Optional[str] = Field(
        default=None,
        env="GOOGLE_OAUTH2_REDIRECT_URI"
    )
    
    YOUTUBE_MAX_RESULTS: int = 50
    YOUTUBE_QUOTA_LIMIT: int = 10000
    
    # OpenRouter API Configuration
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MAX_TOKENS: int = 2000
    OPENROUTER_TEMPERATURE: float = 0.7
    
    # Agent-specific OpenRouter Model Configuration
    # Content Analyzer Agent (Agent 4)
    CONTENT_ANALYZER_MODEL: Optional[str] = None  # Falls back to OPENROUTER_MODEL
    CONTENT_ANALYZER_TEMPERATURE: float = 0.5
    CONTENT_ANALYZER_MAX_TOKENS: int = 1500
    
    # Comment Generator Agent (Agent 5)
    COMMENT_GENERATOR_MODEL: Optional[str] = None  # Falls back to OPENROUTER_MODEL
    COMMENT_GENERATOR_TEMPERATURE: float = 0.8
    COMMENT_GENERATOR_MAX_TOKENS: int = 200
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_BOT_USERNAME: Optional[str] = None
    TELEGRAM_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_API_ID: Optional[str] = None
    TELEGRAM_API_HASH: Optional[str] = None
    TELEGRAM_ADMIN_USER_ID: Optional[str] = None
    TELEGRAM_ALLOWED_USERS: Optional[str] = None
    
    # LangGraph Configuration
    LANGGRAPH_CHECKPOINT_BACKEND: str = "memory"
    LANGGRAPH_MAX_RETRIES: int = 3
    LANGGRAPH_TIMEOUT: int = 300
    
    # Data Storage Configuration
    DATA_DIRECTORY: str = "./data"
    CHANNELS_DIRECTORY: str = "./data/channels"
    LOGS_DIRECTORY: str = "./logs"
    TEMP_DIRECTORY: str = "./temp"
    JSON_INDENT: int = 2
    JSON_ENSURE_ASCII: bool = False
    
    # Rate Limiting Configuration
    YOUTUBE_QUOTA_PER_DAY: int = 10000
    YOUTUBE_REQUESTS_PER_SECOND: int = 1
    OPENROUTER_REQUESTS_PER_MINUTE: int = 60
    OPENROUTER_REQUESTS_PER_DAY: int = 1000
    TELEGRAM_MESSAGES_PER_SECOND: int = 1
    TELEGRAM_MESSAGES_PER_MINUTE: int = 20
    
    # Agent Configuration
    CHANNEL_PARSER_TIMEOUT: int = 60
    
    # Description Service Configuration (replaces transcript)
    DESCRIPTION_TIMEOUT: int = 60
    DESCRIPTION_RETRY_ATTEMPTS: int = 2
    
    # Content Processing Configuration
    COMMENTS_ORDER: str = "relevance"
    SCRAPER_TIMEOUT: int = 180
    ANALYSIS_TIMEOUT: int = 300
    COMMENT_MAX_LENGTH: int = 500
    COMMENT_MIN_LENGTH: int = 50
    COMMENT_STYLE: str = "engaging"
    COMMENT_POST_DELAY: int = 10
    COMMENT_POST_RETRY_DELAY: int = 5  # Delay between retry attempts
    COMMENT_POST_RETRIES: int = 3
    COMMENT_POST_TIMEOUT: int = 60
    
    # Monitoring & Logging Configuration
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "./logs/app.log"
    LOG_MAX_SIZE: str = "10MB"  # Not used with daily rotation, kept for compatibility
    LOG_BACKUP_COUNT: int = 30  # Keep 30 days of log files
    SENTRY_DSN: Optional[str] = None
    ENABLE_METRICS: bool = False
    METRICS_PORT: int = 9090
    
    # Security Configuration
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_KEY_ENCRYPTION_KEY: Optional[str] = None
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    CORS_ORIGINS: str = "*"
    
    # Feature Flags
    ENABLE_COMMENT_POSTING: bool = False
    ENABLE_ANALYTICS: bool = False
    ENABLE_SCHEDULING: bool = False
    ENABLE_MULTI_USER: bool = False
    ENABLE_WEBHOOKS: bool = False
    
    # Development Configuration
    DEV_SKIP_RATE_LIMITS: bool = False
    DEV_MOCK_APIS: bool = False
    DEV_SAMPLE_DATA: bool = False
    
    # =============================================================================
    # 🛡️ PRODUCTION RELIABILITY SETTINGS
    # =============================================================================
    
    # Health monitoring
    HEALTH_CHECK_INTERVAL: int = 300  # 5 minutes
    ENABLE_AUTO_CLEANUP: bool = True  # Auto cleanup old data
    MAX_WORKFLOW_HISTORY: int = 100  # Keep last 100 workflows
    
    # Process monitoring
    ENABLE_PROCESS_MONITORING: bool = True  # Monitor system resources
    MAX_MEMORY_USAGE_MB: int = 1024  # 1GB limit
    AUTO_RESTART_ON_HIGH_MEMORY: bool = False  # Auto restart if memory high
    
    # Connection resilience
    API_RETRY_ATTEMPTS: int = 3  # Retry failed API calls 3 times
    API_RETRY_DELAY: int = 5  # 5 seconds between retries
    CONNECTION_TIMEOUT: int = 30  # 30 second connection timeout
    
    # Service auto-recovery
    ENABLE_AUTO_RECOVERY: bool = True  # Auto recover from failures
    MAX_RECOVERY_ATTEMPTS: int = 3  # Maximum recovery attempts
    RECOVERY_DELAY: int = 60  # 1 minute between recovery attempts
    
    @validator('ALLOWED_HOSTS', pre=True)
    def parse_allowed_hosts(cls, v):
        if v is None or v == "":
            return "localhost,127.0.0.1"
        return v
    
    @validator('CORS_ORIGINS', pre=True)
    def parse_cors_origins(cls, v):
        if v is None or v == "":
            return "*"
        return v
    
    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'LOG_LEVEL must be one of {valid_levels}')
        return v.upper()
    
    @validator('ENVIRONMENT')
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production']
        if v.lower() not in valid_envs:
            raise ValueError(f'ENVIRONMENT must be one of {valid_envs}')
        return v.lower()
    
    def create_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [
            self.DATA_DIRECTORY,
            self.CHANNELS_DIRECTORY,
            self.LOGS_DIRECTORY,
            self.TEMP_DIRECTORY
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def get_allowed_users(self) -> List[int]:
        """Get allowed Telegram user IDs as a list of integers"""
        if not self.TELEGRAM_ALLOWED_USERS:
            return []
        
        try:
            return [int(user_id.strip()) for user_id in self.TELEGRAM_ALLOWED_USERS.split(',')]
        except ValueError:
            return []
    
    def get_content_analyzer_model(self) -> str:
        """Get the model for content analysis agent"""
        return self.CONTENT_ANALYZER_MODEL or self.OPENROUTER_MODEL
    
    def get_comment_generator_model(self) -> str:
        """Get the model for comment generation agent"""
        return self.COMMENT_GENERATOR_MODEL or self.OPENROUTER_MODEL
    
    def get_youtube_api_key(self) -> Optional[str]:
        """Get YouTube API key (either GOOGLE_API_KEY or YOUTUBE_API_KEY)"""
        return self.GOOGLE_API_KEY or self.YOUTUBE_API_KEY
    
    def get_oauth2_scopes(self) -> List[str]:
        """Get OAuth2 scopes as a list"""
        return [scope.strip() for scope in self.GOOGLE_OAUTH2_SCOPES.split(',')]
    
    def has_oauth2_credentials(self) -> bool:
        """Check if OAuth2 credentials are configured"""
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)
    
    def can_post_comments(self) -> bool:
        """Check if comment posting is enabled and configured"""
        # Add detailed debugging
        enable_posting = self.ENABLE_COMMENT_POSTING
        has_oauth = self.has_oauth2_credentials()
        has_api_key = self.get_youtube_api_key() is not None
        
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 Comment posting check:")
        logger.info(f"   - ENABLE_COMMENT_POSTING: {enable_posting}")
        logger.info(f"   - has_oauth2_credentials(): {has_oauth}")
        logger.info(f"   - get_youtube_api_key() is not None: {has_api_key}")
        logger.info(f"   - Final result: {enable_posting and has_oauth and has_api_key}")
        
        return (
            enable_posting and
            has_oauth and
            has_api_key
        )
    
    def get_allowed_hosts(self) -> List[str]:
        """Get allowed hosts as a list"""
        return [host.strip() for host in self.ALLOWED_HOSTS.split(',')]
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins as a list"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(',')]
    
    def _read_env_value(self, key: str, default_value: str) -> str:
        """Read a value directly from .env file to ensure fresh data."""
        env_file = Path(".env")
        if not env_file.exists():
            return default_value
        
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        env_key, env_value = line.split('=', 1)
                        if env_key == key:
                            return env_value.strip('"\'')
        except Exception:
            pass
        return default_value
    
    @property
    def live_openrouter_model(self) -> str:
        """Get OpenRouter model directly from .env file."""
        env_value = self._read_env_value("OPENROUTER_MODEL", "")
        return env_value or "google/gemini-2.0-flash-001"  # Fallback if .env missing
    
    @property 
    def live_channel_parser_max_videos(self) -> int:
        """Get max videos directly from .env file."""
        env_value = self._read_env_value("CHANNEL_PARSER_MAX_VIDEOS", "")
        try:
            return int(env_value) if env_value else 3  # Fallback if .env missing
        except ValueError:
            return 3
    
    @property
    def live_max_comments_per_video(self) -> int:
        """Get max comments directly from .env file."""
        env_value = self._read_env_value("MAX_COMMENTS_PER_VIDEO", "")
        try:
            return int(env_value) if env_value else 100  # Fallback if .env missing
        except ValueError:
            return 100
    
    @property
    def live_openrouter_temperature(self) -> float:
        """Get OpenRouter temperature directly from .env file."""
        env_value = self._read_env_value("OPENROUTER_TEMPERATURE", "")
        try:
            return float(env_value) if env_value else 0.7  # Fallback if .env missing
        except ValueError:
            return 0.7

    # Properties for the removed fields that read directly from .env
    @property
    def OPENROUTER_MODEL(self) -> str:
        """Get OpenRouter model directly from .env file."""
        return self.live_openrouter_model
    
    @property
    def CHANNEL_PARSER_MAX_VIDEOS(self) -> int:
        """Get max videos directly from .env file."""
        return self.live_channel_parser_max_videos
        
    @property  
    def MAX_COMMENTS_PER_VIDEO(self) -> int:
        """Get max comments directly from .env file."""
        return self.live_max_comments_per_video
    
    def get_oauth2_redirect_uri(self, host: str = None, port: int = None) -> str:
        """Get OAuth2 redirect URI dynamically based on current host and port"""
        # If explicitly set in .env file, use that value
        if self.GOOGLE_OAUTH2_REDIRECT_URI:
            logger.info(f"🔗 Using OAuth2 redirect URI from .env: {self.GOOGLE_OAUTH2_REDIRECT_URI}")
            return self.GOOGLE_OAUTH2_REDIRECT_URI
        
        # Auto-detect host if not provided
        if host is None:
            host = self._detect_host()
        
        # Use the port from environment, current PORT setting, or default
        actual_port = port or self.PORT or 7844
        dynamic_uri = f"http://{host}:{actual_port}/oauth2callback"
        
        logger.info(f"🔗 Auto-generated OAuth2 redirect URI: {dynamic_uri}")
        return dynamic_uri
    
    def _detect_host(self) -> str:
        """Detect the appropriate host for OAuth2 redirect URI"""
        import socket
        import requests
        
        # Try to detect if we're running on a VPS/cloud instance
        try:
            # Method 1: Check if we can get external IP from metadata services
            try:
                # AWS/GCP metadata service
                response = requests.get('http://169.254.169.254/latest/meta-data/public-ipv4', timeout=2)
                if response.status_code == 200:
                    external_ip = response.text.strip()
                    logger.info(f"🌐 Detected AWS/GCP external IP: {external_ip}")
                    return external_ip
            except:
                pass
            
            # Method 2: Try to get external IP from a public service
            try:
                response = requests.get('https://api.ipify.org', timeout=5)
                if response.status_code == 200:
                    external_ip = response.text.strip()
                    # Only use external IP if it's not a private IP
                    if not any(external_ip.startswith(prefix) for prefix in ['10.', '172.', '192.168.', '127.']):
                        logger.info(f"🌐 Detected external IP: {external_ip}")
                        return external_ip
            except:
                pass
            
            # Method 3: Check environment variables commonly set in VPS deployments
            import os
            vps_host = os.getenv('VPS_HOST') or os.getenv('SERVER_HOST') or os.getenv('PUBLIC_DOMAIN') or os.getenv('DOMAIN_NAME')
            if vps_host:
                logger.info(f"🌐 Using domain from environment: {vps_host}")
                return vps_host
            
            # Method 4: Try to get the machine's hostname if it's not localhost
            hostname = socket.gethostname()
            if hostname and hostname != 'localhost' and not hostname.startswith('127.'):
                # Try to resolve hostname to IP
                try:
                    host_ip = socket.gethostbyname(hostname)
                    if not host_ip.startswith('127.'):
                        logger.info(f"🌐 Using hostname-resolved IP: {host_ip}")
                        return host_ip
                except:
                    pass
        
        except Exception as e:
            logger.warning(f"Failed to detect host: {e}")
        
        # Fallback to localhost for development
        logger.info("🌐 Fallback to localhost for development")
        return "localhost"
    
    def check_env_file_status(self) -> dict:
        """Check the status of .env file and key settings"""
        import os
        from pathlib import Path
        
        env_file = Path(".env")
        logger = logging.getLogger(__name__)
        
        status = {
            "env_file_exists": env_file.exists(),
            "env_file_path": str(env_file.absolute()),
            "working_directory": os.getcwd(),
            "enable_comment_posting_env": os.getenv("ENABLE_COMMENT_POSTING"),
            "enable_comment_posting_setting": self.ENABLE_COMMENT_POSTING,
        }
        
        logger.info(f"🔍 Environment file status:")
        logger.info(f"   - .env file exists: {status['env_file_exists']}")
        logger.info(f"   - .env file path: {status['env_file_path']}")
        logger.info(f"   - Working directory: {status['working_directory']}")
        logger.info(f"   - ENABLE_COMMENT_POSTING (env var): {status['enable_comment_posting_env']}")
        logger.info(f"   - ENABLE_COMMENT_POSTING (setting): {status['enable_comment_posting_setting']}")
        
        if env_file.exists():
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "ENABLE_COMMENT_POSTING" in content:
                        logger.info(f"   - Found ENABLE_COMMENT_POSTING in .env file")
                    else:
                        logger.warning(f"   - ENABLE_COMMENT_POSTING NOT found in .env file")
            except Exception as e:
                logger.error(f"   - Error reading .env file: {e}")
        else:
            logger.warning(f"   - .env file does not exist! Using default settings.")
            
        return status
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env that don't have class field definitions


# Global settings instance
_settings_instance = None

def get_settings() -> Settings:
    """Get the settings instance, creating it if it doesn't exist."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
        _settings_instance.create_directories()
    return _settings_instance

def reload_settings() -> Settings:
    """Force reload the settings from .env file."""
    global _settings_instance
    _settings_instance = Settings()
    _settings_instance.create_directories()
    return _settings_instance

# Create initial settings instance for backward compatibility
settings = get_settings() 
