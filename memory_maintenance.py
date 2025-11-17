#!/usr/bin/env python3
"""
Memory Maintenance Script

Maintains the memory repository by:
1. Categorizing memories into "solid instructions" and "simple talks"
2. Extracting important information from simple talks
3. Integrating simple talks into a dynamic memory file
4. Cleaning up redundant memories
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

from assistant.core.config import Config
from assistant.core.llm_provider import LLMProviderManager
from assistant.memory.repository_manager import MemoryRepositoryManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MemoryMaintainer:
    """Maintains and organizes memory repository."""
    
    def __init__(self, config: Config):
        """
        Initialize memory maintainer.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.llm_manager = LLMProviderManager(config)
        self.repo_manager = MemoryRepositoryManager(
            repo_url=config.memory_repo_url,
            repo_path=config.memory_repo_path,
            token=config.memory_repo_token
        )
        self.repo_path = Path(config.memory_repo_path)
        self.dynamic_memory_file = self.repo_path / "dynamic_memory.json"
    
    def load_all_memories(self) -> List[Dict[str, Any]]:
        """Load all memories from the repository."""
        logger.info("Loading all memories from repository...")
        
        # Ensure repository is up to date
        self.repo_manager.clone_or_update()
        
        memories = []
        memories_dir = self.repo_path / "memories"
        
        if not memories_dir.exists():
            logger.warning(f"Memories directory not found: {memories_dir}")
            return memories
        
        # Load all JSON memory files
        for memory_file in memories_dir.glob("memory_*.json"):
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    memory_data = json.load(f)
                    # Add file path for tracking
                    if isinstance(memory_data, dict):
                        memory_data['_file_path'] = str(memory_file)
                        memories.append(memory_data)
                    elif isinstance(memory_data, list):
                        for item in memory_data:
                            if isinstance(item, dict):
                                item['_file_path'] = str(memory_file)
                                memories.append(item)
            except Exception as e:
                logger.error(f"Error loading memory file {memory_file}: {e}")
        
        logger.info(f"Loaded {len(memories)} memories from repository")
        return memories
    
    def categorize_memory(self, memory: Dict[str, Any]) -> Tuple[str, str]:
        """
        Categorize a memory using LLM.
        
        Args:
            memory: Memory dictionary
            
        Returns:
            Tuple of (category, reasoning)
            category: "solid_instruction" or "simple_talk"
        """
        content = memory.get("content", "")
        source = memory.get("source", "unknown")
        timestamp = memory.get("timestamp", "")
        
        prompt = f"""Analyze the following memory and categorize it:

Memory Content: {content}
Source: {source}
Timestamp: {timestamp}

Categorize this memory into one of two categories:
1. "solid_instruction" - Contains important instructions, preferences, facts, or information that should be preserved as-is
2. "simple_talk" - Contains casual conversation, testing, or simple interactions that can be integrated into a summary

Consider:
- Does it contain actionable instructions or important facts?
- Is it a preference or setting that should be remembered?
- Is it just casual conversation or testing?
- Does it have lasting value or is it transient?

Respond with JSON:
{{
    "category": "solid_instruction" or "simple_talk",
    "reasoning": "brief explanation of why",
    "has_important_info": true/false,
    "important_info": "extracted important information if has_important_info is true, otherwise null"
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
            category = result.get("category", "simple_talk")
            reasoning = result.get("reasoning", "")
            has_important_info = result.get("has_important_info", False)
            important_info = result.get("important_info")
            
            logger.debug(f"Memory categorized as {category}: {reasoning}")
            
            return category, reasoning, has_important_info, important_info
            
        except Exception as e:
            logger.error(f"Error categorizing memory: {e}")
            # Default to simple_talk if categorization fails
            return "simple_talk", f"Error during categorization: {e}", False, None
    
    def extract_important_info(self, memories: List[Dict[str, Any]]) -> str:
        """
        Extract and integrate important information from simple talk memories.
        
        Args:
            memories: List of simple talk memories
            
        Returns:
            Integrated summary of important information
        """
        if not memories:
            return ""
        
        logger.info(f"Extracting important information from {len(memories)} simple talk memories...")
        
        # Prepare memory summaries for LLM
        memory_summaries = []
        for i, memory in enumerate(memories, 1):
            content = memory.get("content", "")
            timestamp = memory.get("timestamp", "")
            source = memory.get("source", "")
            memory_summaries.append(f"Memory {i} ({timestamp}):\n{content}\nSource: {source}\n")
        
        memories_text = "\n---\n".join(memory_summaries)
        
        prompt = f"""Analyze the following simple talk memories and extract all important information.
        
