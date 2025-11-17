"""
Memory Repository Manager

Handles cloning and managing the private memory repository.
"""

import os
import shutil
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from git import Repo, GitCommandError
import logging

logger = logging.getLogger(__name__)


class MemoryRepositoryManager:
    """Manages the memory repository cloning and operations."""
    
    def __init__(self, repo_url: str, repo_path: str, token: Optional[str] = None):
        """
        Initialize the memory repository manager.
        
        Args:
            repo_url: URL of the memory repository
            repo_path: Local path to clone/manage the repository
            token: Authentication token for private repositories
        """
        self.repo_url = repo_url
        self.repo_path = Path(repo_path)
        self.token = token
        self.repo: Optional[Repo] = None
        
        # Prepare URL with token if provided
        self._prepare_repo_url()
    
    def _prepare_repo_url(self) -> None:
        """Prepare repository URL with authentication token if needed."""
        if self.token and self.token not in self.repo_url:
            # Insert token into URL
            if self.repo_url.startswith("https://"):
                # Format: https://token@github.com/user/repo.git
                if "@" not in self.repo_url:
                    self.repo_url = self.repo_url.replace(
                        "https://",
                        f"https://{self.token}@"
                    )
            elif self.repo_url.startswith("git@"):
                # For SSH, token is not used directly
                pass
    
    def clone_or_update(self, force_clone: bool = False) -> bool:
        """
        Clone the repository if it doesn't exist, or update if it does.
        
        Args:
            force_clone: If True, remove existing repo and clone fresh
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if force_clone and self.repo_path.exists():
                logger.info(f"Removing existing repository at {self.repo_path}")
                shutil.rmtree(self.repo_path)
            
            if not self.repo_path.exists():
                logger.info(f"Cloning memory repository from {self.repo_url}")
                self.repo = Repo.clone_from(self.repo_url, self.repo_path)
                logger.info(f"Repository cloned successfully to {self.repo_path}")
            else:
                logger.info(f"Updating existing repository at {self.repo_path}")
                self.repo = Repo(self.repo_path)
                
                # Pull latest changes
                origin = self.repo.remotes.origin
                origin.pull()
                logger.info("Repository updated successfully")
            
            return True
            
        except GitCommandError as e:
            logger.error(f"Git operation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Error managing repository: {e}")
            return False
    
    def get_memory_files(self) -> List[Path]:
        """Get all memory files from the repository."""
        if not self.repo_path.exists():
            return []
        
        memory_files = []
        # Look for common memory file patterns
        patterns = ["*.json", "*.md", "*.txt", "memories/*", "*.yaml", "*.yml"]
        
        for pattern in patterns:
            memory_files.extend(self.repo_path.rglob(pattern))
        
        # Filter out .git directory and other non-memory files
        memory_files = [
            f for f in memory_files
            if ".git" not in str(f) and f.is_file()
        ]
        
        return memory_files
    
    def load_memories(self) -> List[Dict[str, Any]]:
        """
        Load all memories from the repository.
        
        Returns:
            List of memory dictionaries
        """
        memories = []
        memory_files = self.get_memory_files()
        
        for file_path in memory_files:
            try:
                if file_path.suffix == ".json":
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            # Add source information to each memory
                            for memory in data:
                                if "source" not in memory:
                                    memory["source"] = str(file_path.relative_to(self.repo_path))
                                memories.append(memory)
                        elif isinstance(data, dict):
                            if "source" not in data:
                                data["source"] = str(file_path.relative_to(self.repo_path))
                            memories.append(data)
                
                elif file_path.suffix in [".md", ".txt"]:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        memories.append({
                            "content": content,
                            "source": str(file_path.relative_to(self.repo_path)),
                            "file_type": file_path.suffix
                        })
                
            except Exception as e:
                logger.warning(f"Error loading memory from {file_path}: {e}")
                continue
        
        logger.info(f"Loaded {len(memories)} memories from repository")
        return memories
    
    def save_memory(self, memory: Dict[str, Any], filename: Optional[str] = None) -> bool:
        """
        Save a new memory to the repository.
        
        Args:
            memory: Memory dictionary to save
            filename: Optional filename (auto-generated if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.repo_path.exists():
                logger.error("Repository not cloned")
                return False
            
            # Create memories directory if it doesn't exist
            memories_dir = self.repo_path / "memories"
            memories_dir.mkdir(exist_ok=True)
            
            # Generate filename if not provided
            if not filename:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"memory_{timestamp}.json"
            
            file_path = memories_dir / filename
            
            # Load existing memories if file exists
            existing_memories = []
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_memories = json.load(f)
            
            # Add new memory
            existing_memories.append(memory)
            
            # Save
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing_memories, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Memory saved to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            return False
    
    def commit_and_push(self, message: str = "Update memories") -> bool:
        """
        Commit and push changes to the repository.
        
        Args:
            message: Commit message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.repo:
                self.repo = Repo(self.repo_path)
            
            # Add all changes
            self.repo.git.add(A=True)
            
            # Check if there are changes
            if not self.repo.is_dirty() and not self.repo.untracked_files:
                logger.info("No changes to commit")
                return True
            
            # Commit with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full_message = f"{message}\n\nTimestamp: {timestamp}"
            
            self.repo.index.commit(full_message)
            
            # Push to remote
            origin = self.repo.remotes.origin
            origin.push()
            
            logger.info(f"Changes committed and pushed successfully: {message[:50]}")
            return True
            
        except Exception as e:
            logger.error(f"Error committing/pushing: {e}")
            return False
    
    def delete_memory_file(self, source: str) -> bool:
        """
        Delete a memory file from the repository.
        
        Args:
            source: Source path of the memory (relative to repo root)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.repo_path.exists():
                logger.error("Repository not cloned")
                return False
            
            file_path = self.repo_path / source
            
            if not file_path.exists():
                logger.warning(f"Memory file not found: {source}")
                return False
            
            # Delete the file
            file_path.unlink()
            logger.info(f"Deleted memory file: {source}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting memory file: {e}")
            return False
    
    def delete_memory_from_file(self, source: str, memory_id: Optional[str] = None) -> bool:
        """
        Delete a specific memory from a JSON file, or delete the entire file if it's the only memory.
        
        Args:
            source: Source path of the memory file
            memory_id: Optional ID or content to match for deletion
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.repo_path.exists():
                logger.error("Repository not cloned")
                return False
            
            file_path = self.repo_path / source
            
            if not file_path.exists() or file_path.suffix != ".json":
                logger.warning(f"Memory file not found or not JSON: {source}")
                return False
            
            # Load existing memories
            with open(file_path, "r", encoding="utf-8") as f:
                memories = json.load(f)
            
            if not isinstance(memories, list):
                logger.warning(f"Memory file does not contain a list: {source}")
                return False
            
            # Remove matching memories
            original_count = len(memories)
            if memory_id:
                # Match by source or content
                memories = [
                    m for m in memories
                    if m.get("source") != memory_id and str(m.get("content", "")) != str(memory_id)
                ]
            else:
                # If no ID specified, this might be a full file deletion
                memories = []
            
            removed_count = original_count - len(memories)
            
            if removed_count == 0:
                logger.info(f"No matching memories found to delete in {source}")
                return False
            
            # Save updated memories or delete file if empty
            if len(memories) == 0:
                file_path.unlink()
                logger.info(f"Deleted empty memory file: {source}")
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(memories, f, indent=2, ensure_ascii=False)
                logger.info(f"Removed {removed_count} memory(ies) from {source}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting memory from file: {e}")
            return False

