"""
File handling utilities for YouTube Comment Automation Bot
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
import aiofiles
import aiofiles.os
from datetime import datetime
import tempfile
import shutil
import time
import uuid

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

def ensure_env_file_exists() -> bool:
    """
    Ensure .env file exists. If not, copy from example.env.
    
    Returns:
        bool: True if .env exists or was successfully created, False otherwise
    """
    env_path = Path(".env")
    example_env_path = Path("example.env")
    
    # Check if .env already exists
    if env_path.exists():
        logger.info("✅ .env file found")
        return True
    
    # Check if example.env exists
    if not example_env_path.exists():
        logger.error("❌ Neither .env nor example.env found. Cannot create environment file.")
        return False
    
    try:
        # Copy example.env to .env
        shutil.copy2(example_env_path, env_path)
        logger.info("✅ Created .env file from example.env")
        logger.info("⚠️  Please configure your API keys in the .env file or through the settings page")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create .env file: {e}")
        return False

def validate_env_credentials() -> Dict[str, bool]:
    """
    Validate if environment credentials are properly configured.
    
    Returns:
        Dict with validation status for each service
    """
    from ..config import get_settings
    
    try:
        settings = get_settings()
        
        # Helper function to check if value is valid (not empty or placeholder)
        def is_valid_credential(value: str) -> bool:
            if not value:
                return False
            
            value_lower = value.lower()
            
            # Check for common placeholder patterns (using substring matching)
            placeholder_patterns = [
                "here", "your_key", "your_token", "your_api", "your_secret", 
                "your_id", "your_hash", "placeholder", "not_configured",
                "replace_with", "add_your", "example", "test_key",
                "demo_", "sample_", "_here", "api_key_here", "token_here"
            ]
            
            # If any placeholder pattern is found in the value, it's invalid
            for pattern in placeholder_patterns:
                if pattern in value_lower:
                    return False
            
            # Check minimum length for real API keys
            if len(value) < 15:
                return False
                
            return True
        
        return {
            "telegram_configured": is_valid_credential(settings.TELEGRAM_BOT_TOKEN or ""),
            "openrouter_configured": is_valid_credential(settings.OPENROUTER_API_KEY or ""),
            "youtube_oauth_configured": (
                is_valid_credential(settings.GOOGLE_CLIENT_ID or "") and 
                is_valid_credential(settings.GOOGLE_CLIENT_SECRET or "")
            ),
            "youtube_api_configured": is_valid_credential(settings.GOOGLE_API_KEY or settings.YOUTUBE_API_KEY or "")
        }
    except Exception as e:
        logger.error(f"Error validating environment credentials: {e}")
        return {
            "telegram_configured": False,
            "openrouter_configured": False,
            "youtube_oauth_configured": False,
            "youtube_api_configured": False
        }

class FileHandler:
    """Handles file operations for the bot"""
    
    @staticmethod
    async def ensure_directory(directory_path: str) -> None:
        """
        Ensure directory exists, create if it doesn't
        
        Args:
            directory_path: Path to directory
        """
        try:
            await aiofiles.os.makedirs(directory_path, exist_ok=True)
            logger.info(f"Directory ensured: {directory_path}")
        except Exception as e:
            logger.error(f"Failed to create directory {directory_path}: {e}")
            raise
    
    @staticmethod
    async def save_json(data: Dict[str, Any], file_path: str) -> bool:
        """
        Save data to JSON file
        
        Args:
            data: Data to save
            file_path: Path to JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            directory = os.path.dirname(file_path)
            if directory:
                await FileHandler.ensure_directory(directory)
            
            # Add metadata
            data["_metadata"] = {
                "last_updated": datetime.utcnow().isoformat(),
                "version": settings.APP_VERSION,
                "bot_name": settings.APP_NAME
            }
            
            # Save file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(
                    data,
                    indent=settings.JSON_INDENT,
                    ensure_ascii=settings.JSON_ENSURE_ASCII,
                    default=str
                ))
            
            logger.info(f"JSON data saved to: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save JSON to {file_path}: {e}")
            return False
    
    @staticmethod
    async def load_json(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Load data from JSON file
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Loaded data or None if failed
        """
        try:
            if not await aiofiles.os.path.exists(file_path):
                logger.warning(f"JSON file not found: {file_path}")
                return None
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
            
            logger.info(f"JSON data loaded from: {file_path}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load JSON from {file_path}: {e}")
            return None
    
    @staticmethod
    async def update_json(file_path: str, updates: Dict[str, Any]) -> bool:
        """
        Update existing JSON file with new data
        
        Args:
            file_path: Path to JSON file
            updates: Data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load existing data
            existing_data = await FileHandler.load_json(file_path) or {}
            
            # Merge updates
            existing_data.update(updates)
            
            # Save updated data
            return await FileHandler.save_json(existing_data, file_path)
            
        except Exception as e:
            logger.error(f"Failed to update JSON file {file_path}: {e}")
            return False
    
    @staticmethod
    async def create_channel_directory(channel_id: str, channel_name: Optional[str] = None) -> str:
        """
        Create directory for channel data using just the channel name for clean structure.
        Handles duplicate names by adding a small channel ID suffix when needed.
        
        Args:
            channel_id: YouTube channel ID
            channel_name: Optional channel name for better directory naming
            
        Returns:
            Path to channel directory
        """
        if channel_name and channel_name.strip():
            # Sanitize channel name for file system
            safe_name = FileHandler._sanitize_filename(channel_name.strip())
            
            # Check if directory already exists with different channel ID
            base_dir = os.path.join(settings.CHANNELS_DIRECTORY, safe_name)
            
            if os.path.exists(base_dir):
                # Check if it's the same channel or a different one
                existing_data_file = os.path.join(base_dir, "videos_data.json")
                if os.path.exists(existing_data_file):
                    try:
                        with open(existing_data_file, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                            existing_channel_id = existing_data.get("channel_id", "")
                            
                            # If different channel ID, add suffix to avoid conflict
                            if existing_channel_id and existing_channel_id != channel_id:
                                # Add short suffix from channel ID
                                suffix = channel_id[-6:] if len(channel_id) >= 6 else channel_id
                                directory_name = f"{safe_name}-{suffix}"
                            else:
                                # Same channel, use existing directory
                                directory_name = safe_name
                    except:
                        # If we can't read the file, use suffix to be safe
                        suffix = channel_id[-6:] if len(channel_id) >= 6 else channel_id
                        directory_name = f"{safe_name}-{suffix}"
                else:
                    # Directory exists but no data file, use it
                    directory_name = safe_name
            else:
                # No conflict, use clean name
                directory_name = safe_name
        else:
            # Fallback to just channel ID
            directory_name = channel_id
        
        channel_dir = os.path.join(settings.CHANNELS_DIRECTORY, directory_name)
        await FileHandler.ensure_directory(channel_dir)
        return channel_dir
    
    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Sanitize filename for file system compatibility.
        
        Args:
            filename: Raw filename
            
        Returns:
            Sanitized filename safe for file systems
        """
        import re
        
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        filename = filename.strip('-')
        
        # Limit length
        if len(filename) > 50:
            filename = filename[:50].rstrip('-')
        
        return filename or "UnknownChannel"
    
    @staticmethod
    def get_channel_data_file(channel_id: str, channel_name: Optional[str] = None) -> str:
        """
        Get path to channel data JSON file, with conflict resolution for duplicate names.
        
        Args:
            channel_id: YouTube channel ID
            channel_name: Optional channel name for directory lookup
            
        Returns:
            Path to channel data file
        """
        if channel_name and channel_name.strip():
            safe_name = FileHandler._sanitize_filename(channel_name.strip())
            
            # Check for existing directory conflicts
            base_dir = os.path.join(settings.CHANNELS_DIRECTORY, safe_name)
            
            if os.path.exists(base_dir):
                # Check if it's the same channel or a different one
                existing_data_file = os.path.join(base_dir, "videos_data.json")
                if os.path.exists(existing_data_file):
                    try:
                        with open(existing_data_file, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                            existing_channel_id = existing_data.get("channel_id", "")
                            
                            # If different channel ID, add suffix to avoid conflict
                            if existing_channel_id and existing_channel_id != channel_id:
                                suffix = channel_id[-6:] if len(channel_id) >= 6 else channel_id
                                directory_name = f"{safe_name}-{suffix}"
                            else:
                                directory_name = safe_name
                    except:
                        # If we can't read the file, use suffix to be safe
                        suffix = channel_id[-6:] if len(channel_id) >= 6 else channel_id
                        directory_name = f"{safe_name}-{suffix}"
                else:
                    directory_name = safe_name
            else:
                directory_name = safe_name
        else:
            directory_name = channel_id
            
        return os.path.join(settings.CHANNELS_DIRECTORY, directory_name, "videos_data.json")
    
    @staticmethod
    async def initialize_channel_data(channel_id: str, channel_name: str) -> Dict[str, Any]:
        """
        Initialize channel data structure
        
        Args:
            channel_id: YouTube channel ID
            channel_name: Channel name
            
        Returns:
            Initial channel data structure
        """
        initial_data = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "processed_at": datetime.utcnow().isoformat(),
            "status": "initialized",
            "videos": [],
            "statistics": {
                "total_videos": 0,
                "processed_videos": 0,
                "failed_videos": 0,
                "comments_posted": 0
            }
        }
        
        # Create channel directory and save initial data
        await FileHandler.create_channel_directory(channel_id, channel_name)
        file_path = FileHandler.get_channel_data_file(channel_id, channel_name)
        await FileHandler.save_json(initial_data, file_path)
        
        return initial_data
    
    @staticmethod
    async def cleanup_temp_files(max_age_hours: int = 24) -> None:
        """
        Clean up temporary files older than specified age
        
        Args:
            max_age_hours: Maximum age of files to keep
        """
        try:
            temp_dir = Path(settings.TEMP_DIRECTORY)
            if not temp_dir.exists():
                return
            
            cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
            
            for file_path in temp_dir.iterdir():
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    await aiofiles.os.remove(str(file_path))
                    logger.info(f"Cleaned up temp file: {file_path}")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {e}")
    
    @staticmethod
    def create_temp_file(prefix: str = "workflow_", suffix: str = ".json") -> str:
        """
        Create a temporary file in the temp directory.
        
        Args:
            prefix: File prefix
            suffix: File suffix
            
        Returns:
            Path to the temporary file
        """
        try:
            temp_dir = Path("./temp")
            temp_dir.mkdir(exist_ok=True)
            
            # Create temporary file
            temp_file = temp_dir / f"{prefix}{int(time.time())}{suffix}"
            temp_file.touch()
            
            logger.info(f"Created temporary file: {temp_file}")
            return str(temp_file)
            
        except Exception as e:
            logger.error(f"Error creating temporary file: {e}")
            raise
    
    @staticmethod
    async def save_temp_workflow_state(workflow_id: str, state: Dict[str, Any]) -> str:
        """
        Save workflow state to temporary file.
        
        Args:
            workflow_id: Workflow identifier
            state: Workflow state data
            
        Returns:
            Path to the temporary state file
        """
        try:
            temp_file = FileHandler.create_temp_file(
                prefix=f"workflow_{workflow_id}_", 
                suffix=".json"
            )
            
            # Fix: Correct parameter order - data first, then file_path
            await FileHandler.save_json({
                "workflow_id": workflow_id,
                "timestamp": datetime.now().isoformat(),
                "state": state
            }, temp_file)
            
            logger.debug(f"Saved workflow state to temp file: {temp_file}")
            return temp_file
            
        except Exception as e:
            logger.error(f"Error saving temp workflow state: {e}")
            raise
    
    @staticmethod
    def cleanup_temp_files(older_than_hours: int = 24) -> int:
        """
        Clean up temporary files older than specified hours.
        
        Args:
            older_than_hours: Delete files older than this many hours
            
        Returns:
            Number of files deleted
        """
        try:
            temp_dir = Path("./temp")
            if not temp_dir.exists():
                return 0
            
            cutoff_time = time.time() - (older_than_hours * 3600)
            deleted_count = 0
            
            for temp_file in temp_dir.glob("*"):
                if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_time:
                    temp_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old temp file: {temp_file}")
            
            logger.info(f"Cleaned up {deleted_count} temporary files")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
            return 0
    
    @staticmethod
    async def save_multi_channel_data_individually(
        workflow_state: Dict[str, Any], 
        channels_data: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Save multi-channel workflow data as individual channel directories.
        
        This method takes a multi-channel workflow state and splits it into
        individual channel directories for better organization and management.
        
        Args:
            workflow_state: Complete workflow state
            channels_data: List of individual channel data
            
        Returns:
            List of saved file paths
        """
        try:
            saved_files = []
            
            # Process each channel individually
            for channel_data in channels_data:
                channel_id = channel_data.get("channel_id", "")
                channel_name = channel_data.get("channel_name", "Unknown")
                
                if not channel_id:
                    logger.warning(f"Skipping channel with missing ID: {channel_name}")
                    continue
                
                # Create individual channel directory
                await FileHandler.create_channel_directory(channel_id, channel_name)
                
                # Extract videos belonging to this channel
                channel_videos = []
                for video in workflow_state.get("videos", []):
                    # Check if video belongs to this channel
                    video_channel_id = video.get("channel_id")
                    if not video_channel_id:
                        # For older data, try to match by discovery method or URL
                        video_url = video.get("url", "")
                        if channel_id in video_url or any(
                            keyword in video_url for keyword in [
                                channel_data.get("channel_handle", "").replace("@", ""),
                                channel_name.lower().replace(" ", "")
                            ]
                        ):
                            video["channel_id"] = channel_id  # Update video with channel ID
                            channel_videos.append(video)
                    elif video_channel_id == channel_id:
                        channel_videos.append(video)
                
                # Create individual channel data structure
                individual_channel_data = {
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "processed_at": datetime.now().isoformat(),
                    "status": "processed_individually",
                    "videos": channel_videos,
                    "statistics": {
                        "total_videos": len(channel_videos),
                        "processed_videos": sum(1 for v in channel_videos if v.get("content_scraped", False)),
                        "failed_videos": sum(1 for v in channel_videos if v.get("status") == "failed"),
                        "comments_posted": sum(1 for v in channel_videos if v.get("comment_posted", False))
                    },
                    "channel_info": channel_data.get("channel_info", {}),
                    "workflow_metadata": {
                        "original_workflow_id": workflow_state.get("workflow_id"),
                        "original_multi_channel_name": workflow_state.get("channel_name"),
                        "separated_at": datetime.now().isoformat(),
                        "user_id": workflow_state.get("user_id"),
                        "chat_id": workflow_state.get("chat_id")
                    }
                }
                
                # Save individual channel file
                channel_file_path = FileHandler.get_channel_data_file(channel_id, channel_name)
                success = await FileHandler.save_json(individual_channel_data, channel_file_path)
                
                if success:
                    saved_files.append(channel_file_path)
                    logger.info(f"💾 Saved individual channel data: {channel_name} ({len(channel_videos)} videos)")
                else:
                    logger.error(f"❌ Failed to save channel data for: {channel_name}")
            
            logger.info(f"✅ Successfully separated multi-channel data into {len(saved_files)} individual files")
            return saved_files
            
        except Exception as e:
            logger.error(f"Failed to save multi-channel data individually: {e}")
            return []
    
    @staticmethod
    async def cleanup_multi_channel_file(multi_channel_directory: str) -> bool:
        """
        Clean up the old multi-channel directory after successful separation.
        
        Args:
            multi_channel_directory: Path to multi-channel directory
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            import shutil
            from pathlib import Path
            
            multi_dir_path = Path(multi_channel_directory)
            if multi_dir_path.exists():
                # Create backup before deletion
                backup_path = multi_dir_path.parent / f"{multi_dir_path.name}_backup_{int(time.time())}"
                shutil.move(str(multi_dir_path), str(backup_path))
                logger.info(f"🗂️ Multi-channel directory moved to backup: {backup_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cleanup multi-channel directory: {e}")
            return False


# Create global file handler instance
file_handler = FileHandler()

# Add synchronous wrapper functions for compatibility
def ensure_directory(directory_path: str) -> None:
    """Sync wrapper for ensure_directory"""
    import asyncio
    import os
    try:
        os.makedirs(directory_path, exist_ok=True)
        logger.info(f"Directory ensured: {directory_path}")
    except Exception as e:
        logger.error(f"Failed to create directory {directory_path}: {e}")
        raise

def save_json(data: Dict[str, Any], file_path: str) -> bool:
    """Sync wrapper for save_json"""
    try:
        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory:
            ensure_directory(directory)
        
        # Add metadata
        data["_metadata"] = {
            "last_updated": datetime.utcnow().isoformat(),
            "version": settings.APP_VERSION,
            "bot_name": settings.APP_NAME
        }
        
        # Save file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(
                data,
                indent=settings.JSON_INDENT,
                ensure_ascii=settings.JSON_ENSURE_ASCII,
                default=str
            ))
        
        logger.info(f"JSON data saved to: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save JSON to {data}: {e}")
        return False

def load_json(file_path: str) -> Optional[Dict[str, Any]]:
    """Sync wrapper for load_json"""
    try:
        if not os.path.exists(file_path):
            logger.warning(f"JSON file not found: {file_path}")
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)
        
        logger.info(f"JSON data loaded from: {file_path}")
        return data
        
    except Exception as e:
        logger.error(f"Failed to load JSON from {file_path}: {e}")
        return None 