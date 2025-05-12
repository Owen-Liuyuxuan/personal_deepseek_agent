# deepseek_chat/api/search.py
import os
import requests
import json
from typing import List, Dict, Any, Optional

class GoogleSearchClient:
    def __init__(self, api_key: Optional[str] = None, cse_id: Optional[str] = None):
        """Initialize Google Search API client."""
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.cse_id = cse_id or os.environ.get("GOOGLE_CSE_ID")
        
        if not self.api_key:
            raise ValueError("Google API key not provided. Set GOOGLE_API_KEY environment variable or pass as parameter.")
        if not self.cse_id:
            raise ValueError("Google CSE ID not provided. Set GOOGLE_CSE_ID environment variable or pass as parameter.")
    
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Perform a Google search with the given query."""
        endpoint = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(num_results, 10)  # Google API allows max 10 results per query
        }
        
        response = requests.get(endpoint, params=params)
        
        if response.status_code != 200:
            raise Exception(f"Google search failed with status {response.status_code}: {response.text}")
        
        results = []
        data = response.json()
        
        if "items" in data:
            for item in data["items"]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })
        
        return results

    def format_search_results(self, results: List[Dict[str, str]]) -> str:
        """Format search results for inclusion in conversation."""
        if not results:
            return "No search results found."
        
        formatted = "**Search Results:**\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"{i}. [{result['title']}]({result['link']})\n"
            formatted += f"   {result['snippet']}\n\n"
        
        return formatted
