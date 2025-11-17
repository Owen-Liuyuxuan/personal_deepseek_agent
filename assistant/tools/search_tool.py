"""
Google Search Tool with dynamic decision making.

Uses LLM to determine if search is needed, then performs search if necessary.
"""

import os
import requests
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from assistant.core.llm_provider import LLMProviderManager

logger = logging.getLogger(__name__)


class SearchInput(BaseModel):
    """Input schema for search tool."""
    query: str = Field(description="The search query to execute")


class GoogleSearchTool(BaseTool):
    """Google Search tool for LangChain."""
    
    name: str = "google_search"
    description: str = "Search Google for current information, news, facts, or recent developments. Use this when the question requires up-to-date information that might not be in the knowledge base."
    args_schema: type[BaseModel] = SearchInput
    
    # Pydantic fields for tool configuration
    api_key: str = Field(description="Google API key")
    cse_id: str = Field(description="Google Custom Search Engine ID")
    
    def __init__(self, api_key: str, cse_id: str):
        """
        Initialize Google Search tool.
        
        Args:
            api_key: Google API key
            cse_id: Google Custom Search Engine ID
        """
        super().__init__(api_key=api_key, cse_id=cse_id)
    
    def _run(self, query: str) -> str:
        """Execute the search."""
        try:
            endpoint = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "num": 5  # Get top 5 results
            }
            
            response = requests.get(endpoint, params=params, timeout=10)
            
            if response.status_code != 200:
                return f"Search failed with status {response.status_code}: {response.text}"
            
            data = response.json()
            results = []
            
            if "items" in data:
                for item in data["items"]:
                    results.append({
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "snippet": item.get("snippet", "")
                    })
            
            if not results:
                return "No search results found."
            
            # Format results
            formatted = "**Search Results:**\n\n"
            for i, result in enumerate(results, 1):
                formatted += f"{i}. **{result['title']}**\n"
                formatted += f"   URL: {result['link']}\n"
                formatted += f"   {result['snippet']}\n\n"
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            return f"Error performing search: {str(e)}"


class SearchDecisionMaker:
    """Uses LLM to determine if a search is needed."""
    
    def __init__(self, llm_manager: LLMProviderManager):
        """
        Initialize search decision maker.
        
        Args:
            llm_manager: LLM provider manager
        """
        self.llm_manager = llm_manager
    
    def should_search(self, question: str, context: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Determine if a search is needed for the question.
        
        Args:
            question: User's question
            context: Additional context (e.g., memories)
            
        Returns:
            Tuple of (should_search: bool, search_query: Optional[str])
        """
        prompt = f"""Analyze the following question and determine if a web search is needed to answer it accurately.

Question: {question}
{f'Context: {context}' if context else ''}

Consider:
1. Does it require CURRENT information (news, weather, current events, recent developments)?
2. Does it ask for SPECIFIC FACTS that might not be in the knowledge base?
3. Does it require REAL-TIME data (stock prices, sports scores, etc.)?
4. Can it be answered with general knowledge or existing context?

Respond with JSON:
{{
    "search_needed": true/false,
    "search_query": "optimized search query" or null,
    "reason": "brief explanation"
}}
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_manager.invoke(messages)
            
            # Parse JSON response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            result = json.loads(response.strip())
            search_needed = result.get("search_needed", False)
            search_query = result.get("search_query") if search_needed else None
            
            logger.info(f"Search decision: {search_needed}, query: {search_query}")
            return search_needed, search_query
            
        except Exception as e:
            logger.error(f"Error determining search need: {e}")
            return False, None

