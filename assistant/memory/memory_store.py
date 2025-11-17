"""
Memory Store using LangChain for vector storage and retrieval.

Uses cloud-based embeddings for GitHub Actions compatibility (no CUDA required).
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

# Try to use langchain-chroma if available, otherwise fall back to langchain_community
try:
    from langchain_chroma import Chroma
except ImportError:
    # Fallback to deprecated langchain_community version
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community.vectorstores")
    from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Google Gemini embeddings - optional due to version compatibility
# Using lazy import to avoid metaclass conflicts
GoogleGenerativeAIEmbeddings = None

from assistant.core.config import Config, LLMProvider

logger = logging.getLogger(__name__)


class MemoryStore:
    """Manages memory storage and retrieval using vector embeddings."""
    
    def __init__(self, config: Config, persist_directory: str = "./memory_store"):
        """
        Initialize the memory store.
        
        Args:
            config: Configuration object
            persist_directory: Directory to persist vector store
        """
        self.config = config
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize embeddings
        self._initialize_embeddings()
        
        # Initialize vector store
        self.vector_store: Optional[Chroma] = None
        self._initialize_vector_store()
        
        # Text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
    
    def _initialize_embeddings(self) -> None:
        """
        Initialize cloud-based embedding model.
        
        Priority (if embedding_provider is "auto"):
        1. OpenAI embeddings (if OPENAI_API_KEY is set)
        2. Google Gemini embeddings (if GEMINI_API_KEY is set)
        3. Simple keyword-based fallback (no ML, no CUDA)
        
        If embedding_provider is explicitly set, use that provider.
        """
        embedding_provider = self.config.embedding_provider.lower()
        
        # Explicit OpenAI provider
        if embedding_provider == "openai" or (embedding_provider == "auto" and self.config.openai_api_key):
            if not self.config.openai_api_key:
                logger.warning("OPENAI_API_KEY not set but OpenAI embeddings requested")
            else:
                try:
                    self.embeddings = OpenAIEmbeddings(
                        api_key=self.config.openai_api_key,
                        model=self.config.openai_embedding_model
                    )
                    logger.info(f"Using OpenAI embeddings (cloud-based, model: {self.config.openai_embedding_model})")
                    return
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI embeddings: {e}")
        
        # Explicit Gemini provider
        if embedding_provider == "gemini" or (embedding_provider == "auto" and self.config.gemini_api_key):
            # Lazy import to avoid version conflicts
            global GoogleGenerativeAIEmbeddings
            if GoogleGenerativeAIEmbeddings is None:
                try:
                    from langchain_google_genai import GoogleGenerativeAIEmbeddings
                except (ImportError, TypeError) as e:
                    logger.warning(f"langchain-google-genai not available: {e}")
                    logger.warning("Install with: pip install langchain-google-genai==0.0.8")
            elif not self.config.gemini_api_key:
                logger.warning("GEMINI_API_KEY not set but Gemini embeddings requested")
            else:
                try:
                    self.embeddings = GoogleGenerativeAIEmbeddings(
                        model="models/embedding-001",
                        google_api_key=self.config.gemini_api_key
                    )
                    logger.info("Using Google Gemini embeddings (cloud-based)")
                    return
                except Exception as e:
                    logger.warning(f"Failed to initialize Gemini embeddings: {e}")
        
        # Explicit simple provider or fallback
        if embedding_provider == "simple" or embedding_provider == "auto":
            logger.warning("Using simple keyword-based search (no ML, no CUDA)")
            logger.warning("For better results, set OPENAI_API_KEY or GEMINI_API_KEY")
            self.embeddings = SimpleKeywordEmbeddings()
        else:
            raise ValueError(f"Unknown embedding provider: {embedding_provider}. Use 'openai', 'gemini', 'simple', or 'auto'")
    
    def _initialize_vector_store(self) -> None:
        """Initialize or load the vector store."""
        try:
            self.vector_store = Chroma(
                persist_directory=str(self.persist_directory),
                embedding_function=self.embeddings,
                collection_name="memories"
            )
            logger.info("Vector store initialized")
        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            # Create new store
            self.vector_store = Chroma(
                embedding_function=self.embeddings,
                collection_name="memories"
            )
    
    def add_memories(self, memories: List[Dict[str, Any]]) -> None:
        """
        Add memories to the vector store.
        
        Args:
            memories: List of memory dictionaries
        """
        if not memories:
            return
        
        documents = []
        metadatas = []
        
        for memory in memories:
            # Extract content
            content = memory.get("content", "")
            if isinstance(content, dict):
                content = json.dumps(content, ensure_ascii=False)
            
            # Create document
            doc = Document(
                page_content=content,
                metadata={
                    "source": memory.get("source", "unknown"),
                    "timestamp": memory.get("timestamp", datetime.now().isoformat()),
                    "file_type": memory.get("file_type", "unknown")
                }
            )
            
            documents.append(doc)
            metadatas.append(doc.metadata)
        
        # Split documents if needed
        split_docs = []
        for doc in documents:
            splits = self.text_splitter.split_documents([doc])
            split_docs.extend(splits)
        
        # Add to vector store
        if split_docs:
            self.vector_store.add_documents(split_docs)
            logger.info(f"Added {len(split_docs)} memory chunks to vector store")
    
    def search_memories(self, query: str, k: int = 5) -> List[Document]:
        """
        Search for relevant memories.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of relevant document chunks
        """
        if not self.vector_store:
            return []
        
        try:
            results = self.vector_store.similarity_search(query, k=k)
            logger.info(f"Found {len(results)} relevant memories for query: {query[:50]}")
            return results
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            return []
    
    def get_all_memories(self) -> List[Document]:
        """Get all memories from the store."""
        if not self.vector_store:
            return []
        
        try:
            # Get all documents (this might be memory intensive for large stores)
            results = self.vector_store.similarity_search("", k=10000)  # Large k to get all
            return results
        except Exception as e:
            logger.error(f"Error retrieving all memories: {e}")
            return []
    
    def delete_memory(self, memory_id: Optional[str] = None) -> bool:
        """
        Delete a memory from the store.
        
        Args:
            memory_id: ID of memory to delete (if None, deletes all)
            
        Returns:
            True if successful
        """
        # Note: ChromaDB deletion requires specific implementation
        # This is a placeholder for the functionality
        logger.warning("Memory deletion not fully implemented")
        return True


class SimpleKeywordEmbeddings(Embeddings):
    """
    Simple keyword-based embedding fallback.
    
    This is a lightweight, non-ML fallback that doesn't require CUDA or heavy dependencies.
    It uses simple keyword matching and TF-IDF-like scoring for similarity.
    """
    
    def __init__(self):
        """Initialize simple keyword embeddings."""
        self.embedding_dim = 128  # Fixed dimension for compatibility
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Create simple embeddings based on keyword extraction.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            # Extract keywords (simple word-based)
            words = self._extract_keywords(text)
            # Create a simple embedding vector
            embedding = self._words_to_embedding(words)
            embeddings.append(embedding)
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """
        Create embedding for a query.
        
        Args:
            text: Query text
            
        Returns:
            Embedding vector
        """
        words = self._extract_keywords(text)
        return self._words_to_embedding(words)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple word extraction (lowercase, alphanumeric)
        words = re.findall(r'\b[a-z0-9]+\b', text.lower())
        # Filter out very short words and common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'}
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        return keywords[:50]  # Limit to top 50 keywords
    
    def _words_to_embedding(self, words: List[str]) -> List[float]:
        """
        Convert keywords to a simple embedding vector.
        
        Uses a hash-based approach to create a fixed-size vector.
        """
        import hashlib
        
        # Create a vector based on keyword hashes
        embedding = [0.0] * self.embedding_dim
        
        for word in words:
            # Hash the word to get consistent positions
            hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16)
            # Map to embedding dimension
            idx = hash_val % self.embedding_dim
            # Add weight based on word length (longer words might be more important)
            weight = min(len(word) / 10.0, 1.0)
            embedding[idx] += weight
        
        # Normalize the vector
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding

