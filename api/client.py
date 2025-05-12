# deepseek_chat/api/client.py
import os
import requests
from typing import List, Dict, Any, Optional, Tuple, Union
import json
import datetime

class DeepseekClient:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Deepseek API client."""
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("Deepseek API key not provided. Set DEEPSEEK_API_KEY environment variable or pass as parameter.")
        
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def chat_completion(self, 
                        messages: List[Dict[str, str]], 
                        model: str = "deepseek-chat", 
                        temperature: float = 0.7,
                        max_tokens: int = 1000) -> Dict[str, Any]:
        """Send a chat completion request to Deepseek API."""
        endpoint = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        response = requests.post(endpoint, headers=self.headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status {response.status_code}: {response.text}")
        
        return response.json()
    
    def detect_search_need(self, user_query: str, model: str = "deepseek-chat") -> Tuple[bool, Optional[str]]:
        """Detect if a search is needed for the given user query."""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        system_message = {
            "role": "system", 
            "content": (
                f"Current time: {current_time}\n\n"
                "You are a helpful assistant that determines if a web search is needed to answer user queries accurately. "
                "Evaluate the query and determine:\n"
                "1. If it likely requires CURRENT information (e.g., news, weather, current events)\n"
                "2. If it contains requests for SPECIFIC FACTS you might not know\n"
                "3. If it asks about RECENT developments or products\n"
                "Output a JSON object with two fields:\n"
                "- 'search_needed': true/false\n"
                "- 'search_query': optimized search terms if search is needed, null otherwise"
            )
        }
        
        
        user_message = {
            "role": "user",
            "content": f"Query: {user_query}"
        }
        
        response = self.chat_completion(
            messages=[system_message, user_message],
            model=model,
            temperature=0.1
        )
        
        try:
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            # Extract JSON from the potentially messy content
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
            return result.get("search_needed", False), result.get("search_query")
        except json.JSONDecodeError:
            # If we can't parse the JSON, default to not searching
            return False, None
    
    def extract_memory(self, 
                       chat_history: List[Dict[str, str]], 
                       model: str = "deepseek-chat") -> str:
        """Extract a memory summary from chat history using Deepseek API."""
        # Create a system message specifically for memory extraction
        system_message = {
            "role": "system", 
            "content": (
                "Your task is to extract important information from the following conversation "
                "that would be valuable to remember for future interactions. "
                "Focus on preferences, interests, facts about the user, and ongoing projects. "
                "Format your response as a single, concise bullet point (starting with •) "
                "that captures key information without explanations or meta-commentary. "
                "Keep it under 200 characters. Example: • User is working on a Python project "
                "with Deepseek API integration and prefers detailed technical explanations."
            )
        }
        
        # Create a user message containing the chat history
        user_message = {
            "role": "user",
            "content": "Here is the conversation to extract memory from:\n\n" + 
                      "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        }
        
        # Call the API with these messages
        response = self.chat_completion(
            messages=[system_message, user_message],
            model=model,
            temperature=0.3,  # Lower temperature for more focused extraction
            max_tokens=200
        )
        
        # Extract and return the memory
        memory_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return memory_text.strip()
    
    def detect_file_creation(self, response_content: str) -> List[Dict[str, str]]:
        """Parse the response to detect file creation directives."""
        system_message = {
            "role": "system", 
            "content": (
                "Analyze the following assistant response and identify any file creation directives. "
                "A file creation directive is indicated by triple backticks followed by a file type and filename, "
                "and content enclosed within the backticks. Example: ```python:app.py\ndef hello():\n    print('Hello')\n```\n"
                "For each file found, output a JSON object with 'filename', 'file_type', and 'content' fields. "
                "Return an array of these objects, or an empty array if no files are found."
            )
        }
        
        user_message = {
            "role": "user",
            "content": f"Assistant response: {response_content}"
        }
        
        response = self.chat_completion(
            messages=[system_message, user_message],
            model="deepseek-chat",
            temperature=0.1
        )
        
        try:
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "[]")
            # Extract JSON from the potentially messy content
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
            if isinstance(result, list):
                return result
            return []
        except json.JSONDecodeError:
            return []
