"""
REST Backend with an explicit implementation of endpoints, just for educational purposes to compare against MCP
"""

from flask import Flask, jsonify, request
from googleapiclient.discovery import build
from google.oauth2 import service_account
import numpy as np
from flask_cors import CORS
from openai import OpenAI
import tiktoken

from threading import Lock
import os

from config import Config

app = Flask(__name__)
CORS(app)

# Validate configuration
Config.validate()

# Service account credentials
SCOPES = Config.GOOGLE_DRIVE_SCOPES.split(',')

try:
    # Try to load existing tokens from file
    import json
    with open('../scripts/google_tokens.json', 'r') as f:
        tokens = json.load(f)
    
    from google.oauth2.credentials import Credentials
    GOOGLE_CREDS = Credentials(
        token=tokens['token'],
        refresh_token=tokens['refresh_token'],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=tokens['client_id'],
        client_secret=tokens['client_secret'],
        scopes=SCOPES
    )
    print("✅ Loaded OAuth credentials from tokens file")
    
except FileNotFoundError:
    print("No OAuth tokens found. You need to authenticate first.")
    print("Run: python gdrive_token_gen.py to generate tokens")
    GOOGLE_CREDS = None
except Exception as e:
    print(f"Error loading credentials: {e}")
    GOOGLE_CREDS = None

index = []  # In-memory index: list of dicts with keys: id, name, content
index_lock = Lock()

client = OpenAI(api_key=Config.OPENAI_API_KEY)
model = Config.OPENAI_MODEL

def get_drive_service():
    if GOOGLE_CREDS is None:
        raise Exception("Google credentials not properly configured. Please update USER_EMAIL in app.py")
    return build('drive', 'v3', credentials=GOOGLE_CREDS)

def get_docs_service():
    if GOOGLE_CREDS is None:
        raise Exception("Google credentials not properly configured. Please update USER_EMAIL in app.py")
    return build('docs', 'v1', credentials=GOOGLE_CREDS)

def extract_text_from_doc(doc):
    """Extract all text from a Google Doc API response."""
    text = []
    print(f"Extracting text from doc with {len(doc.get('body', {}).get('content', []))} content elements")
    for element in doc.get('body', {}).get('content', []):
        if 'paragraph' in element:
            for elem in element['paragraph'].get('elements', []):
                if 'textRun' in elem and 'content' in elem['textRun']:
                    text.append(elem['textRun']['content'])
    result = ''.join(text)
    print(f"Extracted {len(result)} characters of text")
    return result

def get_embedding(text):
    # Use OpenAI's embedding API (text-embedding-3-small is fast and cheap)
    resp = client.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )
    return np.array(resp.data[0].embedding)

def cosine_similarity(a, b):
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def build_index():
    global index
    with index_lock:
        index = []
        service = get_drive_service()
        try:
            results = service.files().list(pageSize=50).execute()  # type: ignore[attr-defined]
            items = results.get('files', [])
            print(f"Found {len(items)} files in Drive")
            if len(items) == 0:
                print("No files found - service account may not have access to any files")
                return
            
            for file in items:
                file_id = file['id']
                name = file['name']
                print(f"Processing file: {name} ({file_id}) type: {file.get('mimeType')}")
                # Only index Google Docs for demo
                if file.get('mimeType') == 'application/vnd.google-apps.document':
                    try:
                        docs_service = get_docs_service()
                        doc = docs_service.documents().get(documentId=file_id).execute()  # type: ignore[attr-defined]
                        content = extract_text_from_doc(doc)
                        print(f"Indexed Google Doc: {name} (content length: {len(content)})")
                    except Exception as e:
                        print(f"Error indexing {name}: {e}")
                        content = ''
                else:
                    content = ''
                # Compute embedding for name + content
                try:
                    embedding = get_embedding(name + '\n' + content)
                    index.append({'id': file_id, 'name': name, 'content': content, 'embedding': embedding})
                    print(f"Added to index: {name}")
                except Exception as e:
                    print(f"Error creating embedding for {name}: {e}")
        except Exception as e:
            print(f"Error accessing Drive API: {e}")
            print("Service account may not have proper permissions")


################################################################################################################################################################
#   Routes
################################################################################################################################################################


