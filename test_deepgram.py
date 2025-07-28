#!/usr/bin/env python3
"""
Test script to verify Deepgram API key and connection
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_deepgram_api():
    """Test Deepgram API key and connection"""
    api_key = os.getenv('DEEPGRAM_API_KEY')
    
    print("🔍 Testing Deepgram API Integration")
    print("=" * 50)
    
    # Check API key
    print(f"API Key: {api_key[:10]}...{api_key[-5:] if api_key and len(api_key) > 15 else 'INVALID'}")
    print(f"API Key Length: {len(api_key) if api_key else 0}")
    
    if not api_key:
        print("❌ No Deepgram API key found in .env file")
        return False
    
    if len(api_key) < 30:
        print("⚠️  API key seems too short. Deepgram keys are usually 40+ characters")
        print("   Example format: 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0'")
    
    # Test API connection
    print("\n🌐 Testing API Connection...")
    
    try:
        # Use a simple API endpoint to test authentication
        url = "https://api.deepgram.com/v1/projects"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API key is valid and working!")
            projects = response.json()
            print(f"Found {len(projects.get('projects', []))} project(s)")
            return True
        elif response.status_code == 401:
            print("❌ Authentication failed - Invalid API key")
            print("   Please check your Deepgram API key in the .env file")
        elif response.status_code == 402:
            print("❌ Payment required - Insufficient credits")
            print("   Please add credits to your Deepgram account")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text}")
        
        return False
        
    except requests.exceptions.ConnectionError:
        print("❌ Network connection error")
        print("   Please check your internet connection")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request timeout")
        print("   Please try again later")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def get_api_key_instructions():
    """Provide instructions for getting a valid Deepgram API key"""
    print("\n📝 How to get a valid Deepgram API key:")
    print("=" * 50)
    print("1. Go to https://console.deepgram.com/")
    print("2. Sign up for a free account (includes $200 in free credits)")
    print("3. Navigate to 'API Keys' in the dashboard")
    print("4. Create a new API key")
    print("5. Copy the key (it should be 40+ characters long)")
    print("6. Update your .env file:")
    print("   DEEPGRAM_API_KEY=your_actual_api_key_here")
    print("\n💡 Note: Free tier includes:")
    print("   - $200 in free credits")
    print("   - No credit card required")
    print("   - Supports multiple audio formats")

if __name__ == "__main__":
    success = test_deepgram_api()
    
    if not success:
        get_api_key_instructions()
    
    print("\n" + "=" * 50)
    print("Test completed!")
