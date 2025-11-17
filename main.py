#!/usr/bin/env python3
"""
Feishu Assistant Processor

This script receives inputs from GitHub Actions workflow,
processes them using the Personal Assistant system,
and sends a message to Feishu via webhook.
"""

import os
import sys
import argparse
import requests
import json
import logging
from datetime import datetime
from typing import Dict, Any

from assistant.core.config import Config
from assistant.core.orchestrator import PersonalAssistantOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    print(f"Sending message to Feishu: {title}, {timestamp}, {text}")
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
    
    # Initialize configuration
    logger.info("Initializing configuration...")
    config = Config()
    
    # Validate configuration
    validation = config.validate()
    if not validation["valid"]:
        logger.error(f"Configuration validation failed. Missing: {validation['missing']}")
        print(f"Error: Missing required configuration: {', '.join(validation['missing'])}", file=sys.stderr)
        sys.exit(1)
    
    # Get webhook URL from environment variable (set via GitHub secret)
    webhook_url = config.feishu_webhook_url
    
    if not webhook_url:
        print("Error: FEISHU_WEBHOOK_URL environment variable is not set", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Initialize orchestrator
        logger.info("Initializing Personal Assistant Orchestrator...")
        orchestrator = PersonalAssistantOrchestrator(config)
        
        # Process the question
        logger.info(f"Processing question from {args.user}...")
        result = orchestrator.process_question(
            question=args.question,
            user=args.user,
            time=args.time
        )
        
        # Prepare message content
        # Only include the answer, no metadata
        answer = result.get("answer", "I apologize, but I couldn't generate a response.")
        
        # Clean up the answer - remove any generic greetings if it's a real question
        if args.question and len(args.question) > 10:
            # Remove generic greetings that don't answer the question
            generic_greetings = [
                "hello! how can i help you today?",
                "hello! how can i help you?",
                "how can i help you today?",
                "how can i help you?",
            ]
            answer_lower = answer.lower().strip()
            if any(greeting in answer_lower for greeting in generic_greetings):
                # If answer is just a greeting, try to get a better response
                logger.warning("Received generic greeting instead of answer, this should not happen")
        
        text_content = answer
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create title
        title = "Personal Assistant Response"
        
        # Send message to Feishu
        logger.info("Sending response to Feishu...")
        success = send_to_feishu(webhook_url, title, timestamp, text_content)
        
        if not success:
            print("Failed to send message to Feishu", file=sys.stderr)
            sys.exit(1)
        
        logger.info("Processing completed successfully")
        print("Processing completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        print(f"Error: {str(e)}", file=sys.stderr)
        
        # Try to send error message to Feishu
        try:
            error_text = f"An error occurred while processing your question:\n\n{str(e)}\n\nQuestion: {args.question}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            send_to_feishu(webhook_url, "Error", timestamp, error_text)
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()

