"""
Configuration management for the personal assistant.
"""

import os
from typing import Optional, Dict, Any
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"


class Config:
    """Configuration manager for the assistant."""
    
    def __init__(self):
        # LLM Configuration
        self.llm_provider = os.environ.get("LLM_PROVIDER", LLMProvider.DEEPSEEK.value)
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        
        # Model selection
        self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        self.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Memory Repository Configuration
        self.memory_repo_url = os.environ.get("MEMORY_REPO_URL")
        self.memory_repo_token = os.environ.get("MEMORY_REPO_TOKEN")  # For private repos
        self.memory_repo_path = os.environ.get("MEMORY_REPO_PATH", "./memory_repo")
        
        # Google Search Configuration
        self.google_api_key = os.environ.get("GOOGLE_API_KEY")
        self.google_cse_id = os.environ.get("GOOGLE_CSE_ID")
        
        # GitHub Configuration
        self.github_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        
        # Feishu Configuration
        self.feishu_webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
        
        # Assistant Configuration
        self.temperature = float(os.environ.get("TEMPERATURE", "0.1"))
        self.max_tokens = int(os.environ.get("MAX_TOKENS", "10000"))
        
        # Embedding Configuration
        self.embedding_provider = os.environ.get("EMBEDDING_PROVIDER", "simple")  # auto, openai, gemini, simple
        self.openai_embedding_model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        
    def get_llm_api_key(self) -> Optional[str]:
        """Get the API key for the configured LLM provider."""
        if self.llm_provider == LLMProvider.OPENAI.value:
            return self.openai_api_key
        elif self.llm_provider == LLMProvider.DEEPSEEK.value:
            return self.deepseek_api_key
        elif self.llm_provider == LLMProvider.GEMINI.value:
            return self.gemini_api_key
        return None
    
    def get_model_name(self) -> str:
        """Get the model name for the configured LLM provider."""
        if self.llm_provider == LLMProvider.OPENAI.value:
            return self.openai_model
        elif self.llm_provider == LLMProvider.DEEPSEEK.value:
            return self.deepseek_model
        elif self.llm_provider == LLMProvider.GEMINI.value:
            return self.gemini_model
        return self.deepseek_model
    
    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return missing required fields."""
        missing = []
        
        # Check LLM API key
        if not self.get_llm_api_key():
            missing.append(f"{self.llm_provider.upper()}_API_KEY")
        
        # Check memory repo if configured
        if self.memory_repo_url and not self.memory_repo_token:
            missing.append("MEMORY_REPO_TOKEN (required for private repos)")
        
        # Check Feishu webhook
        if not self.feishu_webhook_url:
            missing.append("FEISHU_WEBHOOK_URL")
        
        return {
            "valid": len(missing) == 0,
            "missing": missing
        }

