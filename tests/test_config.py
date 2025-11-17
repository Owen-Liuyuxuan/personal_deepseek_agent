"""
Tests for configuration management.
"""

import os
import pytest
from assistant.core.config import Config, LLMProvider


class TestConfig:
    """Test configuration management."""
    
    def test_config_defaults(self):
        """Test default configuration values."""
        # Clear environment variables
        env_vars = [
            "LLM_PROVIDER", "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
            "GEMINI_API_KEY", "FEISHU_WEBHOOK_URL"
        ]
        original_values = {}
        for var in env_vars:
            original_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]
        
        try:
            config = Config()
            
            # Test defaults
            assert config.llm_provider == LLMProvider.DEEPSEEK.value
            assert config.deepseek_model == "deepseek-chat"
            assert config.openai_model == "gpt-4o-mini"
            assert config.gemini_model == "gemini-2.5-flash"
            assert config.temperature == 0.1
            assert config.max_tokens == 5000
            assert config.memory_repo_path == "./memory_repo"
            
        finally:
            # Restore environment variables
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value
    
    def test_config_from_env(self):
        """Test configuration from environment variables."""
        # Set test environment variables
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "test-key-123"
        os.environ["OPENAI_MODEL"] = "gpt-4"
        os.environ["FEISHU_WEBHOOK_URL"] = "https://test.webhook.url"
        os.environ["TEMPERATURE"] = "0.5"
        os.environ["MAX_TOKENS"] = "1000"
        
        try:
            config = Config()
            
            assert config.llm_provider == "openai"
            assert config.openai_api_key == "test-key-123"
            assert config.openai_model == "gpt-4"
            assert config.feishu_webhook_url == "https://test.webhook.url"
            assert config.temperature == 0.5
            assert config.max_tokens == 1000
            
        finally:
            # Clean up
            for var in ["LLM_PROVIDER", "OPENAI_API_KEY", "OPENAI_MODEL", 
                       "FEISHU_WEBHOOK_URL", "TEMPERATURE", "MAX_TOKENS"]:
                if var in os.environ:
                    del os.environ[var]
    
    def test_get_llm_api_key(self):
        """Test getting LLM API key."""
        # Test Deepseek
        os.environ["LLM_PROVIDER"] = "deepseek"
        os.environ["DEEPSEEK_API_KEY"] = "deepseek-key"
        try:
            config = Config()
            assert config.get_llm_api_key() == "deepseek-key"
        finally:
            del os.environ["LLM_PROVIDER"]
            del os.environ["DEEPSEEK_API_KEY"]
        
        # Test OpenAI
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "openai-key"
        try:
            config = Config()
            assert config.get_llm_api_key() == "openai-key"
        finally:
            del os.environ["LLM_PROVIDER"]
            del os.environ["OPENAI_API_KEY"]
    
    def test_get_model_name(self):
        """Test getting model name."""
        os.environ["LLM_PROVIDER"] = "deepseek"
        os.environ["DEEPSEEK_MODEL"] = "deepseek-chat-v2"
        try:
            config = Config()
            assert config.get_model_name() == "deepseek-chat-v2"
        finally:
            del os.environ["LLM_PROVIDER"]
            del os.environ["DEEPSEEK_MODEL"]
    
    def test_validate_config(self):
        """Test configuration validation."""
        # Test missing API key
        os.environ["LLM_PROVIDER"] = "deepseek"
        if "DEEPSEEK_API_KEY" in os.environ:
            del os.environ["DEEPSEEK_API_KEY"]
        if "FEISHU_WEBHOOK_URL" in os.environ:
            del os.environ["FEISHU_WEBHOOK_URL"]
        
        try:
            config = Config()
            validation = config.validate()
            assert not validation["valid"]
            assert "DEEPSEEK_API_KEY" in str(validation["missing"])
            assert "FEISHU_WEBHOOK_URL" in str(validation["missing"])
        finally:
            if "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]
        
        # Test valid configuration
        os.environ["LLM_PROVIDER"] = "deepseek"
        os.environ["DEEPSEEK_API_KEY"] = "test-key"
        os.environ["FEISHU_WEBHOOK_URL"] = "https://test.url"
        try:
            config = Config()
            validation = config.validate()
            assert validation["valid"]
            assert len(validation["missing"]) == 0
        finally:
            for var in ["LLM_PROVIDER", "DEEPSEEK_API_KEY", "FEISHU_WEBHOOK_URL"]:
                if var in os.environ:
                    del os.environ[var]

