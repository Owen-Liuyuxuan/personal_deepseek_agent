# deepseek_chat/task_manager.py
import os
import time
import threading
import datetime
import json
import schedule
from typing import Dict, Any, Optional

from api.client import DeepseekClient
from memory.manager import MemoryManager
from system_api.notifications import send_notification

class TaskManager:
    def __init__(self, memory_file: Optional[str] = None):
        """Initialize task manager."""
        self.memory_manager = MemoryManager(memory_file)
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.client = DeepseekClient(api_key=self.api_key)
        self.tasks_file = "scheduled_tasks.json"
        self.tasks = self._load_tasks()
        self.running = False
        self.thread = None
    
    def _load_tasks(self) -> Dict[str, Any]:
        """Load scheduled tasks from file."""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_tasks(self) -> None:
        """Save scheduled tasks to file."""
        with open(self.tasks_file, "w") as f:
            json.dump(self.tasks, f, indent=2)
    
    def schedule_next_run(self) -> None:
        """Determine when to run next based on memory and current context."""
        memory_prompt = self.memory_manager.get_memory_prompt()
        
        system_message = {
            "role": "system",
            "content": (
                f"Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                "Based on the user's memory information, determine when to schedule the next "
                "automated check-in. Consider any mentioned deadlines, preferences, or patterns. "
                "Output a JSON with:\n"
                "- 'next_run_minutes': minutes until next run (15-1440)\n"
                "- 'reason': brief explanation for this timing\n"
                "- 'task': suggested task to perform at next run"
            )
        }
        
        user_message = {
            "role": "user",
            "content": f"User memory information:\n{memory_prompt}"
        }
        
        try:
            response = self.client.chat_completion(
                messages=[system_message, user_message],
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=200
            )
            
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            
            # Extract JSON from potentially messy content
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
            
            # Get minutes until next run (default to 60 minutes if not specified)
            minutes = min(max(int(result.get("next_run_minutes", 60)), 15), 1440)
            reason = result.get("reason", "Regular check-in")
            task = result.get("task", "Check for updates")
            
            # Schedule next run
            next_run_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            self.tasks["next_run"] = {
                "time": next_run_time.isoformat(),
                "reason": reason,
                "task": task
            }
            self._save_tasks()
            
            print(f"Next run scheduled for {next_run_time} ({minutes} minutes from now)")
            print(f"Reason: {reason}")
            print(f"Task: {task}")
            
            return minutes
            
        except Exception as e:
            print(f"Error scheduling next run: {str(e)}")
            # Default to 60 minutes if there's an error
            return 60
    
    def perform_scheduled_task(self) -> None:
        """Perform the scheduled task based on memory."""
        if "next_run" not in self.tasks:
            print("No scheduled task found")
            self.schedule_next_run()
            return
        
        task_info = self.tasks["next_run"]
        task = task_info.get("task", "Check for updates")
        
        memory_prompt = self.memory_manager.get_memory_prompt()
        
        system_message = {
            "role": "system",
            "content": (
                f"Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"You need to perform this scheduled task: {task}\n\n"
                "Based on the user's memory information, determine what action to take. "
                "Output a JSON with:\n"
                "- 'action': what action to take (options: 'notify', 'remember', 'none')\n"
                "- 'message': message for notification or memory\n"
                "- 'priority': priority level (1-5, where 5 is highest)"
            )
        }
        
        user_message = {
            "role": "user",
            "content": f"User memory information:\n{memory_prompt}"
        }
        
        try:
            response = self.client.chat_completion(
                messages=[system_message, user_message],
                model="deepseek-chat",
                temperature=0.5,
                max_tokens=300
            )
            
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            
            # Extract JSON from potentially messy content
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
            
            action = result.get("action", "none")
            message = result.get("message", "")
            priority = min(max(int(result.get("priority", 3)), 1), 5)
            
            if action == "notify" and message:
                from system_api.notifications import send_notification
                send_notification("Deepseek Assistant", message, priority)
                
            elif action == "remember" and message:
                self.memory_manager.add_memory(message, "automated_task")
                
            # Schedule next run
            self.schedule_next_run()
            
        except Exception as e:
            print(f"Error performing scheduled task: {str(e)}")
            # Schedule next run anyway
            self.schedule_next_run()
    
    def _run_scheduler(self) -> None:
        """Run the scheduler in a loop."""
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def start(self) -> None:
        """Start the task manager."""
        if self.running:
            return
        
        self.running = True
        
        # Schedule initial task
        minutes = self.schedule_next_run()
        schedule.every(minutes).minutes.do(self.perform_scheduled_task)
        
        # Start scheduler in a separate thread
        self.thread = threading.Thread(target=self._run_scheduler)
        self.thread.daemon = True
        self.thread.start()
        
        print("Task manager started")
    
    def stop(self) -> None:
        """Stop the task manager."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        print("Task manager stopped")