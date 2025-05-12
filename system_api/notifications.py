# deepseek_chat/system_api/notifications.py
import os
import subprocess
import platform
from typing import Optional

def send_notification(title: str, message: str, priority: int = 3) -> bool:
    """Send a system notification with the given title and message.
    
    Args:
        title: The notification title
        message: The notification message
        priority: Priority level (1-5, where 5 is highest)
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    system = platform.system()
    
    try:
        if system == "Linux":
            # Use notify-send on Linux
            urgency = "low"
            if priority >= 4:
                urgency = "critical"
            elif priority >= 2:
                urgency = "normal"
                
            subprocess.run([
                "notify-send",
                f"--urgency={urgency}",
                title,
                message
            ])
            return True
            
        elif system == "Darwin":  # macOS
            # Use osascript on macOS
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script])
            return True
            
        elif system == "Windows":
            # Use PowerShell on Windows
            script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            
            $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
            $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
            $text = $xml.GetElementsByTagName("text")
            $text[0].AppendChild($xml.CreateTextNode("{title}"))
            $text[1].AppendChild($xml.CreateTextNode("{message}"))
            
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Deepseek Chat").Show($toast)
            """
            subprocess.run(["powershell", "-Command", script])
            return True
            
        return False
    
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return False

def play_sound(sound_name: str = "notification") -> bool:
    """Play a system sound.
    
    Args:
        sound_name: Name of the sound to play (notification, alert, etc.)
        
    Returns:
        bool: True if sound was played successfully, False otherwise
    """
    system = platform.system()
    
    try:
        if system == "Linux":
            # Use paplay on Linux
            sounds = {
                "notification": "/usr/share/sounds/freedesktop/stereo/message.oga",
                "alert": "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
                "complete": "/usr/share/sounds/freedesktop/stereo/complete.oga"
            }
            
            sound_file = sounds.get(sound_name, sounds["notification"])
            if os.path.exists(sound_file):
                subprocess.run(["paplay", sound_file])
                return True
                
        elif system == "Darwin":  # macOS
            # Use afplay on macOS
            sounds = {
                "notification": "/System/Library/Sounds/Ping.aiff",
                "alert": "/System/Library/Sounds/Sosumi.aiff",
                "complete": "/System/Library/Sounds/Glass.aiff"
            }
            
            sound_file = sounds.get(sound_name, sounds["notification"])
            subprocess.run(["afplay", sound_file])
            return True
            
        elif system == "Windows":
            # Use PowerShell on Windows
            sounds = {
                "notification": "Notification.Default",
                "alert": "Notification.Looping.Alarm",
                "complete": "Notification.Default"
            }
            
            sound = sounds.get(sound_name, sounds["notification"])
            script = f"""
            (New-Object Media.SoundPlayer).PlaySync([System.IO.Path]::Combine([Environment]::GetFolderPath('Windows'), 'Media', '{sound}.wav'))
            """
            subprocess.run(["powershell", "-Command", script])
            return True
            
        return False
    
    except Exception as e:
        print(f"Error playing sound: {str(e)}")
        return False