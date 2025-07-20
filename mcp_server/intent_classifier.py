#!/usr/bin/env python3
"""
LLM-based Intent Classification using ChatGPT for MCP endpoint routing
"""

import json
from typing import Dict, Any, Optional
from config import Config
from openai import OpenAI

class LLMIntentClassifier:
    """Intent classification using ChatGPT"""
    
    def __init__(self):
        # Validate configuration
        Config.validate()
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
    
    def classify_intent(self, text: str) -> Dict[str, Any]:
        """
        Classify the intent of a user query using ChatGPT
        
        Returns:
            {
                "intent": "document_search|general_knowledge|create_document|file_management",
                "confidence": 0.95,
                "reasoning": "explanation of classification"
            }
        """
        
        prompt = f"""You are an intent classifier for a Google Drive integration system. 

Classify the user's intent into one of these categories:

1. **document_search** - User wants to find, search, or ask about their personal documents/files
   Examples: "find my documents about AI", "search for files", "what documents do I have", "look through my files"

2. **general_knowledge** - User asks general questions not related to their personal documents
   Examples: "what is machine learning", "explain quantum physics", "how does photosynthesis work"

3. **create_document** - User wants to create, write, generate, or make a new document
   Examples: "create a summary", "write a report", "generate a document", "make a list"

4. **file_management** - User wants to manage files (upload, delete, organize, move)
   Examples: "upload a file", "delete documents", "organize my files", "move files to folder"

User query: "{text}"

Respond with ONLY a valid JSON object:
{{
    "intent": "category_name",
    "confidence": 0.95,
    "reasoning": "Brief explanation of why this intent was chosen"
}}

Be precise and accurate in your classification."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise intent classifier. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            # Parse and validate the JSON
            result_text = (response.choices[0].message.content or "").strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            result = json.loads(result_text)
            valid_intents = ["document_search", "general_knowledge", "create_document", "file_management"]
            if result.get("intent") not in valid_intents:
                # Fallback to general_knowledge if invalid intent
                result = {
                    "intent": "general_knowledge",
                    "confidence": 0.5,
                    "reasoning": f"Invalid intent '{result.get('intent')}' received, defaulting to general_knowledge"
                }
            
            return result
            
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            print(f"JSON parsing error: {e}")
            return {
                "intent": "general_knowledge",
                "confidence": 0.3,
                "reasoning": f"JSON parsing failed: {e}"
            }
        except Exception as e:
            print(f"Intent classification error: {e}")
            return {
                "intent": "general_knowledge",
                "confidence": 0.2,
                "reasoning": f"Classification error: {e}"
            }
    
    def should_use_documents(self, intent_result: Dict[str, Any]) -> bool:
        """Determine if document search should be used based on intent"""
        return intent_result["intent"] == "document_search"
    
    def is_action_request(self, intent_result: Dict[str, Any]) -> bool:
        """Determine if this is an action request (create, manage files)"""
        return intent_result["intent"] in ["create_document", "file_management"]
