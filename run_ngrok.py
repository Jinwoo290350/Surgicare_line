#!/usr/bin/env python3
"""
Ngrok tunnel script for LINE Bot development
Automatically sets up ngrok tunnel and updates LINE Bot webhook URL
"""

import os
import sys
import time
import requests
import json
from pyngrok import ngrok, conf
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NgrokManager:
    def __init__(self):
        self.ngrok_auth_token = os.getenv('NGROK_AUTH_TOKEN')
        self.line_channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        self.port = int(os.getenv('PORT', 5000))
        self.region = os.getenv('NGROK_REGION', 'ap')  # Asia Pacific
        self.subdomain = os.getenv('NGROK_SUBDOMAIN')
        
        # Validate required environment variables
        if not self.ngrok_auth_token:
            logger.error("NGROK_AUTH_TOKEN not found in environment variables")
            sys.exit(1)
        
        if not self.line_channel_access_token:
            logger.error("LINE_CHANNEL_ACCESS_TOKEN not found in environment variables")
            sys.exit(1)

    def setup_ngrok(self):
        """Setup ngrok configuration and authentication"""
        try:
            # Set ngrok auth token
            ngrok.set_auth_token(self.ngrok_auth_token)
            
            # Configure ngrok
            conf.get_default().region = self.region
            
            logger.info(f"Ngrok configured for region: {self.region}")
            
        except Exception as e:
            logger.error(f"Failed to setup ngrok: {str(e)}")
            sys.exit(1)

    def create_tunnel(self):
        """Create ngrok tunnel"""
        try:
            # Create tunnel options
            tunnel_options = {
                "addr": self.port,
                "proto": "http",
                "bind_tls": True  # Force HTTPS
            }
            
            # Add subdomain if specified
            if self.subdomain:
                tunnel_options["subdomain"] = self.subdomain
            
            # Create tunnel
            public_url = ngrok.connect(**tunnel_options)
            
            logger.info(f"Ngrok tunnel created: {public_url}")
            return public_url
            
        except Exception as e:
            logger.error(f"Failed to create ngrok tunnel: {str(e)}")
            sys.exit(1)

    def update_line_webhook(self, webhook_url):
        """Update LINE Bot webhook URL"""
        try:
            # LINE Messaging API endpoint
            endpoint = "https://api.line.me/v2/bot/channel/webhook/endpoint"
            
            headers = {
                "Authorization": f"Bearer {self.line_channel_access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "endpoint": f"{webhook_url}/callback"
            }
            
            response = requests.put(endpoint, headers=headers, json=payload)
            
            if response.status_code == 200:
                logger.info(f"LINE webhook updated successfully: {webhook_url}/callback")
                return True
            else:
                logger.error(f"Failed to update LINE webhook: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating LINE webhook: {str(e)}")
            return False

    def verify_webhook(self, webhook_url):
        """Verify webhook is accessible"""
        try:
            test_url = f"{webhook_url}/health"
            response = requests.get(test_url, timeout=10)
            
            if response.status_code == 200:
                logger.info("Webhook verification successful")
                return True
            else:
                logger.warning(f"Webhook verification failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Webhook verification error: {str(e)}")
            return False

    def get_tunnel_info(self):
        """Get information about active tunnels"""
        try:
            tunnels = ngrok.get_tunnels()
            
            if tunnels:
                logger.info("Active ngrok tunnels:")
                for tunnel in tunnels:
                    logger.info(f"  - {tunnel.name}: {tunnel.public_url} -> {tunnel.config['addr']}")
            else:
                logger.info("No active ngrok tunnels found")
                
            return tunnels
            
        except Exception as e:
            logger.error(f"Error getting tunnel info: {str(e)}")
            return []

    def run(self):
        """Main method to setup and run ngrok"""
        logger.info("Starting ngrok setup for LINE Bot...")
        
        # Setup ngrok
        self.setup_ngrok()
        
        # Create tunnel
        public_url = self.create_tunnel()
        
        # Wait a moment for tunnel to be ready
        time.sleep(2)
        
        # Update LINE webhook
        webhook_updated = self.update_line_webhook(public_url)
        
        if webhook_updated:
            logger.info("✅ Ngrok setup completed successfully!")
        else:
            logger.warning("⚠️  Ngrok tunnel created but LINE webhook update failed")
        
        # Show tunnel information
        self.get_tunnel_info()
        
        # Verify webhook
        self.verify_webhook(public_url)
        
        # Display connection info
        self.display_connection_info(public_url)
        
        return public_url

    def display_connection_info(self, public_url):
        """Display connection information"""
        print("\n" + "="*60)
        print("🚀 LINE Bot is ready!")
        print("="*60)
        print(f"Public URL: {public_url}")
        print(f"Webhook URL: {public_url}/callback")
        print(f"Health Check: {public_url}/health")
        print(f"Local Server: http://localhost:{self.port}")
        print("\n📱 You can now test your LINE Bot!")
        print("📊 Monitor ngrok traffic at: http://localhost:4040")
        print("\nPress Ctrl+C to stop the tunnel")
        print("="*60)

    def cleanup(self):
        """Cleanup ngrok tunnels"""
        try:
            ngrok.disconnect_all()
            logger.info("Ngrok tunnels disconnected")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")


def main():
    """Main function"""
    ngrok_manager = NgrokManager()
    
    try:
        # Run ngrok setup
        public_url = ngrok_manager.run()
        
        # Keep the script running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\nShutting down ngrok...")
        ngrok_manager.cleanup()
        logger.info("Ngrok shutdown complete")
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        ngrok_manager.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()