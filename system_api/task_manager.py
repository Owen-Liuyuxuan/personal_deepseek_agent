# deepseek_chat/system_api/task_manager.py
import streamlit as st
from typing import Dict, Any, List, Callable, Optional
import datetime

class TaskManager:
    """Manages application tasks and UI components for Deepseek Chat."""
    
    def __init__(self):
        """Initialize the task manager."""
        self.tasks = {}
        self.ui_components = {}
    
    def register_task(self, name: str, task_func: Callable, description: str = "") -> None:
        """Register a task with the manager.
        
        Args:
            name: Unique name for the task
            task_func: Function to execute for this task
            description: Optional description of what the task does
        """
        self.tasks[name] = {
            "function": task_func,
            "description": description,
            "last_run": None
        }
    
    def execute_task(self, name: str, *args, **kwargs) -> Any:
        """Execute a registered task by name.
        
        Args:
            name: Name of the task to execute
            *args, **kwargs: Arguments to pass to the task function
            
        Returns:
            The result of the task function
        """
        if name not in self.tasks:
            raise ValueError(f"Task '{name}' not registered")
            
        task = self.tasks[name]
        result = task["function"](*args, **kwargs)
        task["last_run"] = datetime.datetime.now()
        return result
    
    def register_ui_component(self, name: str, render_func: Callable) -> None:
        """Register a UI component with the manager.
        
        Args:
            name: Unique name for the UI component
            render_func: Function that renders this component
        """
        self.ui_components[name] = render_func
    
    def render_ui_component(self, name: str, *args, **kwargs) -> None:
        """Render a registered UI component by name.
        
        Args:
            name: Name of the UI component to render
            *args, **kwargs: Arguments to pass to the render function
        """
        if name not in self.ui_components:
            raise ValueError(f"UI component '{name}' not registered")
            
        self.ui_components[name](*args, **kwargs)

