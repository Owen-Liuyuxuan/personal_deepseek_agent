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
    
    def _mask_url(self, url: str) -> str:
        """Mask sensitive information in URL for logging."""
        if "@" in url:
            parts = url.split("@")
            if len(parts) == 2:
                return f"{parts[0][:10]}***@{parts[1]}"
        return url
    
    def _prepare_repo_url(self) -> None:
        """Prepare repository URL with authentication token if needed."""
        if not self.token:
            return
        
        # Check if URL already contains a token (common patterns: ghp_, github_pat_, or x-access-token)
        if "@" in self.repo_url:
            # Check if there's already a token-like pattern before @
            parts = self.repo_url.split("@", 1)
            if len(parts) == 2:
                before_at = parts[0].lower()
                # If it already looks like a token, don't modify
                if any(pattern in before_at for pattern in ["ghp_", "github_pat_", "x-access-token", "oauth"]):
                    logger.debug("URL already contains a token pattern, skipping token insertion")
                    return
                # If it's just a username, replace it with token
                # Extract the part after @
                url_after_at = parts[1]
                # Remove https:// if present
                if url_after_at.startswith("https://"):
                    url_after_at = url_after_at.replace("https://", "")
                self.repo_url = f"https://{self.token}@{url_after_at}"
                logger.debug("Replaced existing username with token in URL")
                return
        
        # Insert token into URL if it doesn't have one
        if self.repo_url.startswith("https://"):
            # GitHub requires the token to be used as the username
            # Format: https://TOKEN@github.com/user/repo.git
            # Remove https:// prefix
            url_without_prefix = self.repo_url.replace("https://", "")
            # Insert token as username (GitHub uses token as username, no password)
            self.repo_url = f"https://{self.token}@{url_without_prefix}"
            logger.debug("Token inserted into repository URL")
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
                # Log the masked URL for security
                masked_url = self._mask_url(self.repo_url)
                logger.info(f"Cloning memory repository from {masked_url}")
                logger.debug(f"Full repo URL format: https://TOKEN@github.com/user/repo")
                # Configure Git to avoid credential prompts in CI/CD
                import subprocess
                import os
                
                # Set Git environment variables to avoid interactive prompts
                env = os.environ.copy()
                env['GIT_TERMINAL_PROMPT'] = '0'
                env['GIT_ASKPASS'] = 'echo'
                
                # Configure Git globally to avoid prompts
                subprocess.run(
                    ['git', 'config', '--global', 'credential.helper', 'store'],
                    check=False,
                    capture_output=True,
                    env=env
                )
                
                # Clone repository
                # Note: GitPython's clone_from doesn't support env parameter directly,
                # so we set environment variables before calling it
                original_env = {}
                for key in ['GIT_TERMINAL_PROMPT', 'GIT_ASKPASS']:
                    if key in env:
                        original_env[key] = os.environ.get(key)
                        os.environ[key] = env[key]
                
                try:
                    # Log the actual URL format for debugging (masked)
                    logger.debug(f"Attempting to clone with URL format: https://TOKEN@github.com/...")
                    self.repo = Repo.clone_from(self.repo_url, self.repo_path)
                    logger.info(f"Repository cloned successfully to {self.repo_path}")
                except Exception as clone_error:
                    # Log more details about the error
                    error_msg = str(clone_error)
                    logger.error(f"Failed to clone repository: {error_msg}")
                    # Check if it's an authentication error
                    if "Authentication failed" in error_msg or "Invalid username or token" in error_msg:
                        logger.error("Git authentication failed. Please check:")
                        logger.error("1. MEMORY_REPO_TOKEN is set correctly")
                        logger.error("2. Token has 'repo' scope for private repositories")
                        logger.error("3. URL format is correct: https://TOKEN@github.com/user/repo")
                        # Try to provide helpful error message
                        if self.token:
                            token_preview = self.token[:10] + "..." if len(self.token) > 10 else "***"
                            logger.error(f"Token preview: {token_preview} (length: {len(self.token)})")
                            # Check if token looks valid
                            if not (self.token.startswith("ghp_") or self.token.startswith("github_pat_") or len(self.token) > 20):
                                logger.warning("Token format might be incorrect. GitHub tokens usually start with 'ghp_' or 'github_pat_'")
                    raise
                finally:
                    # Restore original environment
                    for key, value in original_env.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value
            else:
                logger.info(f"Updating existing repository at {self.repo_path}")
                self.repo = Repo(self.repo_path)
                
                # Update remote URL if token changed
                if self.token:
                    origin = self.repo.remotes.origin
                    current_url = origin.url
                    if self.token not in current_url:
                        # Update remote URL with token
                        new_url = self.repo_url
                        origin.set_url(new_url)
                        logger.debug("Updated remote URL with token")
                
                # Pull latest changes with environment to avoid prompts
                import os
                env = os.environ.copy()
                env['GIT_TERMINAL_PROMPT'] = '0'
                env['GIT_ASKPASS'] = 'echo'
                
                # Set environment variables for Git operations
                original_env = {}
                for key in ['GIT_TERMINAL_PROMPT', 'GIT_ASKPASS']:
                    if key in env:
                        original_env[key] = os.environ.get(key)
                        os.environ[key] = env[key]
                
                try:
                    origin = self.repo.remotes.origin
                    origin.pull()
                    logger.info("Repository updated successfully")
                finally:
                    # Restore original environment
                    for key, value in original_env.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value
            
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

