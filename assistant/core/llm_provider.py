"""
LLM Provider abstraction using LangChain.

Supports OpenAI, Deepseek, and Gemini providers.
"""

import os
import logging
from typing import Optional, Any, List, Dict
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from assistant.core.config import Config, LLMProvider

logger = logging.getLogger(__name__)

# Google Gemini support - optional due to version compatibility
# Using lazy import to avoid metaclass conflicts with incompatible versions
ChatGoogleGenerativeAI = None


class LLMProviderManager:
    """Manages LLM provider initialization and usage."""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm: Optional[BaseChatModel] = None
        self._initialize_llm()
    
    def _initialize_llm(self) -> None:
        """Initialize the LLM based on configuration."""
        provider = self.config.llm_provider
        api_key = self.config.get_llm_api_key()
        model_name = self.config.get_model_name()
        
        if not api_key:
            raise ValueError(f"API key not found for provider: {provider}")
        
        if provider == LLMProvider.OPENAI.value:
            self.llm = ChatOpenAI(
                api_key=api_key,
                model=model_name,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        
        elif provider == LLMProvider.DEEPSEEK.value:
            # Deepseek uses OpenAI-compatible API
            self.llm = ChatOpenAI(
                api_key=api_key,
                model=model_name,
                base_url="https://api.deepseek.com/v1",
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        
        elif provider == LLMProvider.GEMINI.value:
            # Try to use langchain-google-genai, but fallback to direct API if there's a conflict
            global ChatGoogleGenerativeAI
            if ChatGoogleGenerativeAI is None:
                try:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                except (ImportError, TypeError) as e:
                    error_msg = str(e)
                    if "metaclass conflict" in error_msg.lower() or "metaclass" in error_msg.lower():
                        # Use direct Google Generative AI library as fallback
                        logger.warning(
                            f"langchain-google-genai has compatibility issues. "
                            f"Using direct Google Generative AI API instead."
                        )
                        try:
                            import google.generativeai as genai
                            genai.configure(api_key=api_key)
                            # Create a wrapper class for LangChain compatibility
                            from langchain_core.language_models import BaseChatModel
                            from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
                            from langchain_core.outputs import ChatGeneration, ChatResult
                            
                            class GeminiChatWrapper(BaseChatModel):
                                """Wrapper for Google Generative AI to work with LangChain."""
                                
                                model_name: str
                                temperature: float
                                max_tokens: int
                                
                                def __init__(self, model_name: str, temperature: float, max_tokens: int):
                                    super().__init__(
                                        model_name=model_name,
                                        temperature=temperature,
                                        max_tokens=max_tokens
                                    )
                                    self._model = genai.GenerativeModel(model_name)
                                
                                def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                                    # Convert LangChain messages to Gemini format
                                    prompt_parts = []
                                    for msg in messages:
                                        if isinstance(msg, SystemMessage):
                                            prompt_parts.append(f"System: {msg.content}")
                                        elif isinstance(msg, HumanMessage):
                                            prompt_parts.append(msg.content)
                                        elif isinstance(msg, AIMessage):
                                            prompt_parts.append(f"Assistant: {msg.content}")
                                    
                                    full_prompt = "\n".join(prompt_parts)
                                    
                                    # Generate response
                                    response = self._model.generate_content(
                                        full_prompt,
                                        generation_config=genai.types.GenerationConfig(
                                            temperature=self.temperature,
                                            max_output_tokens=self.max_tokens
                                        )
                                    )
                                    
                                    # Convert to LangChain format
                                    message = AIMessage(content=response.text)
                                    generation = ChatGeneration(message=message)
                                    return ChatResult(generations=[generation])
                                
                                @property
                                def _llm_type(self) -> str:
                                    return "gemini"
                            
                            self.llm = GeminiChatWrapper(model_name, self.config.temperature, self.config.max_tokens)
                            logger.info(f"Using direct Google Generative AI API (model: {model_name})")
                            return
                        except ImportError:
                            raise ValueError(
                                f"Gemini provider requires either langchain-google-genai or google-generativeai. "
                                f"Install with: pip install google-generativeai. "
                                f"Original error: {error_msg}"
                            )
                        except Exception as fallback_error:
                            raise ValueError(
                                f"Failed to initialize Gemini with both langchain-google-genai and direct API. "
                                f"Please use 'openai' or 'deepseek' as your LLM_PROVIDER instead. "
                                f"Errors: {error_msg}, {fallback_error}"
                            )
                    else:
                        raise ValueError(
                            f"Gemini provider requires langchain-google-genai. "
                            f"Install with: pip install langchain-google-genai==0.0.8. "
                            f"Error: {error_msg}"
                        )
            
            # Use langchain-google-genai if available
            try:
                self.llm = ChatGoogleGenerativeAI(
                    google_api_key=api_key,
                    model=model_name,
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_tokens
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to initialize Gemini LLM. This may be due to version incompatibility. "
                    f"Please use 'openai' or 'deepseek' as your LLM_PROVIDER instead. "
                    f"Error: {e}"
                )
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def get_llm(self) -> BaseChatModel:
        """Get the initialized LLM instance."""
        if self.llm is None:
            raise RuntimeError("LLM not initialized")
        return self.llm
    
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """Invoke the LLM with messages."""
        if self.llm is None:
            raise RuntimeError("LLM not initialized")
        
        # Convert messages to LangChain format
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))
        
        response = self.llm.invoke(langchain_messages)
        return response.content

