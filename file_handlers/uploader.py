# deepseek_chat/file_handlers/uploader.py
import os
import tempfile
from typing import Dict, Any, BinaryIO, Optional, List
import base64
import mimetypes
import pathlib
import PyPDF2
import docx
import json

class FileUploadHandler:
    def __init__(self, upload_dir: Optional[str] = None):
        """Initialize file upload handler."""
        self.upload_dir = upload_dir or tempfile.gettempdir()
        os.makedirs(self.upload_dir, exist_ok=True)
    
    def save_uploaded_file(self, uploaded_file: BinaryIO) -> Dict[str, Any]:
        """Save an uploaded file and return its metadata."""
        file_path = os.path.join(self.upload_dir, uploaded_file.name)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        file_info = {
            "filename": uploaded_file.name,
            "path": file_path,
            "size": os.path.getsize(file_path),
            "type": mimetypes.guess_type(file_path)[0] or "application/octet-stream",
            "extension": pathlib.Path(file_path).suffix.lower(),
        }
        
        # Extract content if it's a text-based file
        content = self._extract_file_content(file_path, file_info["extension"])
        if content:
            file_info["content"] = content
            
        return file_info
    
    def _extract_file_content(self, file_path: str, extension: str) -> Optional[str]:
        """Extract content from file based on its type."""
        try:
            # Handle text files
            if extension in [".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv", '.ini']:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            
            # Handle PDF files
            elif extension == ".pdf":
                text = ""
                with open(file_path, "rb") as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page_num in range(len(pdf_reader.pages)):
                        text += pdf_reader.pages[page_num].extract_text() + "\n"
                return text
            
            # Handle Word documents
            elif extension in [".docx", ".doc"]:
                doc = docx.Document(file_path)
                return "\n".join([para.text for para in doc.paragraphs])
                
            # Handle JSON files
            elif extension == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.dumps(json.load(f), indent=2)
                    
            return None
        except Exception as e:
            print(f"Error extracting content from file: {str(e)}")
            return None
    
    def format_file_context(self, file_info: Dict[str, Any]) -> str:
        """Format file information for inclusion in the conversation."""
        context = f"File: {file_info['filename']} ({file_info['type']}, {file_info['size']} bytes)\n\n"
        
        if "content" in file_info:
            # Truncate very large content
            content = file_info["content"]
            if len(content) > 8000:
                content = content[:4000] + "\n...[content truncated]...\n" + content[-4000:]
            
            context += f"Content:\n```{file_info['extension'][1:]}\n{content}\n```"
        else:
            context += "[This file type cannot be displayed directly]"
            
        return context
