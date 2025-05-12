# deepseek_chat/app.py (corrected file upload section)
import streamlit as st
import os
from typing import List, Dict, Any
import tempfile
import base64
import uuid

from api.client import DeepseekClient
from api.search import GoogleSearchClient
from memory.manager import MemoryManager
from file_handlers.uploader import FileUploadHandler
from file_handlers.creator import FileCreationHandler
from utils.helpers import format_chat_history, create_system_prompt, truncate_messages_to_token_limit, generate_welcome_message
from utils.parsers import parse_file_creations, extract_response_without_files, check_for_directory_structure
from task_manager import TaskManager
from system_api.notifications import send_notification, play_sound

# Page configuration with wider layout
st.set_page_config(
    page_title="Deepseek Chat with Advanced Features",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Setup custom CSS
st.markdown("""
<style>
.file-upload-section {
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 5px;
    margin-bottom: 20px;
}
.file-content {
    max-height: 300px;
    overflow-y: auto;
    padding: 10px;
    border: 1px solid #eee;
    border-radius: 5px;
    background-color: #f9f9f9;
    margin-top: 10px;
}
.memory-section {
    padding: 10px;
    border: 1px solid #d0f0c0;
    border-radius: 5px;
    background-color: #f0fff0;
    margin-top: 10px;
}
.search-results {
    padding: 10px;
    border: 1px solid #b0e0e6;
    border-radius: 5px;
    background-color: #f0f8ff;
    margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "memory_manager" not in st.session_state:
    st.session_state.memory_manager = MemoryManager()

if "file_handler" not in st.session_state:
    st.session_state.file_handler = FileUploadHandler()

if "file_creator" not in st.session_state:
    st.session_state.file_creator = FileCreationHandler()

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

if "current_upload_id" not in st.session_state:
    st.session_state.current_upload_id = None

if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("DEEPSEEK_API_KEY", "")

if "google_api_key" not in st.session_state:
    st.session_state.google_api_key = os.environ.get("GOOGLE_API_KEY", "")

if "google_cse_id" not in st.session_state:
    st.session_state.google_cse_id = os.environ.get("GOOGLE_CSE_ID", "")

if "suggested_memory" not in st.session_state:
    st.session_state.suggested_memory = ""

if "search_results" not in st.session_state:
    st.session_state.search_results = None

if "created_files" not in st.session_state:
    st.session_state.created_files = []

if "task_manager" not in st.session_state:
    st.session_state.task_manager = TaskManager()
    # Start the task manager
    st.session_state.task_manager.start()

# Sidebar for settings and memory management
with st.sidebar:
    st.title("Settings")
    
    api_key = st.text_input("Deepseek API Key", value=st.session_state.api_key, type="password")
    if api_key != st.session_state.api_key:
        st.session_state.api_key = api_key
    
    with st.expander("Google Search Settings"):
        google_api_key = st.text_input("Google API Key", value=st.session_state.google_api_key, type="password")
        if google_api_key != st.session_state.google_api_key:
            st.session_state.google_api_key = google_api_key
            
        google_cse_id = st.text_input("Google CSE ID", value=st.session_state.google_cse_id, type="password")
        if google_cse_id != st.session_state.google_cse_id:
            st.session_state.google_cse_id = google_cse_id
    
    model = st.selectbox(
        "Select Model",
        ["deepseek-chat", "deepseek-coder", "deepseek-large"]
    )
    
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.7, step=0.1)
    
    search_toggle = st.checkbox("Enable Automatic Google Search", value=True)
    
    st.divider()
    
    st.header("Memory Management")
    
    all_memories = st.session_state.memory_manager.get_all_memories()
    memory_count = len(all_memories)
    
    st.write(f"Current memories: {memory_count}")
    
    if st.button("Clear All Memories"):
        st.session_state.memory_manager.clear_memories()
        st.success("All memories cleared!")
    
    with st.expander("View Memories"):
        if not all_memories:
            st.write("No memories stored.")
        else:
            for i, memory in enumerate(all_memories):
                # Use a container with custom styling instead of nested expanders
                with st.container():
                    st.markdown(f"<div class='memory-item'>", unsafe_allow_html=True)
                    st.write(f"**Memory {i+1}:** {memory['content'][:30]}...")
                    st.write(f"**Content:** {memory['content']}")
                    st.write(f"**Source:** {memory['source']}")
                    st.write(f"**Timestamp:** {memory['timestamp']}")
                    if st.button(f"Delete Memory #{i+1}", key=f"delete_{i}"):
                        st.session_state.memory_manager.remove_memory(i)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
    
    st.divider()
    
    with st.expander("Created Files"):
        if not st.session_state.created_files:
            st.write("No files created yet.")
        else:
            for i, file_info in enumerate(st.session_state.created_files):
                st.write(f"**{i+1}.** {file_info['filename']} ({file_info.get('size', 'N/A')} bytes)")
    
    st.divider()
    
    st.header("System Settings")
    
    enable_notifications = st.checkbox("Enable System Notifications", value=True)
    enable_sounds = st.checkbox("Enable System Sounds", value=True)
    
    if st.button("Send Test Notification"):
        if enable_notifications:
            send_notification("Deepseek Chat", "This is a test notification")
            if enable_sounds:
                play_sound("notification")
            st.success("Test notification sent!")
        else:
            st.warning("Notifications are disabled")

# Main chat interface
col1, col2 = st.columns([3, 1])

# Add this code after initializing the session state variables in app.py
if "welcome_message" not in st.session_state:
    st.session_state.welcome_message = generate_welcome_message(st.session_state.memory_manager)

# Modify the main chat interface section to display the welcome message
with col1:
    st.title("Deepseek Chat")
    
    # Display welcome message
    if st.session_state.welcome_message:
        st.info(st.session_state.welcome_message)

    # Display search results if available
    if st.session_state.search_results:
        with st.container(height=200):
            st.markdown(
                f"<div class='search-results'>{st.session_state.search_results}</div>", 
                unsafe_allow_html=True
            )
    
    # Display chat messages
    for message in st.session_state.messages:
        role = message["role"]
        if role != "system":  # Don't show system messages
            with st.chat_message(role):
                st.write(message["content"])
    
    # Memory extraction and saving section
    if st.session_state.suggested_memory:
        with st.container():
            st.markdown(
                f"<div class='memory-section'><h3>Memory Extraction</h3></div>", 
                unsafe_allow_html=True
            )
            
            col_mem1, col_mem2 = st.columns([3, 1])
            
            with col_mem1:
                memory_content = st.text_area(
                    "AI-suggested memory (edit if needed):", 
                    value=st.session_state.suggested_memory, 
                    help="Review and edit this memory before saving"
                )
                
            with col_mem2:
                st.write("")
                st.write("")
                if st.button("Save Memory", key="save_memory"):
                    if memory_content:
                        st.session_state.memory_manager.add_memory(memory_content, "chat_extraction")
                        st.success("Memory saved!")
                        st.session_state.suggested_memory = ""
                        st.rerun()
                
                if st.button("Skip", key="skip_memory"):
                    st.session_state.suggested_memory = ""
                    st.rerun()

with col2:
    # File upload section - FIXED VERSION
    with st.container():
        st.header("Upload Files")
        
        # Generate a unique file uploader key to avoid caching issues
        uploaded_file = st.file_uploader("Choose a file", type=None, accept_multiple_files=False, key=f"file_uploader_{id(st.session_state)}")
        
        # Process file upload - Fix for infinite refresh loop
        if uploaded_file:
            st.markdown("<div class='file-upload-section'>", unsafe_allow_html=True)
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
                    st.rerun()
                except Exception as e:
                    st.error(f"Error uploading file: {str(e)}")
            st.markdown("</div>", unsafe_allow_html=True)

        else:
            # Reset the current upload ID when no file is selected
            st.session_state.current_upload_id = None
        
        if st.session_state.uploaded_files:
            with st.expander("Uploaded Files"):
                for i, file_info in enumerate(st.session_state.uploaded_files):
                    st.write(f"**{i+1}.** {file_info['filename']} ({file_info['type']})")
                    
                    # Add button to remove file
                    if st.button(f"Remove", key=f"remove_file_{i}"):
                        st.session_state.uploaded_files.pop(i)
                        st.rerun()
        
    
    # Extract memory button
    if len(st.session_state.messages) >= 1 and not st.session_state.suggested_memory:
        if st.button("Extract Memory from Conversation"):
            try:
                client = DeepseekClient(api_key=st.session_state.api_key)
                with st.spinner("Analyzing conversation..."):
                    suggested_memory = client.extract_memory(
                        [m for m in st.session_state.messages if m["role"] != "system"],
                        model=model
                    )
                    st.session_state.suggested_memory = suggested_memory
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to extract memory: {str(e)}")
# Get user input
prompt = st.chat_input("Type your message here...")

if prompt:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
        
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
        
        # Display assistant message
        with st.chat_message("assistant"):
            st.write(st.session_state.messages[-1]["content"], unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        import traceback
        st.error(traceback.format_exc())

# Controls
col_controls1, col_controls2 = st.columns(2)

with col_controls1:
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.search_results = None
        st.rerun()

with col_controls2:
    if st.session_state.created_files and st.button("Clear Created Files"):
        st.session_state.created_files = []
        st.rerun()