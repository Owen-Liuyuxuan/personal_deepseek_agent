# deepseek_chat/utils/parsers.py
import re
from typing import List, Dict, Any, Tuple

def parse_file_creations(response_text: str) -> List[Dict[str, str]]:
    """
    Parse response text to extract file creation directives.
    
    Format: ```filetype:filename
    content
    ```
    """
    files = []
    
    # Pattern matches: ```filetype:filename\ncontent\n```
    pattern = r"```(\w+):([\w\.\-\/]+)\n(.*?)```"
    matches = re.finditer(pattern, response_text, re.DOTALL)
    
    for match in matches:
        file_type = match.group(1)
        filename = match.group(2)
        content = match.group(3)
        
        # Ensure filename has appropriate extension
        if not filename.endswith(f".{file_type}") and file_type not in ["bash", "sh", "markdown"]:
            filename = f"{filename}.{file_type}"
        elif file_type == "markdown" and not filename.endswith(".md"):
            filename = f"{filename}.md"
        elif file_type in ["bash", "sh"] and not filename.endswith(".sh"):
            filename = f"{filename}.sh"
            
        files.append({
            "filename": filename,
            "file_type": file_type,
            "content": content
        })
    
    return files

def extract_response_without_files(response_text: str) -> str:
    """Extract the response text without the file creation blocks."""
    pattern = r"```\w+:[\w\.\-\/]+\n.*?```"
    return re.sub(pattern, "", response_text, flags=re.DOTALL).strip()

def check_for_directory_structure(response_text: str) -> Tuple[bool, List[Dict[str, str]]]:
    """Check if the response contains a directory structure creation directive."""
    if "CREATE_PROJECT_STRUCTURE" in response_text:
        # Extract files within the directive
        pattern = r"CREATE_PROJECT_STRUCTURE\s*\n(.*?)END_PROJECT_STRUCTURE"
        match = re.search(pattern, response_text, re.DOTALL)
        
        if match:
            structure_block = match.group(1)
            files = parse_file_creations(structure_block)
            return True, files
    
    return False, []
