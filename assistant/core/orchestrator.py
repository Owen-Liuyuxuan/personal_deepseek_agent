"""
Main Orchestrator

Coordinates all components using LangChain agents.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    from langchain.agents import AgentExecutor, create_openai_tools_agent
except ImportError:
    # Fallback for different LangChain versions
    try:
        from langchain.agents.agent import AgentExecutor
        from langchain.agents.openai_tools import create_openai_tools_agent
    except ImportError:
        AgentExecutor = None
        create_openai_tools_agent = None

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage

from assistant.core.config import Config
from assistant.core.llm_provider import LLMProviderManager
from assistant.memory.repository_manager import MemoryRepositoryManager
from assistant.memory.memory_store import MemoryStore
from assistant.memory.memory_analyzer import MemoryAnalyzer
from assistant.tools.search_tool import GoogleSearchTool, SearchDecisionMaker
from assistant.tools.github_tool import GitHubTool

logger = logging.getLogger(__name__)


class PersonalAssistantOrchestrator:
    """Main orchestrator for the personal assistant system."""
    
    def __init__(self, config: Config):
        """
        Initialize the orchestrator.
        
        Args:
            config: Configuration object
        """
        self.config = config
        
        # Initialize core components
        logger.info("Initializing LLM provider...")
        self.llm_manager = LLMProviderManager(config)
        
        logger.info("Initializing memory store...")
        self.memory_store = MemoryStore(config)
        
        # Initialize memory repository manager if configured
        self.memory_repo_manager: Optional[MemoryRepositoryManager] = None
        if config.memory_repo_url:
            logger.info("Initializing memory repository manager...")
            self.memory_repo_manager = MemoryRepositoryManager(
                repo_url=config.memory_repo_url,
                repo_path=config.memory_repo_path,
                token=config.memory_repo_token
            )
            # Clone or update repository
            self.memory_repo_manager.clone_or_update()
            # Load memories into vector store
            memories = self.memory_repo_manager.load_memories()
            if memories:
                self.memory_store.add_memories(memories)
        
        logger.info("Initializing memory analyzer...")
        self.memory_analyzer = MemoryAnalyzer(self.llm_manager, self.memory_store)
        
        # Initialize tools
        self.tools = []
        
        # Google Search tool
        if config.google_api_key and config.google_cse_id:
            logger.info("Initializing Google Search tool...")
            self.search_tool = GoogleSearchTool(config.google_api_key, config.google_cse_id)
            self.search_decision_maker = SearchDecisionMaker(self.llm_manager)
            self.tools.append(self.search_tool)
        
        # GitHub tool
        if config.github_token:
            logger.info("Initializing GitHub tool...")
            self.github_tool = GitHubTool(config.github_token, self.memory_store)
            self.tools.append(self.github_tool)
        
        # Initialize agent
        self.agent_executor: Optional[AgentExecutor] = None
        self._initialize_agent()
    
    def _initialize_agent(self) -> None:
        """Initialize the LangChain agent."""
        if not self.tools:
            logger.warning("No tools available, agent will be LLM-only")
            return
        
        # Check if agent classes are available
        if AgentExecutor is None or create_openai_tools_agent is None:
            logger.warning("Agent classes not available, using LLM-only mode")
            self.agent_executor = None
            return
        
        try:
            # Create prompt template
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""You are a helpful personal assistant with access to:
- Personal memory repository with past interactions and preferences
- Google Search for current information
- GitHub operations for repository management

Use the available tools to answer questions accurately. When you have relevant memories, use them. When you need current information, use search. When asked about GitHub repositories, use the GitHub tool.

Always be helpful, accurate, and concise."""),
                MessagesPlaceholder(variable_name="chat_history"),
                HumanMessage(content="{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            
            # Create agent
            llm = self.llm_manager.get_llm()
            
            # Try to create agent with tools
            # Note: Some LLM providers may not support tool calling
            try:
                agent = create_openai_tools_agent(llm, self.tools, prompt)
                
                # Create agent executor
                self.agent_executor = AgentExecutor(
                    agent=agent,
                    tools=self.tools,
                    verbose=True,
                    handle_parsing_errors=True
                )
                
                logger.info("Agent initialized successfully with tools")
            except Exception as agent_error:
                logger.warning(f"Could not create agent with tools: {agent_error}")
                logger.info("Falling back to LLM-only mode (tools will be called manually)")
                self.agent_executor = None
            
        except Exception as e:
            logger.error(f"Error initializing agent: {e}")
            logger.info("Falling back to LLM-only mode")
            self.agent_executor = None
    
    def process_question(self, question: str, user: str, time: str) -> Dict[str, Any]:
        """
        Process a question and return a response.
        
        Args:
            question: User's question
            user: User identifier
            time: Timestamp of the question
            
        Returns:
            Dictionary with response and metadata
        """
        logger.info(f"Processing question from {user}: {question[:100]}")
        
        # Step 1: Analyze question and load relevant memories
        memory_analysis = self.memory_analyzer.analyze_question(question, user)
        memory_context = self.memory_analyzer.format_memories_for_context(
            memory_analysis["all_memories"]
        )
        
        # Step 2: Determine if search is needed
        search_needed = False
        search_query = None
        if hasattr(self, 'search_decision_maker'):
            search_needed, search_query = self.search_decision_maker.should_search(
                question, memory_context
            )
        
        # Step 3: Build context for LLM
        context_parts = []
        
        if memory_context:
            context_parts.append(f"**Relevant Memories:**\n{memory_context}")
        
        full_context = "\n\n".join(context_parts)
        
        # Step 4: Generate response using agent or direct LLM call
        # If search is needed, always perform it directly first (more reliable than relying on agent)
        if search_needed and search_query:
            logger.info(f"Performing search: {search_query}")
            search_results = self.search_tool._run(search_query)
            
            if self.agent_executor:
                # Try agent with search results in context
                try:
                    prompt = f"""You are a helpful personal assistant. Answer the question using the search results and context provided.

{full_context}

**Search Results:**
{search_results}

Question: {question}

Provide a comprehensive answer based on the search results above."""
                    
                    response = self.agent_executor.invoke({
                        "input": prompt,
                        "chat_history": []
                    })
                    answer = response.get("output", "")
                    
                    # If agent gave generic response, use direct LLM call instead
                    if not answer or len(answer) < 50 or "how can i help" in answer.lower():
                        logger.info("Agent gave generic response, using direct LLM call with search results")
                        answer = self._direct_llm_call(
                            question, 
                            f"{full_context}\n\n**Search Results:**\n{search_results}"
                        )
                except Exception as e:
                    logger.error(f"Agent execution error: {e}, using direct LLM call")
                    answer = self._direct_llm_call(
                        question, 
                        f"{full_context}\n\n**Search Results:**\n{search_results}"
                    )
            else:
                # Direct LLM call with search results
                answer = self._direct_llm_call(
                    question, 
                    f"{full_context}\n\n**Search Results:**\n{search_results}"
                )
        elif self.agent_executor:
            # Use agent without search
            try:
                response = self.agent_executor.invoke({
                    "input": f"{full_context}\n\nQuestion: {question}",
                    "chat_history": []
                })
                answer = response.get("output", "")
                
                # If agent gave generic response, use direct LLM call instead
                if not answer or len(answer) < 50 or "how can i help" in answer.lower():
                    logger.info("Agent gave generic response, using direct LLM call")
                    answer = self._direct_llm_call(question, full_context)
            except Exception as e:
                logger.error(f"Agent execution error: {e}")
                answer = self._direct_llm_call(question, full_context)
        else:
            # Direct LLM call without tools
            answer = self._direct_llm_call(question, full_context)
        
        # Step 5: Handle memory creation/deletion
        should_create_tuple = memory_analysis.get("should_create_memory", (False, ""))
        if isinstance(should_create_tuple, tuple) and len(should_create_tuple) == 2:
            should_create, memory_content = should_create_tuple
            if should_create and memory_content:
                # Ensure memory_content is a string
                if not isinstance(memory_content, str):
                    memory_content = str(memory_content) if memory_content else ""
                if memory_content.strip():  # Only create if not empty
                    self._create_memory(memory_content, user, question)
        
        if memory_analysis["memories_to_delete"]:
            self._delete_memories(memory_analysis["memories_to_delete"])
        
        # Step 6: Prepare response
        result = {
            "answer": answer,
            "memories_used": len(memory_analysis["all_memories"]),
            "search_used": search_needed,
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "question": question
        }
        
        return result
    
    def _direct_llm_call(self, question: str, context: str) -> str:
        """Make a direct LLM call without agent."""
        system_prompt = """You are a helpful personal assistant. Use the provided context to answer questions accurately and comprehensively.

When search results are provided, prioritize that information as it contains the most current data. Combine search results with memories when relevant.

Provide clear, direct answers based on the available information."""
        
        user_prompt = f"{context}\n\nQuestion: {question}\n\nPlease provide a helpful, comprehensive answer based on the context above."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return self.llm_manager.invoke(messages)
    
    def _create_memory(self, content: str, user: str, question: str) -> None:
        """Create a new memory."""
        # Ensure content is a string
        if not isinstance(content, str):
            if content is None:
                logger.warning("Memory content is None, skipping memory creation")
                return
            # Convert to string if it's not
            content = str(content)
        
        # Truncate if too long
        if len(content) > 1000:
            content = content[:1000] + "..."
        
        memory = {
            "content": content,
            "source": f"interaction_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "related_question": question
        }
        
        # Add to vector store
        self.memory_store.add_memories([memory])
        
        # Save to repository if available
        if self.memory_repo_manager:
            if self.memory_repo_manager.save_memory(memory):
                # Commit and push immediately to ensure persistence
                commit_message = f"Add memory: {content[:100] if len(content) > 100 else content} (user: {user})"
                if self.memory_repo_manager.commit_and_push(commit_message):
                    logger.info("Memory saved, committed, and pushed to remote repository")
                else:
                    logger.warning("Memory saved but failed to commit/push to remote")
            else:
                logger.warning("Failed to save memory to repository")
        
        # Log with safe string slicing
        content_preview = content[:50] if len(content) > 50 else content
        logger.info(f"Created new memory: {content_preview}")
    
    def _delete_memories(self, memory_sources: List[str]) -> None:
        """
        Delete memories by source/content description and commit/push changes.
        
        Args:
            memory_sources: List of memory source identifiers or content descriptions to delete
        """
        if not memory_sources:
            return
        
        if not self.memory_repo_manager:
            logger.warning("Memory repository manager not available, cannot delete memories")
            return
        
        deleted_count = 0
        deleted_sources = []
        
        # Load all memories to search by content
        all_memories = self.memory_repo_manager.load_memories()
        
        for source_description in memory_sources:
            try:
                success = False
                matched_memories = []
                
                # Strategy 1: Try as direct file path
                if "/" in source_description or source_description.endswith(".json"):
                    if self.memory_repo_manager.delete_memory_file(source_description):
                        deleted_count += 1
                        deleted_sources.append(source_description)
                        success = True
                        continue
                
                # Strategy 2: Search memories by content similarity
                # The LLM might return descriptions like "Any memory about PyTorch version X"
                # We need to find memories that match this description
                for memory in all_memories:
                    memory_content = str(memory.get("content", "")).lower()
                    memory_source = str(memory.get("source", "")).lower()
                    
                    # Check if the description matches memory content or source
                    description_lower = source_description.lower()
                    
                    # Match if description keywords appear in memory content
                    # Extract key terms from description (remove common words)
                    key_terms = [term for term in description_lower.split() 
                                if len(term) > 3 and term not in ["any", "memory", "asserting", "specific", "version", "latest", "stable"]]
                    
                    if key_terms:
                        # Check if any key terms match
                        matches = sum(1 for term in key_terms if term in memory_content or term in memory_source)
                        if matches >= len(key_terms) * 0.5:  # At least 50% of terms match
                            matched_memories.append(memory)
                    elif description_lower in memory_content or description_lower in memory_source:
                        matched_memories.append(memory)
                
                # Delete matched memories
                if matched_memories:
                    for memory in matched_memories:
                        memory_source = memory.get("source", "")
                        # Try to find the file containing this memory
                        memory_files = self.memory_repo_manager.get_memory_files()
                        for file_path in memory_files:
                            if file_path.suffix == ".json":
                                file_source = str(file_path.relative_to(self.memory_repo_manager.repo_path))
                                # Try to delete this specific memory from the file
                                if self.memory_repo_manager.delete_memory_from_file(
                                    file_source, 
                                    memory_id=memory.get("content", "")
                                ):
                                    deleted_count += 1
                                    if memory_source not in deleted_sources:
                                        deleted_sources.append(memory_source)
                                    success = True
                                    break
                
                # Strategy 3: Try exact source match in files
                if not success:
                    memory_files = self.memory_repo_manager.get_memory_files()
                    for file_path in memory_files:
                        if file_path.suffix == ".json":
                            file_source = str(file_path.relative_to(self.memory_repo_manager.repo_path))
                            if source_description in file_source:
                                if self.memory_repo_manager.delete_memory_file(file_source):
                                    deleted_count += 1
                                    deleted_sources.append(source_description)
                                    success = True
                                    break
                
                if not success:
                    logger.debug(f"Could not find matching memories for: {source_description[:100]}")
                    
            except Exception as e:
                logger.error(f"Error deleting memory source {source_description}: {e}")
        
        if deleted_count > 0:
            # Commit and push deletions
            commit_message = f"Delete {deleted_count} outdated memory(ies): {', '.join([s[:50] for s in deleted_sources[:3]])}"
            if len(deleted_sources) > 3:
                commit_message += f" and {len(deleted_sources) - 3} more"
            
            if self.memory_repo_manager.commit_and_push(commit_message):
                logger.info(f"Deleted {deleted_count} memory(ies) and pushed to remote repository")
            else:
                logger.warning(f"Deleted {deleted_count} memory(ies) but failed to commit/push")
        else:
            logger.debug("No memories were deleted (no matches found)")

