"""
Tests for tool functionality.
"""

import pytest
from unittest.mock import Mock, patch
from assistant.tools.search_tool import GoogleSearchTool, SearchDecisionMaker
from assistant.tools.github_tool import GitHubTool
from assistant.core.llm_provider import LLMProviderManager
from assistant.core.config import Config


class TestGoogleSearchTool:
    """Test Google Search tool."""
    
    def test_search_tool_initialization(self):
        """Test search tool initialization."""
        tool = GoogleSearchTool(api_key="test-key", cse_id="test-cse")
        assert tool.name == "google_search"
        assert tool.api_key == "test-key"
        assert tool.cse_id == "test-cse"
    
    @patch('assistant.tools.search_tool.requests.get')
    def test_search_execution(self, mock_get):
        """Test search execution."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "Test Result",
                    "link": "https://test.com",
                    "snippet": "Test snippet"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        tool = GoogleSearchTool(api_key="test-key", cse_id="test-cse")
        result = tool._run("test query")
        
        assert "Test Result" in result
        assert "https://test.com" in result
        mock_get.assert_called_once()


class TestSearchDecisionMaker:
    """Test search decision maker."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        import os
        os.environ["FEISHU_WEBHOOK_URL"] = "https://test.url"
        os.environ["LLM_PROVIDER"] = "deepseek"
        os.environ["DEEPSEEK_API_KEY"] = "test-key"
        
        config = Config()
        yield config
        
        for var in ["FEISHU_WEBHOOK_URL", "LLM_PROVIDER", "DEEPSEEK_API_KEY"]:
            if var in os.environ:
                del os.environ[var]
    
    @pytest.fixture
    def llm_manager(self, config):
        """Create a mock LLM manager."""
        # We'll skip actual LLM initialization for unit tests
        with patch('assistant.core.llm_provider.LLMProviderManager._initialize_llm'):
            manager = LLMProviderManager(config)
            # Mock the invoke method
            manager.invoke = Mock(return_value='{"search_needed": false, "search_query": null}')
            return manager
    
    def test_should_search(self, llm_manager):
        """Test search decision making."""
        decision_maker = SearchDecisionMaker(llm_manager)
        should_search, query = decision_maker.should_search("What is Python?")
        
        # Should call the LLM
        assert llm_manager.invoke.called


class TestGitHubTool:
    """Test GitHub tool."""
    
    def test_github_tool_initialization(self):
        """Test GitHub tool initialization."""
        tool = GitHubTool(token="test-token")
        assert tool.name == "github_operations"
        assert tool.github is not None
    
    @patch('assistant.tools.github_tool.Github')
    def test_list_repos(self, mock_github):
        """Test listing repositories."""
        # Mock GitHub API
        mock_user = Mock()
        mock_repo = Mock()
        mock_repo.full_name = "test/repo"
        mock_repo.description = "Test repo"
        mock_repo.language = "Python"
        mock_repo.stargazers_count = 10
        mock_repo.private = False
        
        mock_user.get_repos.return_value = [mock_repo]
        mock_github.return_value.get_user.return_value = mock_user
        
        tool = GitHubTool(token="test-token")
        result = tool._run("list_repos")
        
        assert "test/repo" in result
        assert "Python" in result

