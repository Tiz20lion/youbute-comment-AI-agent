"""
File handling utilities for YouTube Comment Automation Bot
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import aiofiles
import aiofiles.os
from datetime import datetime
import tempfile
import shutil
import time

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


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
        Create directory for channel data using proper channel name if available
        
        Args:
            channel_id: YouTube channel ID
            channel_name: Optional channel name for better directory naming
            
        Returns:
            Path to channel directory
        """
        if channel_name and channel_name.strip():
            # Sanitize channel name for file system
            safe_name = FileHandler._sanitize_filename(channel_name.strip())
            # Use format: "ChannelName_CHANNELID" for uniqueness and readability
            directory_name = f"{safe_name}_{channel_id}"
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
        Get path to channel data JSON file
        
        Args:
            channel_id: YouTube channel ID
            channel_name: Optional channel name for directory lookup
            
        Returns:
            Path to channel data file
        """
        if channel_name and channel_name.strip():
            safe_name = FileHandler._sanitize_filename(channel_name.strip())
            directory_name = f"{safe_name}_{channel_id}"
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