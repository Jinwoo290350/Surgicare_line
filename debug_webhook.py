#!/usr/bin/env python3
"""
Debug script for LINE Bot webhook issues
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

def check_webhook_status():
    """Check current webhook endpoint"""
    url = "https://api.line.me/v2/bot/channel/webhook/endpoint"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("✅ Current webhook endpoint:")
            print(f"   URL: {data.get('endpoint', 'Not set')}")
            print(f"   Active: {data.get('active', False)}")
            return data.get('endpoint')
        else:
            print(f"❌ Failed to get webhook info: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error checking webhook: {e}")
        return None

def test_webhook_endpoint(webhook_url):
    """Test if webhook endpoint is accessible"""
    if not webhook_url:
        print("❌ No webhook URL to test")
        return False
    
    try:
        # Test health endpoint
        health_url = webhook_url.replace('/callback', '/health')
        print(f"   Testing: {health_url}")
        
        # Add headers to bypass ngrok browser warning
        headers = {
            'User-Agent': 'LINE-Bot-Webhook-Test/1.0',
            'ngrok-skip-browser-warning': 'true'
        }
        
        response = requests.get(health_url, timeout=10, headers=headers)
        
        print(f"   Response status: {response.status_code}")
        print(f"   Response headers: {dict(response.headers)}")
        print(f"   Response body: {response.text[:500]}...")
        
        if response.status_code == 200:
            print("✅ Webhook endpoint is accessible")
            try:
                data = response.json()
                print(f"   Status: {data.get('status')}")
                print(f"   LINE configured: {data.get('line_configured')}")
            except:
                print("   (Non-JSON response)")
            return True
        else:
            print(f"❌ Webhook not accessible: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print("❌ Webhook timeout - endpoint too slow")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")
        return False

def update_webhook_url(new_url):
    """Update LINE webhook URL"""
    url = "https://api.line.me/v2/bot/channel/webhook/endpoint"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "endpoint": f"{new_url}/callback"
    }
    
    try:
        response = requests.put(url, headers=headers, json=payload)
        if response.status_code == 200:
            print(f"✅ Webhook updated successfully: {new_url}/callback")
            return True
        else:
            print(f"❌ Failed to update webhook: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error updating webhook: {e}")
        return False

def test_line_api():
    """Test LINE API access"""
    url = "https://api.line.me/v2/bot/info"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("✅ LINE API access working")
            print(f"   Bot ID: {data.get('userId')}")
            print(f"   Display Name: {data.get('displayName')}")
            return True
        else:
            print(f"❌ LINE API error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing LINE API: {e}")
        return False

def main():
    print("🔍 LINE Bot Webhook Debugging")
    print("=" * 50)
    
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("❌ LINE_CHANNEL_ACCESS_TOKEN not found in .env")
        return
    
    # Step 1: Test LINE API access
    print("\n1. Testing LINE API access...")
    if not test_line_api():
        print("   Fix LINE_CHANNEL_ACCESS_TOKEN first!")
        return
    
    # Step 2: Test local Flask app
    print("\n2. Testing local Flask app...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Local Flask app is running")
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   LINE configured: {data.get('line_configured')}")
        else:
            print(f"❌ Local Flask app error: {response.status_code}")
            print("   Make sure Flask app is running: python app.py")
    except Exception as e:
        print(f"❌ Cannot connect to local Flask app: {e}")
        print("   Make sure Flask app is running: python app.py")
        return
    
    # Step 3: Check current webhook
    print("\n3. Checking current webhook...")
    current_webhook = check_webhook_status()
    
    # Step 4: Test webhook accessibility
    print("\n4. Testing webhook accessibility...")
    webhook_accessible = test_webhook_endpoint(current_webhook)
    
    # Step 5: Get ngrok URL
    print("\n5. Getting ngrok tunnel info...")
    try:
        ngrok_response = requests.get("http://localhost:4040/api/tunnels")
        if ngrok_response.status_code == 200:
            tunnels = ngrok_response.json().get('tunnels', [])
            https_tunnels = [t for t in tunnels if t['proto'] == 'https']
            
            if https_tunnels:
                ngrok_url = https_tunnels[0]['public_url']
                print(f"✅ Found ngrok HTTPS tunnel: {ngrok_url}")
                
                # Test ngrok directly
                print(f"\n6. Testing ngrok tunnel directly...")
                headers = {
                    'User-Agent': 'LINE-Bot-Webhook-Test/1.0',
                    'ngrok-skip-browser-warning': 'true'
                }
                try:
                    direct_response = requests.get(f"{ngrok_url}/health", headers=headers, timeout=10)
                    print(f"   Direct ngrok test: {direct_response.status_code}")
                    if direct_response.status_code != 200:
                        print(f"   Response: {direct_response.text[:300]}")
                except Exception as e:
                    print(f"   Direct ngrok test failed: {e}")
                
                # Step 7: Update webhook if needed
                if current_webhook != f"{ngrok_url}/callback":
                    print(f"\n7. Updating webhook URL...")
                    if update_webhook_url(ngrok_url):
                        print("✅ Webhook updated successfully!")
                        # Wait a moment for update to take effect
                        import time
                        time.sleep(2)
                    else:
                        print("❌ Failed to update webhook")
                else:
                    print("\n7. Webhook URL is already correct")
                
                # Step 8: Test webhook again
                print(f"\n8. Final webhook test...")
                if test_webhook_endpoint(ngrok_url):
                    print("✅ Everything looks good!")
                    print("\n💡 Try sending a message to your LINE Bot now!")
                else:
                    print("❌ Webhook still not working")
                    print("\n🔧 Troubleshooting steps:")
                    print("   1. Check if Flask app is running: python app.py")
                    print("   2. Check Flask logs for errors")
                    print("   3. Restart ngrok: ngrok http 8000")
                    print("   4. Make sure .env file has correct LINE credentials")
            else:
                print("❌ No HTTPS ngrok tunnel found")
                print("   Make sure ngrok is running with: ngrok http 8000")
        else:
            print("❌ Cannot connect to ngrok API")
            print("   Make sure ngrok is running")
    except Exception as e:
        print(f"❌ Error getting ngrok info: {e}")
    
    print("\n" + "=" * 50)
    print("Debug complete!")

if __name__ == "__main__":
    main()