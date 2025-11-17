#!/usr/bin/env python3
"""
Feishu Assistant Processor

This script receives inputs from GitHub Actions workflow,
processes them, and sends a message to Feishu via webhook.
"""

import os
import sys
import argparse
import requests
import json
from datetime import datetime
from typing import Dict, Any


def dummy_process(question: str, user: str, time: str) -> Dict[str, Any]:
    """
    Dummy processing function for the received inputs.
    
    Args:
        question: The question content
        user: The Feishu user
        time: The time of the question
        
    Returns:
        A dictionary containing processed information
    """
    # Dummy processing - just return the inputs for now
    return {
        "processed": True,
        "question": question,
        "user": user,
        "time": time
    }


def send_to_feishu(webhook_url: str, title: str, timestamp: str, text: str) -> bool:
    """
    Send a message to Feishu using webhook.
    
    Args:
        webhook_url: The Feishu webhook URL
        title: Message title
        timestamp: Message timestamp
        text: Message text content
        
    Returns:
        True if successful, False otherwise
    """
    if not webhook_url:
        print("Error: FEISHU_WEBHOOK_URL environment variable is not set", file=sys.stderr)
        return False
    
    # Prepare the message payload according to Feishu webhook format
    # Using a dictionary format with title, timestamp, and text fields as requested
    message_data = {
        "title": title,
        "timestamp": timestamp,
        "text": text
    }
    
    # Format the message for better readability in Feishu
    # The message_data dictionary contains: title, timestamp, text
    # Feishu webhook supports text messages with markdown formatting
    formatted_message = f"**{message_data['title']}**\n\n**Timestamp:** {message_data['timestamp']}\n\n**Content:**\n{message_data['text']}"
    
    payload = {
        "msg_type": "text",
        "content": {
            "text": formatted_message
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print("Successfully sent message to Feishu")
                return True
            else:
                print(f"Feishu API returned error: {result.get('msg', 'Unknown error')}", file=sys.stderr)
                return False
        else:
            print(f"HTTP request failed with status {response.status_code}: {response.text}", file=sys.stderr)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error sending request to Feishu: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point for the Feishu Assistant Processor."""
    parser = argparse.ArgumentParser(description="Feishu Assistant Processor")
    parser.add_argument("--question", required=True, help="Question content")
    parser.add_argument("--user", required=True, help="Feishu user")
    parser.add_argument("--time", required=True, help="Time of the question")
    
    args = parser.parse_args()
    
    # Get webhook URL from environment variable (set via GitHub secret)
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
    
    if not webhook_url:
        print("Error: FEISHU_WEBHOOK_URL environment variable is not set", file=sys.stderr)
        sys.exit(1)
    
    # Process the inputs (dummy function for now)
    processed_data = dummy_process(args.question, args.user, args.time)
    
    # Prepare message content
    # Text should contain all received inputs
    text_content = f"Question: {args.question}\nUser: {args.user}\nTime: {args.time}"
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create title
    title = "Feishu Assistant Response"
    
    # Send message to Feishu
    success = send_to_feishu(webhook_url, title, timestamp, text_content)
    
    if not success:
        print("Failed to send message to Feishu", file=sys.stderr)
        sys.exit(1)
    
    print("Processing completed successfully")


if __name__ == "__main__":
    main()

