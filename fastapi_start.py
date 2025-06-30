#!/usr/bin/env python3
"""
FastAPI Startup Script for YouTube Comment AI Agent
Launches the application using uvicorn with proper configuration
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Launch the FastAPI application with uvicorn"""
    print("🚀 Starting YouTube Comment AI Agent with FastAPI...")
    
    # Set environment variables for optimal performance
    os.environ.setdefault("PYTHONPATH", str(project_root))
    
    # Configure uvicorn
    config = {
        "app": "app.main:app",
        "host": "127.0.0.1",
        "port": 7844,
        "reload": False,  # Set to True for development
        "log_level": "info",
        "access_log": True,
        "use_colors": True,
        "server_header": False,
        "date_header": False
    }
    
    print(f"🌐 Server will be available at: http://127.0.0.1:7844")
    print(f"⚙️  Settings page: http://127.0.0.1:7844/settings")
    print(f"📊 Dashboard: http://127.0.0.1:7844/dashboard")
    print("🔥 Press Ctrl+C to stop the server")
    print("-" * 60)
    
    # Launch the server
    uvicorn.run(**config)

if __name__ == "__main__":
    main() 