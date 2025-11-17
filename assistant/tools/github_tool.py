"""
GitHub Operations Tool

Performs GitHub operations with memory of different repositories.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from github import Github
from github.GithubException import GithubException

from assistant.core.llm_provider import LLMProviderManager

logger = logging.getLogger(__name__)


class GitHubOperationInput(BaseModel):
    """Input schema for GitHub operations."""
    operation: str = Field(description="Operation to perform: 'list_repos', 'get_repo_info', 'create_issue', 'list_issues', 'get_file_content'")
    repository: Optional[str] = Field(default=None, description="Repository name (owner/repo)")
    issue_title: Optional[str] = Field(default=None, description="Issue title (for create_issue)")
    issue_body: Optional[str] = Field(default=None, description="Issue body (for create_issue)")
    file_path: Optional[str] = Field(default=None, description="File path (for get_file_content)")
    branch: Optional[str] = Field(default="main", description="Branch name (for get_file_content)")


class GitHubTool(BaseTool):
    """GitHub operations tool for LangChain."""
    
    name: str = "github_operations"
    description: str = """Perform GitHub operations. Available operations:
    - list_repos: List all repositories accessible to the user
    - get_repo_info: Get information about a specific repository
    - create_issue: Create an issue in a repository
    - list_issues: List issues in a repository
    - get_file_content: Get content of a file from a repository
    """
    args_schema: type[BaseModel] = GitHubOperationInput
    
    # Pydantic fields for tool configuration
    token: str = Field(description="GitHub personal access token")
    memory_store: Optional[Any] = Field(default=None, description="Optional memory store")
    
    def __init__(self, token: str, memory_store: Optional[Any] = None):
        """
        Initialize GitHub tool.
        
        Args:
            token: GitHub personal access token
            memory_store: Optional memory store to remember repository information
        """
        super().__init__(token=token, memory_store=memory_store)
        # Initialize non-Pydantic attributes after super().__init__
        # Use object.__setattr__ to bypass Pydantic validation for non-field attributes
        object.__setattr__(self, 'github', Github(token))
        self._load_repo_memories()
    
    def _load_repo_memories(self) -> None:
        """Load memories about repositories."""
        # memory_store is a Pydantic field, so we can access it normally
        if self.memory_store:
            # Search for repository-related memories
            repo_memories = self.memory_store.search_memories("github repository", k=10)
            object.__setattr__(self, 'repo_memories', {doc.metadata.get("source"): doc.page_content for doc in repo_memories})
        else:
            object.__setattr__(self, 'repo_memories', {})
    
    def _save_repo_memory(self, repo_name: str, info: str) -> None:
        """Save repository information to memory."""
        if self.memory_store:
            memory = {
                "content": f"Repository {repo_name}: {info}",
                "source": f"github_repo_{repo_name}",
                "timestamp": datetime.now().isoformat(),
                "file_type": "github"
            }
            # This would need to be implemented in memory_store
            logger.info(f"Would save memory for repo {repo_name}")
    
    def _run(self, operation: str, repository: Optional[str] = None, 
             issue_title: Optional[str] = None, issue_body: Optional[str] = None,
             file_path: Optional[str] = None, branch: str = "main") -> str:
        """Execute the GitHub operation."""
        try:
            if operation == "list_repos":
                return self._list_repos()
            elif operation == "get_repo_info":
                if not repository:
                    return "Error: repository parameter required for get_repo_info"
                return self._get_repo_info(repository)
            elif operation == "create_issue":
                if not repository or not issue_title:
                    return "Error: repository and issue_title required for create_issue"
                return self._create_issue(repository, issue_title, issue_body or "")
            elif operation == "list_issues":
                if not repository:
                    return "Error: repository parameter required for list_issues"
                return self._list_issues(repository)
            elif operation == "get_file_content":
                if not repository or not file_path:
                    return "Error: repository and file_path required for get_file_content"
                return self._get_file_content(repository, file_path, branch)
            else:
                return f"Unknown operation: {operation}"
                
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return f"GitHub API error: {e.data.get('message', str(e))}"
        except Exception as e:
            logger.error(f"Error performing GitHub operation: {e}")
            return f"Error: {str(e)}"
    
    def _list_repos(self) -> str:
        """List all repositories."""
        try:
            repos = []
            for repo in self.github.get_user().get_repos():
                repos.append({
                    "name": repo.full_name,
                    "description": repo.description or "",
                    "language": repo.language or "",
                    "stars": repo.stargazers_count,
                    "private": repo.private
                })
            
            if not repos:
                return "No repositories found."
            
            result = "**Repositories:**\n\n"
            for repo in repos[:20]:  # Limit to 20
                result += f"- **{repo['name']}**"
                if repo['private']:
                    result += " (private)"
                result += f"\n  {repo['description']}\n"
                result += f"  Language: {repo['language']}, Stars: {repo['stars']}\n\n"
            
            return result
            
        except Exception as e:
            return f"Error listing repositories: {str(e)}"
    
    def _get_repo_info(self, repo_name: str) -> str:
        """Get information about a repository."""
        try:
            repo = self.github.get_repo(repo_name)
            
            info = {
                "name": repo.full_name,
                "description": repo.description or "",
                "language": repo.language or "",
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count,
                "created_at": repo.created_at.isoformat(),
                "updated_at": repo.updated_at.isoformat(),
                "default_branch": repo.default_branch,
                "private": repo.private
            }
            
            # Save to memory
            self._save_repo_memory(repo_name, json.dumps(info, indent=2))
            
            result = f"**Repository: {info['name']}**\n\n"
            result += f"Description: {info['description']}\n"
            result += f"Language: {info['language']}\n"
            result += f"Stars: {info['stars']}, Forks: {info['forks']}\n"
            result += f"Open Issues: {info['open_issues']}\n"
            result += f"Default Branch: {info['default_branch']}\n"
            result += f"Created: {info['created_at']}\n"
            result += f"Updated: {info['updated_at']}\n"
            
            return result
            
        except Exception as e:
            return f"Error getting repository info: {str(e)}"
    
    def _create_issue(self, repo_name: str, title: str, body: str) -> str:
        """Create an issue in a repository."""
        try:
            repo = self.github.get_repo(repo_name)
            issue = repo.create_issue(title=title, body=body)
            
            return f"Issue created successfully:\n- Number: {issue.number}\n- URL: {issue.html_url}\n- Title: {issue.title}"
            
        except Exception as e:
            return f"Error creating issue: {str(e)}"
    
    def _list_issues(self, repo_name: str, state: str = "open") -> str:
        """List issues in a repository."""
        try:
            repo = self.github.get_repo(repo_name)
            issues = repo.get_issues(state=state)
            
            result = f"**Issues ({state}):**\n\n"
            count = 0
            for issue in issues[:10]:  # Limit to 10
                result += f"#{issue.number}: {issue.title}\n"
                result += f"  URL: {issue.html_url}\n"
                if issue.body:
                    body_preview = issue.body[:100] + "..." if len(issue.body) > 100 else issue.body
                    result += f"  {body_preview}\n"
                result += "\n"
                count += 1
            
            if count == 0:
                return f"No {state} issues found."
            
            return result
            
        except Exception as e:
            return f"Error listing issues: {str(e)}"
    
    def _get_file_content(self, repo_name: str, file_path: str, branch: str = "main") -> str:
        """Get content of a file from a repository."""
        try:
            repo = self.github.get_repo(repo_name)
            file_content = repo.get_contents(file_path, ref=branch)
            
            if file_content.encoding == "base64":
                import base64
                content = base64.b64decode(file_content.content).decode("utf-8")
            else:
                content = file_content.content
            
            result = f"**File: {file_path} (branch: {branch})**\n\n"
            result += f"```\n{content}\n```"
            
            return result
            
        except Exception as e:
            return f"Error getting file content: {str(e)}"

