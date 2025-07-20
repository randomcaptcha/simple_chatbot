#!/usr/bin/env python3
"""
Configuration utility for loading environment variables
"""

import os
from pathlib import Path

def load_env_file(env_file_path):
    """Load environment variables from a .env file"""
    if not os.path.exists(env_file_path):
        print(f"Warning: {env_file_path} not found")
        return
    
    with open(env_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value

# Load environment variables from config.env (in parent directory)
root_dir = Path(__file__).parent.parent
env_file = root_dir / "config.env"
load_env_file(env_file)

class Config:
    """Configuration class with all API keys and settings"""
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    
    # MCP Server Configuration
    MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://127.0.0.1:5000')
    
    # Google Drive Configuration
    GOOGLE_DRIVE_SCOPES = os.getenv('GOOGLE_DRIVE_SCOPES', 
                                   'https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/documents')
    
    @classmethod
    def validate(cls):
        """Validate that required configuration is present"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required in config.env")
        
        print("✅ Configuration loaded successfully")
        return True

# Validate configuration on import
if __name__ == "__main__":
    Config.validate() 