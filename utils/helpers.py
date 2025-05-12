# deepseek_chat/utils/helpers.py
from typing import List, Dict, Any, Optional

def format_chat_history(messages: List[Dict[str, str]]) -> str:
    """Format chat history for display."""
    formatted = []
    for msg in messages:
        role = msg["role"].capitalize()
        content = msg["content"]
        formatted.append(f"**{role}**: {content}")
    
    return "\n\n".join(formatted)

def create_system_prompt(memory_prompt: str = "", include_file_creation: bool = True) -> Dict[str, str]:
    """Create a system prompt with memory and file creation capabilities."""
    base_prompt = "You are a helpful AI assistant based on the Deepseek model. "
    
    if include_file_creation:
        base_prompt += (
            "You can create files by using the following syntax in your response:\n\n"
            "```filetype:filename\nfile content\n```\n\n"
            "For example, to create a Python file named app.py, use:\n"
            "```python:app.py\ndef hello():\n    print('Hello world')\n```\n\n"
            "For creating a complete project structure, start with:\n"
            "CREATE_PROJECT_STRUCTURE\n"
            "Then list all files inside, and end with:\n"
            "END_PROJECT_STRUCTURE\n\n"
        )
    
    if memory_prompt:
        full_prompt = f"{base_prompt}\n\n{memory_prompt}"
    else:
        full_prompt = base_prompt
        
    return {"role": "system", "content": full_prompt}

def truncate_messages_to_token_limit(messages: List[Dict[str, str]], 
                                     max_tokens: int = 7000) -> List[Dict[str, str]]:
    """Truncate messages to stay within token limits."""
    system_messages = [msg for msg in messages if msg["role"] == "system"]
    non_system_messages = [msg for msg in messages if msg["role"] != "system"]
    
    # Estimate tokens (rough approximation: 4 chars ≈ 1 token)
    total_chars = sum(len(msg["content"]) for msg in messages)
    estimated_tokens = total_chars // 4
    
    if estimated_tokens <= max_tokens:
        return messages
    
    # Keep system messages and truncate conversation history
    result = system_messages.copy()
    
    # Always keep the latest user message if it exists
    latest_user_message = None
    for i in reversed(range(len(non_system_messages))):
        if non_system_messages[i]["role"] == "user":
            latest_user_message = non_system_messages.pop(i)
            break
            
    # Add messages until we approach the limit
    remaining_tokens = max_tokens - (sum(len(msg["content"]) for msg in system_messages) // 4)
    if latest_user_message:
        remaining_tokens -= len(latest_user_message["content"]) // 4
    
    # Add messages from newest to oldest until we approach the limit
    for msg in reversed(non_system_messages):
        msg_tokens = len(msg["content"]) // 4
        if remaining_tokens - msg_tokens > 0:
            result.append(msg)
            remaining_tokens -= msg_tokens
        else:
            break
    
    # Add back the latest user message if we had one
    if latest_user_message:
        result.append(latest_user_message)
    
    # Sort messages to maintain proper conversation flow
    result.sort(key=lambda msg: 0 if msg["role"] == "system" else 1)
    
    return result
