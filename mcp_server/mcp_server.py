#!/usr/bin/env python3

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
import numpy as np
from openai import OpenAI
import tiktoken
from threading import Lock
import os

from config import Config

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP Types
@dataclass
class Tool:
    name: str
    description: str
    inputSchema: Dict[str, Any]

@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    mimeType: str

class GoogleDriveMCPServer:
    
    def __init__(self):
        # Validate configuration
        Config.validate()
        
        # Initialize Google credentials
        self.setup_google_credentials()
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        
        # Naive document index
        self.index = []
        self.index_lock = Lock()
        
        # Define MCP tools
        self.tools = [
            Tool(
                name="list_files",
                description="List files in Google Drive",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pageSize": {"type": "integer", "default": 10},
                        "mimeType": {"type": "string", "description": "Filter by MIME type"}
                    }
                }
            ),
            Tool(
                name="read_document",
                description="Read content from a Google Doc",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string", "description": "Google Doc file ID"}
                    },
                    "required": ["file_id"]
                }
            ),
            Tool(
                name="create_document",
                description="Create a new Google Doc",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Document title"},
                        "content": {"type": "string", "description": "Document content"}
                    },
                    "required": ["title"]
                }
            ),
            Tool(
                name="search_documents",
                description="Search documents using semantic similarity",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="ask_question",
                description="Ask a question about your documents or general knowledge",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "The question to ask"},
                        "use_documents": {"type": "boolean", "default": True, "description": "Whether to search documents"}
                    },
                    "required": ["question"]
                }
            ),
            Tool(
                name="reindex_documents",
                description="Rebuild the document search index",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
        
        self.resources = [
            MCPResource(
                uri="gdrive://files",
                name="Google Drive Files",
                description="Access to files in Google Drive",
                mimeType="application/json"
            ),
            MCPResource(
                uri="gdrive://documents",
                name="Google Documents",
                description="Access to Google Docs content",
                mimeType="text/plain"
            )
        ]

    def setup_google_credentials(self):
        SCOPES = Config.GOOGLE_DRIVE_SCOPES.split(',')
        
        try:
            with open('../scripts/google_tokens.json', 'r') as f:
                tokens = json.load(f)
            
            self.google_creds = Credentials(
                token=tokens['token'],
                refresh_token=tokens['refresh_token'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=tokens['client_id'],
                client_secret=tokens['client_secret'],
                scopes=SCOPES
            )
            logger.info("✅ Loaded OAuth credentials")
            
        except FileNotFoundError:
            # Fall back to service account, but this acc does not have access to doc write access
            self.google_creds = service_account.Credentials.from_service_account_file(
                '../scripts/gdrive_service_account.json', scopes=SCOPES
            )
            logger.info("Using service account: no doc write access available")
        
        self.drive_service = build('drive', 'v3', credentials=self.google_creds)  # type: ignore
        self.docs_service = build('docs', 'v1', credentials=self.google_creds)  # type: ignore

    def get_embedding(self, text: str) -> np.ndarray:
        """Get text embedding using OpenAI"""
        resp = self.client.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        return np.array(resp.data[0].embedding)

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings"""
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def extract_text_from_doc(self, doc: Dict) -> str:
        """Extract text from Google Doc API response"""
        text = []
        for element in doc.get('body', {}).get('content', []):
            if 'paragraph' in element:
                for elem in element['paragraph'].get('elements', []):
                    if 'textRun' in elem and 'content' in elem['textRun']:
                        text.append(elem['textRun']['content'])
        return ''.join(text)

    def build_index(self):
        """Build document search index"""
        with self.index_lock:
            self.index = []
            try:
                results = self.drive_service.files().list(  # type: ignore
                    q="mimeType='application/vnd.google-apps.document'",
                    pageSize=50
                ).execute()
                
                items = results.get('files', [])
                logger.info(f"Found {len(items)} Google Docs")
                
                for file in items:
                    try:
                        doc = self.docs_service.documents().get(  # type: ignore
                            documentId=file['id']
                        ).execute()
                        content = self.extract_text_from_doc(doc)
                        embedding = self.get_embedding(file['name'] + '\n' + content)
                        
                        self.index.append({
                            'id': file['id'],
                            'name': file['name'],
                            'content': content,
                            'embedding': embedding
                        })
                        logger.info(f"Indexed: {file['name']}")
                        
                    except Exception as e:
                        logger.error(f"Error indexing {file['name']}: {e}")
                        
            except Exception as e:
                logger.error(f"Error accessing Drive API: {e}")

    # MCP Protocol Methods
    async def initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Initializing MCP server")
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "serverInfo": {
                "name": "google-drive-mcp-server",
                "version": "1.0.0"
            }
        }

    async def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            for tool in self.tools
        ]

    async def list_resources(self) -> List[Dict[str, Any]]:
        return [
            {
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
                "mimeType": resource.mimeType
            }
            for resource in self.resources
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Calling tool: {name} with args: {arguments}")
        
        try:
            if name == "list_files":
                return await self._list_files(arguments)
            elif name == "read_document":
                return await self._read_document(arguments)
            elif name == "create_document":
                return await self._create_document(arguments)
            elif name == "search_documents":
                return await self._search_documents(arguments)
            elif name == "ask_question":
                return await self._ask_question(arguments)
            elif name == "reindex_documents":
                return await self._reindex_documents(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
                
        except Exception as e:
            logger.error(f"Error in tool {name}: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource"""
        if uri == "gdrive://files":
            return await self._list_files({})
        elif uri == "gdrive://documents":
            return await self._list_files({"mimeType": "application/vnd.google-apps.document"})
        else:
            raise ValueError(f"Unknown resource: {uri}")

    # Tool Implementations
    async def _list_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List files in Google Drive"""
        page_size = args.get('pageSize', 10)
        mime_type = args.get('mimeType')
        
        query = f"mimeType='{mime_type}'" if mime_type else None
        
        results = self.drive_service.files().list(  # type: ignore
            pageSize=page_size,
            q=query,
            fields="files(id, name, mimeType, createdTime, modifiedTime)"
        ).execute()
        
        files = results.get('files', [])
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(files, indent=2)
            }]
        }

    async def _read_document(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read content from a Google Doc"""
        file_id = args['file_id']
        
        doc = self.docs_service.documents().get(documentId=file_id).execute()  # type: ignore
        content = self.extract_text_from_doc(doc)
        
        return {
            "content": [{
                "type": "text",
                "text": content
            }]
        }

    async def _create_document(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Google Doc"""
        title = args['title']
        content = args.get('content', '')
        
        doc = self.docs_service.documents().create(body={'title': title}).execute()  # type: ignore
        doc_id = doc['documentId']
        
        if content:
            self.docs_service.documents().batchUpdate(  # type: ignore
                documentId=doc_id,
                body={
                    'requests': [{
                        'insertText': {
                            'location': {'index': 1},
                            'text': content
                        }
                    }]
                }
            ).execute()
        
        doc_url = f'https://docs.google.com/document/d/{doc_id}/edit'
        
        return {
            "content": [{
                "type": "text",
                "text": f"Created document: {title}\nURL: {doc_url}\nDocument ID: {doc_id}"
            }]
        }

    async def _search_documents(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search documents using semantic similarity"""
        query = args['query']
        max_results = args.get('max_results', 5)
        
        if not self.index:
            return {
                "content": [{
                    "type": "text",
                    "text": "No documents indexed. Run reindex_documents first."
                }]
            }
        
        query_embedding = self.get_embedding(query)
        
        with self.index_lock:
            scored = [
                (self.cosine_similarity(query_embedding, doc['embedding']), doc)
                for doc in self.index
            ]
            sorted_scored = sorted(scored, key=lambda x: x[0], reverse=True)[:max_results]
        
        results = []
        for score, doc in sorted_scored:
            results.append(f"Score: {score:.3f}\nName: {doc['name']}\nContent: {doc['content'][:200]}...\n")
        
        return {
            "content": [{
                "type": "text",
                "text": f"Search results for '{query}':\n\n" + "\n".join(results)
            }]
        }

    async def _ask_question(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Ask a question about documents or general knowledge"""
        question = args['question']
        use_documents = args.get('use_documents', True)
        
        if use_documents and self.index:
            # Use document context
            return await self._answer_with_documents(question)
        else:
            # Use general knowledge
            return await self._answer_with_general_knowledge(question)

    async def _answer_with_documents(self, question: str) -> Dict[str, Any]:
        """Answer using document context"""
        try:
            query_embedding = self.get_embedding(question)
            
            with self.index_lock:
                scored = [
                    (self.cosine_similarity(query_embedding, doc['embedding']), doc)
                    for doc in self.index
                ]
                sorted_scored = sorted(scored, key=lambda x: x[0], reverse=True)
                # Filter by similarity threshold and get top 5
                relevant_docs = [doc for score, doc in sorted_scored if score > 0.1][:5]
            
            if not relevant_docs:
                # No relevant documents found, fall back to general knowledge
                return await self._answer_with_general_knowledge(question)
            
            # Build context with token management
            enc = tiktoken.encoding_for_model(self.model)
            context_chunks = []
            total_tokens = 0
            max_context_tokens = 6000
            
            for doc in relevant_docs:
                chunk = f"{doc['name']}:\n{doc['content'][:1000]}"
                chunk_tokens = len(enc.encode(chunk))
                
                if total_tokens + chunk_tokens > max_context_tokens:
                    break
                context_chunks.append(chunk)
                total_tokens += chunk_tokens
            
            context = "\n\n".join(context_chunks)
            prompt = f"""You are a helpful assistant with access to the following documents. Answer the user's question using the information from these documents. If the answer cannot be found in the provided documents, say "I don't have information about that in your documents, but I can help with general knowledge questions."

Documents:
{context}

Question: {question}

Answer:"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )
            
            return {
                "content": [{
                    "type": "text",
                    "text": response.choices[0].message.content
                }]
            }
        except Exception as e:
            # Fall back to general knowledge if there's an error
            print(f"Error in document search: {e}")
            return await self._answer_with_general_knowledge(question)

    async def _answer_with_general_knowledge(self, question: str) -> Dict[str, Any]:
        """Answer using general knowledge"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": question}],
            temperature=0.3,
            max_tokens=1000
        )
        
        return {
            "content": [{
                "type": "text",
                "text": response.choices[0].message.content
            }]
        }

    async def _reindex_documents(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Rebuild document index"""
        self.build_index()
        
        return {
            "content": [{
                "type": "text",
                "text": f"Reindexed {len(self.index)} documents"
            }]
        }

# MCP Server instance
mcp_server = GoogleDriveMCPServer()

# Example usage function
async def example_usage():
    """Example of how to use the MCP server"""
    # Initialize
    await mcp_server.initialize({})
    
    # List tools
    tools = await mcp_server.list_tools()
    print("Available tools:", [tool['name'] for tool in tools])
    
    # List resources
    resources = await mcp_server.list_resources()
    print("Available resources:", [res['uri'] for res in resources])
    
    # Example tool calls
    result = await mcp_server.call_tool("list_files", {"pageSize": 5})
    print("Files:", result['content'][0]['text'])
    
    result = await mcp_server.call_tool("ask_question", {
        "question": "What is machine learning?",
        "use_documents": False
    })
    print("Answer:", result['content'][0]['text'])

if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage()) 