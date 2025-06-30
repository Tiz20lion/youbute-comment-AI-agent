#!/usr/bin/env python3
"""
YouTube OAuth2 Setup Script

This script helps you set up OAuth2 authentication for YouTube comment posting.
Run this script to authenticate your bot for posting comments to YouTube.

Prerequisites:
1. Create a Google Cloud Project
2. Enable YouTube Data API v3
3. Create OAuth2 credentials (client ID and secret)
4. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file

Usage:
    python oauth2_setup.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def check_prerequisites():
    """Check if all prerequisites are met."""
    print("🔍 Checking prerequisites...")
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found. Please copy example.env to .env and configure it.")
        return False
    
    # Check OAuth2 credentials
    if not settings.has_oauth2_credentials():
        print("❌ OAuth2 credentials not configured.")
        print("   Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file.")
        print("   Get these from Google Cloud Console > APIs & Services > Credentials")
        return False
    
    # Check API key
    if not settings.get_youtube_api_key():
        print("❌ YouTube API key not configured.")
        print("   Please set GOOGLE_API_KEY or YOUTUBE_API_KEY in your .env file.")
        return False
    
    print("✅ All prerequisites met!")
    return True


def print_oauth2_instructions():
    """Print OAuth2 setup instructions."""
    print("\n" + "="*60)
    print("📋 OAUTH2 SETUP INSTRUCTIONS")
    print("="*60)
    print()
    print("To enable comment posting, you need OAuth2 authentication.")
    print("Follow these steps:")
    print()
    print("1. Go to Google Cloud Console:")
    print("   https://console.cloud.google.com/")
    print()
    print("2. Create a new project or select existing one")
    print()
    print("3. Enable YouTube Data API v3:")
    print("   - Go to APIs & Services > Library")
    print("   - Search for 'YouTube Data API v3'")
    print("   - Click 'Enable'")
    print()
    print("4. Create OAuth2 credentials:")
    print("   - Go to APIs & Services > Credentials")
    print("   - Click 'Create Credentials' > 'OAuth 2.0 Client IDs'")
    print("   - Choose 'Web application'")
    print("   - Add authorized redirect URI:")
    print(f"     {settings.GOOGLE_OAUTH2_REDIRECT_URI}")
    print("   - Download the JSON file")
    print()
    print("5. Update your .env file:")
    print("   - Set GOOGLE_CLIENT_ID=your_client_id")
    print("   - Set GOOGLE_CLIENT_SECRET=your_client_secret")
    print()
    print("6. Run this script again to authenticate")
    print()


async def run_oauth2_flow():
    """Run the OAuth2 authentication flow."""
    try:
        from app.services.youtube_service import YouTubeService
        
        print("🔍 Starting OAuth2 authentication flow...")
        
        # Initialize YouTube service
        youtube_service = YouTubeService()
        
        # Generate authorization URL
        auth_url = youtube_service.get_oauth2_authorization_url()
        if not auth_url:
            print("❌ Failed to generate authorization URL")
            return False
        
        print("\n" + "="*60)
        print("🌐 AUTHORIZATION REQUIRED")
        print("="*60)
        print()
        print("1. Open this URL in your browser:")
        print(f"   {auth_url}")
        print()
        print("2. Sign in with your Google account")
        print("3. Grant permission to access YouTube")
        print("4. Copy the full redirect URL from your browser")
        print("   (It will look like: http://localhost:7844/oauth2callback?code=...)")
        print()
        
        # Get authorization response from user
        while True:
            response_url = input("Paste the full redirect URL here: ").strip()
            if response_url.startswith(settings.GOOGLE_OAUTH2_REDIRECT_URI):
                break
            print("❌ Invalid URL. Please paste the full redirect URL starting with:")
            print(f"   {settings.GOOGLE_OAUTH2_REDIRECT_URI}")
        
        # Complete authorization
        success = youtube_service.complete_oauth2_authorization(response_url)
        
        if success:
            print("✅ OAuth2 authentication completed successfully!")
            print("🎉 Your bot is now authorized to post comments to YouTube!")
            print()
            print("Next steps:")
            print("1. Set ENABLE_COMMENT_POSTING=true in your .env file")
            print("2. Start your bot and begin posting comments!")
            return True
        else:
            print("❌ OAuth2 authentication failed")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Error during OAuth2 flow: {e}")
        return False


def main():
    """Main function."""
    print("🤖 YouTube Comment Bot - OAuth2 Setup")
    print("="*50)
    
    # Check prerequisites
    if not check_prerequisites():
        print_oauth2_instructions()
        return
    
    print(f"📋 Current configuration:")
    print(f"   Client ID: {settings.GOOGLE_CLIENT_ID[:20]}...")
    print(f"   Redirect URI: {settings.GOOGLE_OAUTH2_REDIRECT_URI}")
    print(f"   Scopes: {', '.join(settings.get_oauth2_scopes())}")
    print()
    
    # Ask user if they want to proceed
    proceed = input("Do you want to start the OAuth2 authentication flow? (y/N): ").strip().lower()
    if proceed not in ['y', 'yes']:
        print("👋 OAuth2 setup cancelled")
        return
    
    # Run OAuth2 flow
    try:
        success = asyncio.run(run_oauth2_flow())
        if not success:
            print("\n💡 Troubleshooting tips:")
            print("- Make sure your OAuth2 credentials are correct")
            print("- Check that the redirect URI matches your Google Cloud Console settings")
            print("- Ensure YouTube Data API v3 is enabled in your Google Cloud project")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 OAuth2 setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
