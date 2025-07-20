# MCP Interface <> Google Drive

Experimenting with MCP interface and connecting to Google Drive / Docs
Just to see how a manual MCP hookup would work

## Project Overview

This project demonstrates:
- MCP server implementation for Google Drive
- Regular REST implementation, just for comparison (rest_server.py)
- Doc search using OpenAI embeddings
- LLM-only intent classification for request routing
- Document creation and management via Google Docs API

Disclaimer:
- Naive indexing (just in-memory index)
- Naive embedding generation, no RAG
- Using Cursor for scaffolding and documentation generation

## Project Structure

```
simple_chatbot/
├── frontend/                 # Next.js React frontend
│   ├── src/app/             # App router pages
│   ├── src/components/      # UI components
│   └── public/              # Static assets
├── mcp_server/              # MCP server implementation
│   ├── mcp_server.py        # Core MCP server
│   ├── mcp_bridge.py        # REST API bridge
│   ├── intent_classifier.py # LLM-based intent classification
│   ├── config.py           # Configuration management
│   └── rest_server.py      # Legacy REST implementation
├── scripts/                 # Setup and utility scripts
│   ├── generate_google_tokens.py    # OAuth token generation
│   ├── gdrive_token_gen.py         # Legacy token generator
│   ├── google_tokens.json          # OAuth tokens (generated)
│   └── gdrive_service_account.json # Service account key (from GCP)
├── config.env               # Environment configuration
└── .gitignore              # Git ignore rules
```

## Setup

### 1. Environment Setup

```bash
# Clone and navigate to project
cd simple_chatbot

# Install Python dependencies
cd mcp_server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
npm install
```

### 2. Configuration Setup

**Copy template files and add your credentials:**

```bash
# Copy configuration templates
cp config.env.template config.env
cp scripts/google_tokens.json.template scripts/google_tokens.json
cp scripts/gdrive_service_account.json.template scripts/gdrive_service_account.json

# Edit config.env with your OpenAI API key
vim config.env 
```

### 3. Google API Configuration

#### Option A: OAuth 2.0 (Recommended - Full Access)

1. **Create Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project or select existing
   - Enable Google Drive API and Google Docs API

2. **Create OAuth 2.0 Credentials:**
   - Navigate to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client IDs"
   - Application type: "Desktop application"
   - Download JSON file and rename to `client_secrets.json`
   - Place in `scripts/` directory

3. **Generate OAuth Tokens:**
   ```bash
   cd scripts
   python generate_google_tokens.py
   ```
   This will open browser for authentication and save tokens to `google_tokens.json`

#### Option B: Service Account (Read-Only Access)

1. **Create Service Account:**
   - In Google Cloud Console, go to "IAM & Admin" → "Service Accounts"
   - Create new service account
   - Grant "Google Drive API" and "Google Docs API" roles
   - Create and download JSON key file
   - Rename to `gdrive_service_account.json` and place in `scripts/`

## Running the Application

### Start Backend (MCP Bridge)

```bash
cd mcp_server
source venv/bin/activate
python mcp_bridge.py
```

Server runs on `http://127.0.0.1:5000`

### Start Frontend

```bash
cd frontend
npm run dev
```

Frontend runs on `http://localhost:3000`

## Usage

### Document Indexing

The system maintains an in-memory index of Google Docs for semantic search. To rebuild the index:

```bash
# Via REST API
curl -X POST http://127.0.0.1:5000/reindex

```

### Debug Index Contents

To inspect what documents are indexed:

```bash
# Via REST API
curl http://127.0.0.1:5000/debug-index

# Returns JSON with document count and metadata
```

### API Endpoints

- `POST /ask` - Ask questions (document search or general knowledge)
- `POST /execute` - Execute commands (document creation, file management)
- `POST /reindex` - Rebuild document search index
- `GET /debug-index` - View indexed documents
- `GET /list-files` - List Google Drive files
- `POST /create-google-doc` - Create new Google Doc

### Example Usage

```bash
# Ask about documents
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What documents do I have about AI?"}'

# Create a document
curl -X POST http://127.0.0.1:5000/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "Create a summary of my project documents"}'

# Check index status
curl http://127.0.0.1:5000/debug-index
```

## Key Features

- **MCP Compliance:** Implements Model Context Protocol for standardized tool/resource access
- **Semantic Search:** Uses OpenAI embeddings for intelligent document retrieval
- **Intent Classification:** LLM-based routing of user requests to appropriate tools
- **Hybrid Q&A:** Combines document context with general knowledge
- **Document Management:** Create and manage Google Docs through API

## Architecture Notes

- **MCP Server:** Core implementation following MCP protocol specification
- **REST Bridge:** Provides HTTP endpoints for frontend integration
- **Intent Classifier:** Uses ChatGPT to classify user intent for proper routing
- **Embedding Index:** In-memory semantic search index with cosine similarity
- **Credential Management:** Supports both OAuth 2.0 and service account authentication