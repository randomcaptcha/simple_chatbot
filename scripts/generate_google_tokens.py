#!/usr/bin/env python3
"""
Generate Google OAuth tokens for Google Drive API
For personal Gmail accounts
"""

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# OAuth 2.0 scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

def generate_google_tokens():
    """Generate OAuth 2.0 credentials for Google Drive API"""
    
    creds = None
    
    # Check if tokens already exist
    if os.path.exists('google_tokens.json'):
        print("✅ Found existing tokens")
        with open('google_tokens.json', 'r') as f:
            tokens = json.load(f)
        print(f"   Client ID: {tokens['client_id']}")
        print(f"   Expires: {tokens.get('expires_at', 'Unknown')}")
        return
    
    # Check if we have existing tokens in parent directory
    if os.path.exists('../google_tokens.json'):
        try:
            with open('../google_tokens.json', 'r') as f:
                tokens = json.load(f)
            
            creds = Credentials(
                token=tokens['access_token'],
                refresh_token=tokens['refresh_token'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=tokens['client_id'],
                client_secret=tokens['client_secret'],
                scopes=SCOPES
            )
            
            # Refresh if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                print("✅ Refreshed existing tokens")
            else:
                print("✅ Using existing valid tokens")
                
        except Exception as e:
            print(f"❌ Error loading tokens: {e}")
            creds = None
    
    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("✅ Refreshed expired tokens")
            except Exception as e:
                print(f"❌ Error refreshing tokens: {e}")
                creds = None
        
        if not creds:
            print("🔐 Need to authenticate with Google...")
            
            # Check if client_secrets.json exists
            if not os.path.exists('client_secrets.json'):
                print("❌ client_secrets.json not found!")
                print("\n📋 To get client_secrets.json:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a new project or select existing")
                print("3. Enable Google Drive API")
                print("4. Go to Credentials")
                print("5. Create OAuth 2.0 Client ID")
                print("6. Set application type to 'Desktop application'")
                print("7. Download the JSON file and rename it to 'client_secrets.json'")
                print("8. Place it in the scripts/ directory")
                return None
            
            # Load client secrets
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
            print("✅ Successfully authenticated!")
    
    # Save tokens for future use
    tokens = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': "https://oauth2.googleapis.com/token",
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes,
        'expires_at': creds.expiry.isoformat() if creds.expiry else None
    }
    
    with open('google_tokens.json', 'w') as f:
        json.dump(tokens, f, indent=2)
    
    print("💾 Tokens saved to google_tokens.json")
    return creds

if __name__ == "__main__":
    print("🔐 Google Drive OAuth Token Generator")
    print("=" * 40)
    
    creds = generate_google_tokens()
    
    if creds:
        print("\n✅ OAuth token generation successful!")
        print("You can now run your MCP server with: python mcp_bridge.py")
    else:
        print("\n❌ OAuth token generation failed. Please follow the instructions above.") 