@app.route('/reindex', methods=['POST'])
def reindex():
    try:
        build_index()
        return jsonify({'message': 'Index rebuilt', 'count': len(index)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/list-files', methods=['GET'])
def list_files():
    try:
        service = get_drive_service()
        results = service.files().list(pageSize=10).execute()  # type: ignore[attr-defined]
        items = results.get('files', [])
        return jsonify({'files': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/read-file', methods=['GET'])
def read_file():
    file_id = request.args.get('file_id')
    if not file_id:
        return jsonify({'error': 'file_id is required'}), 400
    try:
        service = get_drive_service()
        file = service.files().get(fileId=file_id, fields='name, mimeType').execute()  # type: ignore[attr-defined]
        mime_type = file['mimeType']
        if mime_type == 'application/vnd.google-apps.document':
            docs_service = get_docs_service()
            doc = docs_service.documents().get(documentId=file_id).execute()  # type: ignore[attr-defined]
            content = '\n'.join([el.get('textRun', {}).get('content', '') for el in doc.get('body', {}).get('content', []) if 'textRun' in el.get('paragraph', {}).get('elements', [{}])[0]])
            return jsonify({'name': file['name'], 'content': content}), 200
        else:
            return jsonify({'error': 'Only Google Docs are supported in this demo.'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create-google-doc', methods=['POST'])
def create_google_doc():
    data = request.get_json()
    title = data.get('title', 'Untitled')
    content = data.get('content', '')
    try:
        docs_service = get_docs_service()
        doc = docs_service.documents().create(body={'title': title}).execute()  # type: ignore[attr-defined]
        doc_id = doc['documentId']
        # Insert content
        if content:
            docs_service.documents().batchUpdate(documentId=doc_id, body={  # type: ignore[attr-defined]
                'requests': [
                    {
                        'insertText': {
                            'location': {'index': 1},
                            'text': content
                        }
                    }
                ]
            }).execute()
        doc_url = f'https://docs.google.com/document/d/{doc_id}/edit'
        return jsonify({'doc_id': doc_id, 'url': doc_url}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Remove the /search endpoint implementation
# (No code for /search should remain)

@app.route('/execute', methods=['POST'])
def execute():
    data = request.get_json()
    command = data.get('command', '').lower()
    if not command:
        return jsonify({'error': 'Missing command'}), 400
    # For demo: if command is about top 100 pet influencers, search and create doc
    if 'top 100 pet influencers' in command:
        with index_lock:
            matches = [doc for doc in index if 'pet influencer' in doc['content'].lower()]
            top_100 = matches[:100]
            content = '\n\n'.join([f"{i+1}. {doc['name']}\n{doc['content'][:300]}" for i, doc in enumerate(top_100)])
        # Create Google Doc
        try:
            docs_service = get_docs_service()
            doc = docs_service.documents().create(body={'title': 'Top 100 Pet Influencers'}).execute()  # type: ignore[attr-defined]
            doc_id = doc['documentId']
            if content:
                docs_service.documents().batchUpdate(documentId=doc_id, body={  # type: ignore[attr-defined]
                    'requests': [
                        {
                            'insertText': {
                                'location': {'index': 1},
                                'text': content
                            }
                        }
                    ]
                }).execute()
            doc_url = f'https://docs.google.com/document/d/{doc_id}/edit'
            return jsonify({'message': 'Created Google Doc with top 100 pet influencers', 'url': doc_url}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Command not recognized in demo'}), 400

@app.route('/debug-index', methods=['GET'])
def debug_index():
    with index_lock:
        # Convert numpy arrays to lists for JSON serialization
        serializable_index = []
        for doc in index:
            serializable_doc = {
                'id': doc['id'],
                'name': doc['name'],
                'content': doc['content'],
                'embedding': doc['embedding'].tolist() if hasattr(doc['embedding'], 'tolist') else doc['embedding']
            }
            serializable_index.append(serializable_doc)
        return jsonify(serializable_index), 200

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get('question', '')
    if not question:
        return jsonify({'error': 'Missing question'}), 400

    # Check if this is a command/action request
    action_keywords = ['write', 'create', 'put', 'make', 'generate', 'build', 'send', 'upload']
    is_action = any(keyword in question.lower() for keyword in action_keywords)
    
    if is_action:
        return execute_action(question)
    return answer_question(question)

def execute_action(command):
    """Handle action commands like creating documents"""
    command_lower = command.lower()
    
    # Check for document creation requests
    if any(word in command_lower for word in ['write', 'create', 'put', 'make']) and any(word in command_lower for word in ['document', 'doc', 'summary']):
        try:
            title = "Document"
            if 'summary' in command_lower:
                title = "Summary Document"
            elif 'report' in command_lower:
                title = "Report"
            elif 'list' in command_lower:
                title = "List"
            
            content = ""
            
            search_keywords = ['find', 'search', 'get', 'list', 'top', 'best', 'all']
            if any(keyword in command_lower for keyword in search_keywords):
                # Search the index for relevant content
                with index_lock:
                    # Simple keyword matching for now
                    relevant_docs = []
                    for doc in index:
                        command_words = command_lower.split()
                        if any(word in doc['content'].lower() or word in doc['name'].lower() for word in command_words if len(word) > 3):
                            relevant_docs.append(doc)
                    
                    if relevant_docs:
                        content = f"Results for: {command}\n\n"
                        for i, doc in enumerate(relevant_docs[:20]):  # Limit to 20 results
                            content += f"{i+1}. {doc['name']}\n{doc['content'][:200]}...\n\n"
                    else:
                        content = f"No relevant documents found for: {command}\n\nThis document was created based on your request."
            else:
                # Generic content for document creation requests
                content = f"Document created based on your request: {command}\n\nThis document contains the information you requested."
            
            # Create the Google Doc
            docs_service = get_docs_service()
            doc = docs_service.documents().create(body={'title': title}).execute()  # type: ignore[attr-defined]
            doc_id = doc['documentId']
            
            if content:
                docs_service.documents().batchUpdate(documentId=doc_id, body={  # type: ignore[attr-defined]
                    'requests': [
                        {
                            'insertText': {
                                'location': {'index': 1},
                                'text': content
                            }
                        }
                    ]
                }).execute()
            
            doc_url = f'https://docs.google.com/document/d/{doc_id}/edit'
            return jsonify({
                'answer': f"I've created a document for you based on your request. You can find it here: {doc_url}"
            }), 200
                
        except Exception as e:
            return jsonify({'error': f'Error creating document: {str(e)}'}), 500
    
    return jsonify({'error': 'Action not recognized. Try asking a question instead.'}), 400

def answer_question(question):
    """Handle question answering - either with document context or general knowledge"""
    if tiktoken is None:
        return jsonify({'error': 'tiktoken is required for token counting. Install with: pip install tiktoken'}), 500

    document_keywords = ['my', 'our', 'this', 'that', 'the', 'in', 'from', 'about', 'regarding', 'concerning']
    has_document_context = any(keyword in question.lower() for keyword in document_keywords)
    
    # Check if the question is about specific files, documents, or personal content
    personal_content_keywords = ['document', 'file', 'drive', 'folder', 'project', 'work', 'company', 'business']
    has_personal_content = any(keyword in question.lower() for keyword in personal_content_keywords)
    
    # If question seems to be about personal documents/content, use document search
    if has_document_context and has_personal_content:
        return answer_with_documents(question)
    else:
        return answer_with_general_knowledge(question)

def answer_with_documents(question):
    """Answer questions using indexed document context"""
    q_embedding = get_embedding(question)
    with index_lock:
        scored = [
            (cosine_similarity(q_embedding, doc['embedding']), doc)
            for doc in index
        ]
        # Limit to top N docs
        MAX_DOCS = 10
        MAX_DOC_CHARS = 1000
        sorted_docs = [doc for score, doc in sorted(scored, key=lambda x: x[0], reverse=True) if score > 0.1][:MAX_DOCS]
        print(f"Top documents for query '{question}':")
        for i, (score, doc) in enumerate(sorted(scored, key=lambda x: x[0], reverse=True)[:3]):
            print(f"  {i+1}. {doc['name']} (similarity: {score:.3f})")
        doc_chunks = [f"{doc['name']}:\n{doc['content'][:MAX_DOC_CHARS]}" for doc in sorted_docs]

    # encode
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")

    base_prompt = (
        "You are an assistant with access to the following documents:\n\n"
        "{context}\n\n"
        "Answer the user's question using ONLY the information from the documents above. "
        "If the answer is not contained in the documents, say 'I don't know based on the provided documents.'\n\n"
        f"User's question: {question}\n"
    )

    context = ""
    n_tokens = 0
    for i in range(len(doc_chunks)):
        candidate_context = "\n\n".join(doc_chunks[:i+1])
        prompt = base_prompt.replace('{context}', candidate_context)
        n_tokens = len(enc.encode(prompt))
        if n_tokens > 7000:
            break
        context = candidate_context

    prompt = base_prompt.replace('{context}', context)
    n_tokens = len(enc.encode(prompt))
    print(f"Prompt tokens: {n_tokens}")
    if n_tokens > 8000:
        return jsonify({'error': 'Prompt too long, please ask a more specific question or reduce document size.'}), 400

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that answers using only the provided documents."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=512,
        temperature=0.2,
    )
    answer = response.choices[0].message.content
    return jsonify({'answer': answer})

def answer_with_general_knowledge(question):
    """Answer questions using ChatGPT's general knowledge"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant with access to general knowledge. Answer questions clearly and accurately."},
                {"role": "user", "content": question}
            ],
            max_tokens=512,
            temperature=0.2,
        )
        answer = response.choices[0].message.content
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': f'Error getting response: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False) 