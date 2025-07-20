#!/usr/bin/env python3
"""
MCP-to-REST Bridge
Provides REST API endpoints that wrap the MCP server functionality
In the future, get rid of the bridge and connect straight to fronend
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import asyncio
import json
import os

from config import Config

from mcp_server import GoogleDriveMCPServer
from intent_classifier import LLMIntentClassifier

app = Flask(__name__)
CORS(app)

# Validate configuration
Config.validate()

# Initialize MCP server and intent classifier
mcp_server = GoogleDriveMCPServer()
intent_classifier = LLMIntentClassifier()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'server': 'mcp-bridge'}), 200

# Helper function to run async functions in Flask
def run_async(coro):
    """Run async coroutine in Flask context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Replace async routes with sync versions
@app.route('/ask', methods=['POST'])
def ask_sync():
    """Main endpoint for questions - routes to MCP ask_question tool"""
    data = request.get_json()
    question = data.get('question', '')
    
    if not question:
        return jsonify({'error': 'Missing question'}), 400
    
    try:
        # Initialize MCP server if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mcp_server.initialize({}))
        finally:
            loop.close()
        
        # Use LLM-based intent classification
        intent_result = intent_classifier.classify_intent(question)
        print(f"Intent classification: {intent_result['intent']} (confidence: {intent_result['confidence']:.2f})")
        print(f"Reasoning: {intent_result['reasoning']}")
        
        # Route based on intent
        if intent_classifier.is_action_request(intent_result):
            if intent_result["intent"] == "create_document":
                # Route to document creation
                result = run_async(mcp_server.call_tool("create_document", {
                    "title": f"Document for: {question}",
                    "content": f"Document created based on request: {question}\n\nThis document was generated in response to your request."
                }))
            elif intent_result["intent"] == "file_management":
                # Route to file management (could be expanded with more tools)
                result = run_async(mcp_server.call_tool("create_document", {
                    "title": f"File Management Request: {question}",
                    "content": f"File management request: {question}\n\nNote: Advanced file management features are being developed."
                }))
        else:
            # Route to question answering
            use_documents = intent_classifier.should_use_documents(intent_result)
            result = run_async(mcp_server.call_tool("ask_question", {
                "question": question,
                "use_documents": use_documents
            }))
        
        if result.get('isError'):
            return jsonify({'error': result['content'][0]['text']}), 500
        
        return jsonify({'answer': result['content'][0]['text']}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error processing request: {str(e)}'}), 500

@app.route('/reindex', methods=['POST'])
def reindex_sync():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mcp_server.initialize({}))
            result = loop.run_until_complete(mcp_server.call_tool("reindex_documents", {}))
        finally:
            loop.close()
        
        if result.get('isError'):
            return jsonify({'error': result['content'][0]['text']}), 500
        
        return jsonify({'message': result['content'][0]['text']}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error reindexing: {str(e)}'}), 500

@app.route('/list-files', methods=['GET'])
def list_files_sync():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mcp_server.initialize({}))
            page_size = request.args.get('pageSize', 10, type=int)
            result = loop.run_until_complete(mcp_server.call_tool("list_files", {"pageSize": page_size}))
        finally:
            loop.close()
        
        if result.get('isError'):
            return jsonify({'error': result['content'][0]['text']}), 500
        
        files = json.loads(result['content'][0]['text'])
        return jsonify({'files': files}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error listing files: {str(e)}'}), 500

@app.route('/read-file', methods=['GET'])
def read_file_sync():
    file_id = request.args.get('file_id')
    if not file_id:
        return jsonify({'error': 'file_id is required'}), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mcp_server.initialize({}))
            result = loop.run_until_complete(mcp_server.call_tool("read_document", {"file_id": file_id}))
        finally:
            loop.close()
        
        if result.get('isError'):
            return jsonify({'error': result['content'][0]['text']}), 500
        
        return jsonify({'content': result['content'][0]['text']}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error reading file: {str(e)}'}), 500

@app.route('/create-google-doc', methods=['POST'])
def create_google_doc_sync():
    data = request.get_json()
    title = data.get('title', 'Untitled')
    content = data.get('content', '')
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mcp_server.initialize({}))
            result = loop.run_until_complete(mcp_server.call_tool("create_document", {
                "title": title,
                "content": content
            }))
        finally:
            loop.close()
        
        if result.get('isError'):
            return jsonify({'error': result['content'][0]['text']}), 500
        
        return jsonify({'message': result['content'][0]['text']}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error creating document: {str(e)}'}), 500

@app.route('/search', methods=['POST'])
def search_sync():
    data = request.get_json()
    query = data.get('query', '')
    max_results = data.get('max_results', 5)
    
    if not query:
        return jsonify({'error': 'Missing query'}), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mcp_server.initialize({}))
            result = loop.run_until_complete(mcp_server.call_tool("search_documents", {
                "query": query,
                "max_results": max_results
            }))
        finally:
            loop.close()
        
        if result.get('isError'):
            return jsonify({'error': result['content'][0]['text']}), 500
        
        return jsonify({'results': result['content'][0]['text']}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error searching: {str(e)}'}), 500

@app.route('/execute', methods=['POST'])
def execute_sync():
    data = request.get_json()
    command = data.get('command', '')
    
    if not command:
        return jsonify({'error': 'Missing command'}), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mcp_server.initialize({}))
            
            # Use LLM-based intent classification
            intent_result = intent_classifier.classify_intent(command)
            print(f"Intent classification: {intent_result['intent']} (confidence: {intent_result['confidence']:.2f})")
            print(f"Reasoning: {intent_result['reasoning']}")
            if intent_classifier.is_action_request(intent_result):
                if intent_result["intent"] == "create_document":
                    result = loop.run_until_complete(mcp_server.call_tool("create_document", {
                        "title": f"Document: {command}",
                        "content": f"Document created based on command: {command}"
                    }))
                elif intent_result["intent"] == "file_management":
                    result = loop.run_until_complete(mcp_server.call_tool("create_document", {
                        "title": f"File Management: {command}",
                        "content": f"File management command: {command}\n\nNote: Advanced file management features are being developed."
                    }))
            else:
                use_documents = intent_classifier.should_use_documents(intent_result)
                result = loop.run_until_complete(mcp_server.call_tool("ask_question", {
                    "question": command,
                    "use_documents": use_documents
                }))
        finally:
            loop.close()
        
        if result.get('isError'):
            return jsonify({'error': result['content'][0]['text']}), 500
        
        return jsonify({'message': result['content'][0]['text']}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error executing command: {str(e)}'}), 500

@app.route('/debug-index', methods=['GET'])
def debug_index_sync():
    """Debug endpoint to see indexed documents"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mcp_server.initialize({}))
            
            # Get index info
            with mcp_server.index_lock:
                index_info = {
                    'count': len(mcp_server.index),
                    'documents': [
                        {
                            'id': doc['id'],
                            'name': doc['name'],
                            'content_length': len(doc['content'])
                        }
                        for doc in mcp_server.index
                    ]
                }
        finally:
            loop.close()
        
        return jsonify(index_info), 200
        
    except Exception as e:
        return jsonify({'error': f'Error getting index info: {str(e)}'}), 500

if __name__ == '__main__':
    print("Starting MCP Bridge Server...")
    print("Frontend can connect to: http://127.0.0.1:5000")
    print("MCP Server running on: http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000) 