# deepseek_chat/utils/helpers.py
from typing import List, Dict, Any, Optional
import datetime

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
    base_prompt = "You are a helpful AI assistant. Response should follow the defined formats and requirements."
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if include_file_creation:
        base_prompt += (
            f"Current time: {current_time}\n\n"
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

# Add this function after the existing imports
def generate_welcome_message(memory_manager,client):
    """Generate a welcome message based on memories and current time."""
    import datetime
    
    current_hour = datetime.datetime.now().hour
    
    # Time-based greeting
    if 5 <= current_hour < 12:
        greeting = "Good morning"
    elif 12 <= current_hour < 18:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    
    # Get memories for personalization
    memories = memory_manager.get_all_memories()
    
    memory_prompt = memory_manager.get_memory_prompt()
    
    system_message = {
        "role": "system",
        "content": (
            f"Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            "You are an AI assistant that can generate personalized messages in Chinese, English or Japanese."
            "Generate a warm, personalized welcome message (max 2 sentences) based on the user's "
            "previous interactions and the current time of day. Be conversational and friendly. Return only the welcoming message.\n\n"
        )
    }
    
    user_message = {
        "role": "user",
        "content": f"Time-based greeting: {greeting}\n\nUser memory information:\n{memory_prompt}"
    }
    
    response = client.chat_completion(
        messages=[system_message, user_message],
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=100
    )
    
    welcome_message = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    return welcome_message or f"{greeting}! How can I assist you today?"
