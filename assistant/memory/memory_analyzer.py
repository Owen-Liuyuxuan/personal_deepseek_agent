"""
Memory Analyzer

Uses LLM to analyze questions and determine:
- What memories to load
- What new memories to add
- What old memories to delete
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from assistant.core.llm_provider import LLMProviderManager
from assistant.memory.memory_store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryAnalyzer:
    """Analyzes questions and manages memory operations."""
    
    def __init__(self, llm_manager: LLMProviderManager, memory_store: MemoryStore):
        """
        Initialize the memory analyzer.
        
        Args:
            llm_manager: LLM provider manager
            memory_store: Memory store instance
        """
        self.llm_manager = llm_manager
        self.memory_store = memory_store
    
    def analyze_question(self, question: str, user: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a question to determine memory operations needed.
        
        Args:
            question: User's question
            user: User identifier
            context: Additional context
            
        Returns:
            Dictionary with analysis results
        """
        # First, load basic memories (always loaded)
        basic_memories = self._load_basic_memories()
        
        # Use LLM to determine what additional memories to load
        relevant_memories = self._determine_relevant_memories(question, basic_memories)
        
        # Determine if new memory should be created
        should_create, memory_content = self._should_create_memory(question, user)
        
        # Determine if old memories should be deleted
        memories_to_delete = self._determine_memories_to_delete(question)
        
        return {
            "basic_memories": basic_memories,
            "relevant_memories": relevant_memories,
            "should_create_memory": (should_create, memory_content),
            "memories_to_delete": memories_to_delete,
            "all_memories": basic_memories + relevant_memories
        }
    
    def _load_basic_memories(self) -> List[Dict[str, Any]]:
        """Load basic memories that should always be available."""
        # Search for general/user profile memories
        basic_docs = self.memory_store.search_memories("user profile preferences general information", k=3)
        
        memories = []
        for doc in basic_docs:
            memories.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "timestamp": doc.metadata.get("timestamp", "")
            })
        
        return memories
    
    def _determine_relevant_memories(self, question: str, basic_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use LLM to determine what additional memories are relevant to the question."""
        # Search vector store for relevant memories
        relevant_docs = self.memory_store.search_memories(question, k=5)
        
        # Filter out duplicates with basic memories
        basic_sources = {m.get("source") for m in basic_memories}
        
        memories = []
        for doc in relevant_docs:
            source = doc.metadata.get("source", "unknown")
            if source not in basic_sources:
                memories.append({
                    "content": doc.page_content,
                    "source": source,
                    "timestamp": doc.metadata.get("timestamp", "")
                })
        
        return memories
    
    def _should_create_memory(self, question: str, user: str) -> Tuple[bool, str]:
        """Determine if a new memory should be created from this interaction.
        
        Returns:
            Tuple of (should_create: bool, memory_content: str)
        """
        prompt = f"""Analyze the following question and determine if it contains information worth remembering for future interactions.

Question: {question}
User: {user}

Consider:
1. Does it contain personal preferences, facts, or important information?
2. Is it a one-time question or something that might be relevant later?
3. Does it establish context about projects, interests, or ongoing work?

Respond with JSON:
{{
    "should_remember": true/false,
    "reason": "brief explanation",
    "memory_content": "what to remember (if should_remember is true)"
}}
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_manager.invoke(messages)
            
            if not response or not response.strip():
                logger.debug("Empty response from LLM for memory creation analysis")
                return False, ""
            
            # Parse JSON response
            response_text = response.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Find JSON object in response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx + 1]
                result = json.loads(json_str)
                should_remember = result.get("should_remember", False)
                memory_content = result.get("memory_content", "")
                return should_remember, memory_content
            else:
                logger.debug("Could not find JSON object in LLM response for memory creation analysis")
                return False, ""
            
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parsing error in memory creation analysis: {e}")
            return False, ""
        except Exception as e:
            logger.warning(f"Error determining memory creation: {e}")
            return False, ""
    
    def _determine_memories_to_delete(self, question: str) -> List[str]:
        """Determine if any old memories should be deleted (e.g., outdated information)."""
        # This is a simplified version - in practice, you'd want more sophisticated logic
        # For now, we'll use LLM to identify potentially outdated memories
        
        prompt = f"""Analyze the following question and determine if it suggests that any existing memories might be outdated or should be deleted.

Question: {question}

Consider if the question:
1. Contradicts previous information
2. Indicates a change in preferences or circumstances
3. Suggests outdated information (e.g., asking for "latest" version implies old version info is outdated)
4. Requests information that would make previous specific claims incorrect

IMPORTANT: For memory_sources_to_delete, provide:
- Specific file paths (e.g., "memories/memory_20251117_131316.json") if you know them, OR
- Clear content descriptions that can be matched (e.g., "memory about PyTorch version 1.13.1 being latest" or "memory stating specific version number")

Respond with JSON:
{{
    "should_delete": true/false,
    "memory_sources_to_delete": ["specific file path or clear content description"] or [],
    "reason": "brief explanation of why these should be deleted"
}}
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_manager.invoke(messages)
            
            if not response or not response.strip():
                logger.debug("Empty response from LLM for memory deletion analysis")
                return []
            
            # Parse JSON response
            response_text = response.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Find JSON object in response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx + 1]
                result = json.loads(json_str)
                memory_sources = result.get("memory_sources_to_delete", [])
                if memory_sources:
                    logger.info(f"LLM identified {len(memory_sources)} memory source(s) to delete")
                return memory_sources
            else:
                # No JSON found, return empty list
                logger.debug("Could not find JSON object in LLM response for memory deletion analysis")
                return []
            
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parsing error in memory deletion analysis: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error determining memories to delete: {e}")
            return []
    
    def format_memories_for_context(self, memories: List[Dict[str, Any]]) -> str:
        """Format memories as context string for LLM."""
        if not memories:
            return ""
        
        context = "## Relevant Memories:\n\n"
        for i, memory in enumerate(memories, 1):
            source = memory.get("source", "unknown")
            content = memory.get("content", "")
            timestamp = memory.get("timestamp", "")
            
            context += f"{i}. **{source}**"
            if timestamp:
                context += f" (from {timestamp})"
            context += f"\n{content}\n\n"
        
        return context

