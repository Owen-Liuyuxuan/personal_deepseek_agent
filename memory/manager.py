# deepseek_chat/memory/manager.py
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

class MemoryManager:
    def __init__(self, memory_file: Optional[str] = None):
        """Initialize memory manager."""
        self.memory_file = memory_file or "memory.json"
        self.memories = self._load_memories()
    
    def _load_memories(self) -> List[Dict[str, Any]]:
        """Load memories from file."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []
    
    def _save_memories(self) -> None:
        """Save memories to file."""
        with open(self.memory_file, "w") as f:
            json.dump(self.memories, f, indent=2)
    
    def add_memory(self, content: str, source: str = "manual") -> None:
        """Add a new memory."""
        memory = {
            "content": content,
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        self.memories.append(memory)
        self._save_memories()
    
    def get_all_memories(self) -> List[Dict[str, Any]]:
        """Get all memories."""
        return self.memories
    
    def remove_memory(self, index: int) -> None:
        """Remove a memory by index."""
        if 0 <= index < len(self.memories):
            del self.memories[index]
            self._save_memories()
    
    def clear_memories(self) -> None:
        """Clear all memories."""
        self.memories = []
        self._save_memories()
    
    def get_memory_prompt(self) -> str:
        """Format memories as a prompt for the AI."""
        if not self.memories:
            return ""
        
        prompt = "Here are some important pieces of information about our previous interactions:\n\n"
        for memory in self.memories:
            prompt += f"- {memory['content']}\n"
        
        prompt += "\nPlease keep this information in mind during our conversation."
        
        return prompt
