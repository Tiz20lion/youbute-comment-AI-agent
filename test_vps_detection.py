#!/usr/bin/env python3
"""
Test script to verify VPS detection and OAuth2 redirect URI configuration.
Run this on your VPS to check if the OAuth2 redirect URI is correctly detected.
"""

import sys
import os
import json
import requests

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_vps_detection():
    """Test VPS detection and OAuth2 redirect URI configuration."""
    print("🔍 Testing VPS Detection and OAuth2 Configuration")
    print("=" * 60)
    
    try:
        from app.config import get_settings
        settings = get_settings()
        
        print(f"📍 Current working directory: {os.getcwd()}")
        print(f"🌐 Environment: {settings.ENVIRONMENT}")
        print(f"🔧 Debug mode: {settings.DEBUG}")
        print()
        
        # Test redirect URI detection
        print("🔗 OAuth2 Redirect URI Detection:")
        print("-" * 40)
        
        # Test with different configurations
        redirect_uri = settings.get_oauth2_redirect_uri()
        print(f"✅ Detected redirect URI: {redirect_uri}")
        
        # Check if using .env value or auto-detection
        if settings.GOOGLE_OAUTH2_REDIRECT_URI:
            print(f"📝 Source: .env file (GOOGLE_OAUTH2_REDIRECT_URI)")
            print(f"   Value: {settings.GOOGLE_OAUTH2_REDIRECT_URI}")
        else:
            print(f"🤖 Source: Auto-detection")
            detected_host = settings._detect_host()
            print(f"   Detected host: {detected_host}")
            print(f"   Using port: {settings.PORT}")
        
        print()
        
        # Test OAuth2 configuration
        print("🔐 OAuth2 Configuration Status:")
        print("-" * 40)
        print(f"✅ Client ID configured: {bool(settings.GOOGLE_CLIENT_ID)}")
        print(f"✅ Client Secret configured: {bool(settings.GOOGLE_CLIENT_SECRET)}")
        print(f"✅ Can post comments: {settings.can_post_comments()}")
        print()
        
        # Test API endpoint
        print("🌐 Testing API Endpoint:")
        print("-" * 40)
        try:
            # Try to test the settings API endpoint if server is running
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', settings.PORT))
            sock.close()
            
            if result == 0:
                print(f"✅ Server is running on port {settings.PORT}")
                
                # Test the API endpoint
                response = requests.get(f'http://localhost:{settings.PORT}/api/v1/settings', timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    api_redirect_uri = data.get('oauth2_status', {}).get('redirect_uri')
                    print(f"✅ API endpoint working")
                    print(f"✅ API returns redirect URI: {api_redirect_uri}")
                    
                    if api_redirect_uri == redirect_uri:
                        print("✅ Backend and API redirect URIs match!")
                    else:
                        print("⚠️  Backend and API redirect URIs don't match")
                        print(f"   Backend: {redirect_uri}")
                        print(f"   API:     {api_redirect_uri}")
                else:
                    print(f"❌ API endpoint error: {response.status_code}")
            else:
                print(f"⚠️  Server not running on port {settings.PORT}")
                print("   Start your app to test the API endpoint")
                
        except Exception as e:
            print(f"⚠️  Could not test API endpoint: {e}")
        
        print()
        
        # Give recommendations
        print("📋 Recommendations:")
        print("-" * 40)
        
        # Check if using localhost in production
        if "localhost" in redirect_uri and settings.ENVIRONMENT == "production":
            print("⚠️  WARNING: Using localhost in production!")
            print("   🔧 Fix: Set GOOGLE_OAUTH2_REDIRECT_URI in your .env file")
            print("   📝 Example: GOOGLE_OAUTH2_REDIRECT_URI=http://yourdomain.hopto.org:7844/oauth2callback")
            print()
        
        # Check No-IP domain format
        if any(domain in redirect_uri for domain in ['.hopto.org', '.ddns.net', '.zapto.org']):
            print("✅ Good: Using No-IP dynamic DNS domain")
            print()
        
        # Check if domain points to external IP
        detected_host = settings._detect_host()
        if not detected_host.startswith('127.') and not detected_host == 'localhost':
            print(f"✅ Good: Detected external host/IP: {detected_host}")
        else:
            print("⚠️  Using localhost/local IP")
            print("   🔧 Consider setting PUBLIC_DOMAIN environment variable")
            print("   📝 Example: PUBLIC_DOMAIN=yourdomain.hopto.org")
        
        print()
        print("🎯 Google Console Instructions:")
        print("-" * 40)
        print("1. Go to: https://console.cloud.google.com/")
        print("2. Navigate to: APIs & Services → Credentials")
        print("3. Edit your OAuth2 client")
        print("4. Add this to 'Authorized redirect URIs':")
        print(f"   {redirect_uri}")
        print("5. Save changes")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error importing settings: {e}")
        print("   Make sure you're running this from the project root directory")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_environment_variables():
    """Test environment variables related to OAuth2."""
    print("\n🔧 Environment Variables:")
    print("-" * 40)
    
    # Check important environment variables
    env_vars = [
        'GOOGLE_OAUTH2_REDIRECT_URI',
        'PUBLIC_DOMAIN',
        'VPS_HOST',
        'SERVER_HOST',
        'DOMAIN_NAME',
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'SECRET' in var or 'CLIENT_ID' in var:
                masked_value = value[:8] + '***' if len(value) > 8 else '***'
                print(f"✅ {var}: {masked_value}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: Not set")

if __name__ == "__main__":
    print("🚀 YouTube Comment AI Agent - VPS Configuration Test")
    print("=" * 60)
    
    success = test_vps_detection()
    test_environment_variables()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Configuration test completed!")
        print("📝 Review the recommendations above and update your Google Console")
    else:
        print("❌ Configuration test failed - check the errors above") 