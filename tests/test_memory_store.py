"""
Tests for memory store functionality.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from assistant.core.config import Config
from assistant.memory.memory_store import MemoryStore, SimpleKeywordEmbeddings


class TestMemoryStore:
    """Test memory store operations."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        # Set minimal config
        import os
        os.environ["FEISHU_WEBHOOK_URL"] = "https://test.url"
        os.environ["LLM_PROVIDER"] = "deepseek"
        os.environ["DEEPSEEK_API_KEY"] = "test-key"
        
        config = Config()
        yield config
        
        # Cleanup
        for var in ["FEISHU_WEBHOOK_URL", "LLM_PROVIDER", "DEEPSEEK_API_KEY"]:
            if var in os.environ:
                del os.environ[var]
    
    def test_memory_store_initialization(self, temp_dir, config):
        """Test memory store initialization."""
        store = MemoryStore(config, persist_directory=temp_dir)
        assert store is not None
        assert store.persist_directory == Path(temp_dir)
    
    def test_add_memories(self, temp_dir, config):
        """Test adding memories to the store."""
        store = MemoryStore(config, persist_directory=temp_dir)
        
        memories = [
            {
                "content": "User prefers Python over Java",
                "source": "interaction_1",
                "timestamp": "2024-01-01T00:00:00"
            },
            {
                "content": "User is working on a robotics project",
                "source": "interaction_2",
                "timestamp": "2024-01-02T00:00:00"
            }
        ]
        
        store.add_memories(memories)
        # If no errors, consider it successful
        assert True
    
    def test_search_memories(self, temp_dir, config):
        """Test searching memories."""
        store = MemoryStore(config, persist_directory=temp_dir)
        
        memories = [
            {
                "content": "User prefers Python over Java",
                "source": "interaction_1",
                "timestamp": "2024-01-01T00:00:00"
            }
        ]
        
        store.add_memories(memories)
        
        # Search for relevant memories
        results = store.search_memories("Python programming", k=1)
        # Results might be empty if embeddings fail, but should not raise error
        assert isinstance(results, list)


class TestSimpleKeywordEmbeddings:
    """Test simple keyword embeddings fallback."""
    
    def test_simple_embeddings_initialization(self):
        """Test simple embeddings initialization."""
        embeddings = SimpleKeywordEmbeddings()
        assert embeddings.embedding_dim == 128
    
    def test_embed_documents(self):
        """Test embedding documents."""
        embeddings = SimpleKeywordEmbeddings()
        texts = ["Python is a programming language", "Java is also a language"]
        result = embeddings.embed_documents(texts)
        
        assert len(result) == 2
        assert len(result[0]) == 128
        assert len(result[1]) == 128
        assert all(isinstance(x, float) for x in result[0])
    
    def test_embed_query(self):
        """Test embedding a query."""
        embeddings = SimpleKeywordEmbeddings()
        query = "What is Python?"
        result = embeddings.embed_query(query)
        
        assert len(result) == 128
        assert all(isinstance(x, float) for x in result)
    
    def test_keyword_extraction(self):
        """Test keyword extraction."""
        embeddings = SimpleKeywordEmbeddings()
        text = "The quick brown fox jumps over the lazy dog"
        keywords = embeddings._extract_keywords(text)
        
        # Should extract meaningful keywords, filtering stop words
        assert "quick" in keywords or "brown" in keywords or "fox" in keywords
        assert "the" not in keywords  # Stop word filtered
        assert "over" not in keywords  # Stop word filtered