These are casual conversations or testing interactions. Extract:
- Important facts mentioned
- Preferences expressed
- Questions asked and answers given
- Any actionable information
- User characteristics or patterns

Ignore:
- Generic greetings
- Pure testing without substance
- Redundant information already captured

Memories:
{memories_text}

Provide a comprehensive summary that integrates all important information from these memories.
Focus on extracting facts, preferences, and useful information, not the conversation flow itself.
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_manager.invoke(messages)
            logger.info(f"Extracted important information, length: {len(response)} chars")
            return response.strip()
        except Exception as e:
            logger.error(f"Error extracting important information: {e}")
            return ""
    
    def load_dynamic_memory(self) -> Dict[str, Any]:
        """Load existing dynamic memory file."""
        if self.dynamic_memory_file.exists():
            try:
                with open(self.dynamic_memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading dynamic memory: {e}")
        
        # Return default structure
        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "integrated_info": "",
            "source_memories_count": 0,
            "update_history": []
        }
    
    def save_dynamic_memory(self, dynamic_memory: Dict[str, Any]) -> None:
        """Save dynamic memory file."""
        try:
            with open(self.dynamic_memory_file, 'w', encoding='utf-8') as f:
                json.dump(dynamic_memory, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved dynamic memory to {self.dynamic_memory_file}")
        except Exception as e:
            logger.error(f"Error saving dynamic memory: {e}")
            raise
    
    def integrate_simple_talks(self, simple_talk_memories: List[Dict[str, Any]]) -> str:
        """
        Integrate simple talk memories into dynamic memory.
        
        Args:
            simple_talk_memories: List of simple talk memories to integrate
            
        Returns:
            Updated integrated information
        """
        if not simple_talk_memories:
            logger.info("No simple talk memories to integrate")
            return ""
        
        # Load existing dynamic memory
        dynamic_memory = self.load_dynamic_memory()
        existing_info = dynamic_memory.get("integrated_info", "")
        
        # Extract important information from new simple talks
        new_info = self.extract_important_info(simple_talk_memories)
        
        if not new_info:
            logger.warning("No important information extracted from simple talks")
            return existing_info
        
        # Integrate with existing information
        if existing_info:
            integration_prompt = f"""Integrate the following new information with existing integrated information.

Existing Integrated Information:
{existing_info}

New Information to Integrate:
{new_info}

Provide a comprehensive, integrated summary that:
- Combines both sets of information
- Removes redundancy
- Maintains all important facts and preferences
- Organizes information logically
- Updates any conflicting information with the newer data
"""
            try:
                messages = [{"role": "user", "content": integration_prompt}]
                integrated_info = self.llm_manager.invoke(messages)
                logger.info("Successfully integrated new information with existing")
                return integrated_info.strip()
            except Exception as e:
                logger.error(f"Error integrating information: {e}")
                # Fallback: append new info
                return f"{existing_info}\n\n---\n\n{new_info}"
        else:
            return new_info
    
    def delete_memory_files(self, memory_files: List[str]) -> None:
        """
        Delete memory files from repository.
        
        Args:
            memory_files: List of file paths to delete
        """
        for file_path in memory_files:
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    logger.info(f"Deleted memory file: {path.name}")
            except Exception as e:
                logger.error(f"Error deleting memory file {file_path}: {e}")
    
    def maintain_memories(self) -> Dict[str, Any]:
        """
        Main maintenance function.
        
        Returns:
            Dictionary with maintenance results
        """
        logger.info("Starting memory maintenance...")
        
        # Load all memories
        all_memories = self.load_all_memories()
        
        if not all_memories:
            logger.info("No memories to maintain")
            return {
                "status": "success",
                "total_memories": 0,
                "solid_instructions": 0,
                "simple_talks": 0,
                "deleted_files": 0
            }
        
        # Categorize memories
        solid_instructions = []
        simple_talks = []
        
        logger.info(f"Categorizing {len(all_memories)} memories...")
        for memory in all_memories:
            category, reasoning, has_important_info, important_info = self.categorize_memory(memory)
            
            if category == "solid_instruction":
                solid_instructions.append(memory)
                logger.debug(f"Solid instruction: {memory.get('source', 'unknown')} - {reasoning}")
            else:
                simple_talks.append(memory)
                logger.debug(f"Simple talk: {memory.get('source', 'unknown')} - {reasoning}")
        
        logger.info(f"Categorized: {len(solid_instructions)} solid instructions, {len(simple_talks)} simple talks")
        
        # Integrate simple talks into dynamic memory
        if simple_talks:
            logger.info("Integrating simple talks into dynamic memory...")
            integrated_info = self.integrate_simple_talks(simple_talks)
            
            # Update dynamic memory
            dynamic_memory = self.load_dynamic_memory()
            dynamic_memory["integrated_info"] = integrated_info
            dynamic_memory["last_updated"] = datetime.now().isoformat()
            dynamic_memory["source_memories_count"] = dynamic_memory.get("source_memories_count", 0) + len(simple_talks)
            dynamic_memory["update_history"].append({
                "timestamp": datetime.now().isoformat(),
                "memories_integrated": len(simple_talks),
                "integrated_info_length": len(integrated_info)
            })
            
            self.save_dynamic_memory(dynamic_memory)
            
            # Get unique file paths to delete
            files_to_delete = list(set(memory.get("_file_path", "") for memory in simple_talks if memory.get("_file_path")))
            
            # Delete simple talk memory files
            if files_to_delete:
                logger.info(f"Deleting {len(files_to_delete)} simple talk memory files...")
                self.delete_memory_files(files_to_delete)
                
                # Commit and push changes
                try:
                    commit_message = f"Memory maintenance: Integrated {len(simple_talks)} simple talks into dynamic memory, deleted {len(files_to_delete)} files"
                    self.repo_manager.commit_and_push(commit_message)
                    logger.info("Changes committed and pushed to repository")
                except Exception as e:
                    logger.error(f"Error committing changes: {e}")
        else:
            logger.info("No simple talks to integrate")
        
        return {
            "status": "success",
            "total_memories": len(all_memories),
            "solid_instructions": len(solid_instructions),
            "simple_talks": len(simple_talks),
            "deleted_files": len(set(memory.get("_file_path", "") for memory in simple_talks if memory.get("_file_path"))),
            "dynamic_memory_updated": len(simple_talks) > 0
        }


def main():
    """Main entry point."""
    logger.info("Starting memory maintenance script...")
    
    # Initialize configuration
    config = Config()
    
    # Validate configuration
    validation = config.validate()
    if not validation["valid"]:
        logger.error(f"Configuration validation failed. Missing: {validation['missing']}")
        sys.exit(1)
    
    # Check required configuration
    if not config.memory_repo_url:
        logger.error("MEMORY_REPO_URL is required")
        sys.exit(1)
    
    if not config.llm_provider:
        logger.error("LLM_PROVIDER is required")
        sys.exit(1)
    
    try:
        # Initialize maintainer
        maintainer = MemoryMaintainer(config)
        
        # Run maintenance
        results = maintainer.maintain_memories()
        
        logger.info("Memory maintenance completed successfully")
        logger.info(f"Results: {json.dumps(results, indent=2)}")
        
        print(json.dumps(results, indent=2))
        
    except Exception as e:
        logger.error(f"Memory maintenance failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

