# deepseek_chat/file_handlers/creator.py
import os
import tempfile
import zipfile
import io
from typing import Dict, List, Any, Optional
import base64
from datetime import datetime

class FileCreationHandler:
    def __init__(self, output_dir: Optional[str] = None):
        """Initialize file creation handler."""
        self.output_dir = output_dir or os.path.join(tempfile.gettempdir(), "deepseek_chat_files")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Create a file with the given name and content."""
        # Create nested directories if needed
        full_path = os.path.join(self.output_dir, filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        file_info = {
            "filename": filename,
            "path": full_path,
            "size": os.path.getsize(full_path),
            "created_at": datetime.now().isoformat()
        }
        
        return file_info
    
    def create_directory_structure(self, file_list: List[Dict[str, str]]) -> str:
        """Create a directory structure from a list of files and return the zip path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"project_{timestamp}.zip"
        zip_path = os.path.join(self.output_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for file_info in file_list:
                filename = file_info.get("filename", "")
                content = file_info.get("content", "")
                
                # Add file to zip
                zipf.writestr(filename, content)
        
        return zip_path
    
    def get_download_link_html(self, file_path: str, button_text: str = "Download Files") -> str:
        """Generate an HTML download link for the created file."""
        with open(file_path, "rb") as f:
            bytes_data = f.read()
            b64 = base64.b64encode(bytes_data).decode()
            
        filename = os.path.basename(file_path)
        href = f"data:application/zip;base64,{b64}"
        
        html = f"""
        <a href="{href}" download="{filename}" style="text-decoration:none;">
            <button style="
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 12px 30px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 16px;
                margin: 4px 2px;
                cursor: pointer;
                border-radius: 8px;">
                {button_text}
            </button>
        </a>
        """
        return html