# Task functions that will be moved from app.py
def initialize_session_state():
    """Initialize all session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "memory_manager" not in st.session_state:
        from memory.manager import MemoryManager
        st.session_state.memory_manager = MemoryManager()

    if "file_handler" not in st.session_state:
        from file_handlers.uploader import FileUploadHandler
        st.session_state.file_handler = FileUploadHandler()

    if "file_creator" not in st.session_state:
        from file_handlers.creator import FileCreationHandler
        st.session_state.file_creator = FileCreationHandler()

    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []

    if "current_upload_id" not in st.session_state:
        st.session_state.current_upload_id = None

    if "api_key" not in st.session_state:
        import os
        st.session_state.api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if "google_api_key" not in st.session_state:
        import os
        st.session_state.google_api_key = os.environ.get("GOOGLE_API_KEY", "")

    if "google_cse_id" not in st.session_state:
        import os
        st.session_state.google_cse_id = os.environ.get("GOOGLE_CSE_ID", "")

    if "suggested_memory" not in st.session_state:
        st.session_state.suggested_memory = ""

    if "search_results" not in st.session_state:
        st.session_state.search_results = None

    if "created_files" not in st.session_state:
        st.session_state.created_files = []
        
    if "welcome_message" not in st.session_state:
        from api.client import DeepseekClient
        from utils.helpers import generate_welcome_message
        client = DeepseekClient(api_key=st.session_state.api_key)
        st.session_state.welcome_message = generate_welcome_message(st.session_state.memory_manager, client)

def process_user_message(prompt: str, model: str, temperature: float, search_toggle: bool):
    """Process a user message and generate a response."""
    from api.client import DeepseekClient
    from api.search import GoogleSearchClient
    from utils.helpers import create_system_prompt, truncate_messages_to_token_limit
    from utils.parsers import parse_file_creations, extract_response_without_files, check_for_directory_structure
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Reset search results
    st.session_state.search_results = None
        
    # Get memory prompt
    memory_prompt = st.session_state.memory_manager.get_memory_prompt()
    
    try:
        # Initialize Deepseek client
        client = DeepseekClient(api_key=st.session_state.api_key)
        
        # Check if search is needed
        if search_toggle and st.session_state.google_api_key and st.session_state.google_cse_id:
            with st.spinner("Evaluating search needs..."):
                search_needed, search_query = client.detect_search_need(prompt)
                
                if search_needed and search_query:
                    st.info(f"Searching for information on: {search_query}")
                    
                    # Perform search
                    search_client = GoogleSearchClient(
                        api_key=st.session_state.google_api_key,
                        cse_id=st.session_state.google_cse_id
                    )
                    
                    search_results = search_client.search(search_query)
                    formatted_results = search_client.format_search_results(search_results)
                    
                    # Add search results to conversation context
                    st.session_state.messages.append({
                        "role": "system",
                        "content": f"[Search Results] {formatted_results}"
                    })
                    
                    # Display search results
                    st.session_state.search_results = formatted_results
        
        # Prepare messages for API call
        api_messages = []
        
        # Add system message with memory
        api_messages.append(create_system_prompt(memory_prompt, include_file_creation=True))
        
        # Add truncated chat history to stay within token limits
        conversation_messages = truncate_messages_to_token_limit(st.session_state.messages, max_tokens=7000)
        for msg in conversation_messages:
            if msg["role"] != "system" or msg["content"].startswith("[Search Results]") or msg["content"].startswith("[File Context]"):
                api_messages.append(msg)
            
        # Call API
        with st.spinner("Thinking..."):
            response = client.chat_completion(
                messages=api_messages,
                model=model,
                temperature=temperature,
                max_tokens=2000
            )
            
        # Extract assistant's message
        assistant_message = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Check for file creation in the response
        files_to_create = parse_file_creations(assistant_message)
        is_project, project_files = check_for_directory_structure(assistant_message)
        
        # If there are files to create, process them
        if files_to_create or is_project:
            files_list = project_files if is_project else files_to_create
            
            for file_info in files_list:
                created_file = st.session_state.file_creator.create_file(
                    file_info["filename"],
                    file_info["content"]
                )
                st.session_state.created_files.append(created_file)
            
            # Create zip if it's a project structure
            if is_project and project_files:
                zip_path = st.session_state.file_creator.create_directory_structure(project_files)
                download_html = st.session_state.file_creator.get_download_link_html(
                    zip_path, 
                    "Download Project Files"
                )
                
                # Strip project structure directive from response
                clean_response = extract_response_without_files(assistant_message)
                clean_response += f"\n\n{download_html}"
                
                assistant_message = clean_response
            
        # Add assistant message to chat history (without file creation blocks if files were created)
        if files_to_create and not is_project:
            clean_response = extract_response_without_files(assistant_message)
            st.session_state.messages.append({"role": "assistant", "content": clean_response})
        else:
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})
        
        return True
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return False

def extract_memory_from_conversation(model: str):
    """Extract memory from the current conversation."""
    from api.client import DeepseekClient
    
    try:
        client = DeepseekClient(api_key=st.session_state.api_key)
        with st.spinner("Analyzing conversation..."):
            suggested_memory = client.extract_memory(
                [m for m in st.session_state.messages if m["role"] != "system"],
                model=model
            )
            st.session_state.suggested_memory = suggested_memory
            return True
    except Exception as e:
        st.error(f"Failed to extract memory: {str(e)}")
        return False

def process_file_upload(uploaded_file):
    """Process an uploaded file."""
    if not uploaded_file:
        # Reset the current upload ID when no file is selected
        st.session_state.current_upload_id = None
        return False
        
    # Generate a unique ID for this upload to track if it's been processed
    upload_id = f"{uploaded_file.name}_{hash(uploaded_file.getvalue())}"
    
    # Only process the file if it hasn't been processed before
    if st.session_state.current_upload_id != upload_id:
        try:
            st.session_state.current_upload_id = upload_id
            file_info = st.session_state.file_handler.save_uploaded_file(uploaded_file)
            st.session_state.uploaded_files.append(file_info)
            
            # Add file context to conversation
            file_context = st.session_state.file_handler.format_file_context(file_info)
            st.session_state.messages.append({
                "role": "user",
                "content": f"I've uploaded a file named {uploaded_file.name}. Please analyze it."
            })
            st.session_state.messages.append({
                "role": "system",
                "content": f"[File Context] {file_context}"
            })
            
            st.success(f"File uploaded: {uploaded_file.name}")
            return True
        except Exception as e:
            st.error(f"Error uploading file: {str(e)}")
            return False
    return False