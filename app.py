# deepseek_chat/app.py
import streamlit as st
import os
from typing import List, Dict, Any

# Import our new modules
from system_api.task_manager import TaskManager, initialize_session_state, process_user_message
from ui.components import (
    render_sidebar, 
    render_chat_interface, 
    render_controls
)

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

# Initialize the task manager
# task_manager = TaskManager()

# Initialize session state
initialize_session_state()

# Render the sidebar and get settings
settings = render_sidebar()

# Render the main chat interface
col1, col2 = render_chat_interface()

# Get user input
prompt = st.chat_input("Type your message here...")

if prompt:
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Process the user message
    success = process_user_message(
        prompt=prompt,
        model=settings["model"],
        temperature=settings["temperature"],
        search_toggle=settings["search_toggle"]
    )
    
    if success:
        # Display assistant message
        with st.chat_message("assistant"):
            st.write(st.session_state.messages[-1]["content"], unsafe_allow_html=True)
        
        # Play notification sound if enabled
        if settings["enable_notifications"]:
            from system_api.notifications import send_notification, play_sound
            send_notification("Deepseek Chat", "New response received")
            if settings["enable_sounds"]:
                play_sound("notification")
    
    st.rerun()

# Render control buttons
render_controls()