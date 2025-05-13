# deepseek_chat/ui/components.py
import streamlit as st
from typing import List, Dict, Any

def render_sidebar():
    """Render the sidebar with settings and memory management."""
    from system_api.notifications import send_notification, play_sound
    
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
        
        render_memory_management()
        
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
                
        return {
            "model": model,
            "temperature": temperature,
            "search_toggle": search_toggle,
            "enable_notifications": enable_notifications,
            "enable_sounds": enable_sounds
        }

def render_memory_management():
    """Render the memory management section in the sidebar."""
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

def render_chat_interface():
    """Render the main chat interface."""
    col1, col2 = st.columns([3, 1])
    
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
        
        render_memory_extraction()
    
    with col2:
        render_file_upload()
        
        # Extract memory button
        if len(st.session_state.messages) >= 1 and not st.session_state.suggested_memory:
            if st.button("Extract Memory from Conversation"):
                from system_api.task_manager import extract_memory_from_conversation
                extract_memory_from_conversation("deepseek-chat")
                st.rerun()
    
    return col1, col2

def render_memory_extraction():
    """Render the memory extraction and saving section."""
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

def render_file_upload():
    """Render the file upload section."""
    from system_api.task_manager import process_file_upload
    
    with st.container():
        st.header("Upload Files")
        
        # Generate a unique file uploader key to avoid caching issues
        uploaded_file = st.file_uploader("Choose a file", type=None, accept_multiple_files=False, key=f"file_uploader_{id(st.session_state)}")
        
        # Process file upload - Fix for infinite refresh loop
        if uploaded_file:
            st.markdown("<div class='file-upload-section'>", unsafe_allow_html=True)
            if process_file_upload(uploaded_file):
                st.rerun()
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

def render_controls():
    """Render the control buttons at the bottom of the interface."""
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
