import csv
import smtplib
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from pathlib import Path
import time
# import zipfile
# import shutil
from threading import Thread, Event
import atexit

# ============= CONFIGURATION =============

config_file = "config.json"
app_state_file = "data/app_state.json"

# Global scheduler control
scheduler_stop_event = Event()
scheduler_thread = None

default_config = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",
    "sender_name": "Muhammad Adan",
    "use_tls": True,
    "log_file": "logs/email_log.txt",
    "delay_between_emails": 1,  # seconds
    "max_retries": 3,
    "retry_delay": 1  # initial retry delay in seconds
}

# ============= CONFIG MANAGEMENT =============

def load_config() -> Dict:
    """Load configuration from JSON file or create default."""
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Merge with defaults to ensure all keys exist
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    else:
        # Create default config file
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def get_config() -> Dict:
    """Get current configuration."""
    return load_config()

def save_config(config: Dict):
    """Save configuration to JSON file."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        print("Configuration saved successfully")
    except Exception as e:
        print(f"Error saving config: {e}")

# ============= APP STATE PERSISTENCE =============

def save_app_state(state: Dict):
    """Save application state to local storage for persistence across restarts."""
    try:
        os.makedirs(os.path.dirname(app_state_file), exist_ok=True)
        with open(app_state_file, 'w') as f:
            json.dump(state, f, indent=4)
        print("App state saved successfully")
    except Exception as e:
        print(f"Error saving app state: {e}")

def load_app_state() -> Dict:
    """Load application state from local storage."""
    default_state = {
        "csv_file": None,
        "attachment_files": [],
        "last_subject": "",
        "last_body": "",
        "last_updated": None
    }
    
    if os.path.exists(app_state_file):
        try:
            with open(app_state_file, 'r') as f:
                state = json.load(f)
                # Merge with defaults
                for key, value in default_state.items():
                    if key not in state:
                        state[key] = value
                return state
        except Exception as e:
            print(f"Error loading app state: {e}")
            return default_state
    return default_state






# ============= SCHEDULED EMAIL SENDING =============

def schedule_email_send(csv_file: str, email_template: str, 
                       send_date: str, send_time: str,
                       subject_template: str = "", 
                       attachment_paths: Optional[List[str]] = None,
                       is_html: bool = False) -> Dict:
    
    try:
        # Parse the scheduled date and time
        scheduled_datetime_str = f"{send_date} {send_time}"
        scheduled_datetime = datetime.strptime(scheduled_datetime_str, "%Y-%m-%d %H:%M")
        
        # Validate that scheduled time is in the future
        now = datetime.now()
        if scheduled_datetime <= now:
            return {
                "is_scheduled": False,
                "scheduled_time": scheduled_datetime_str,
                "campaign_id": None,
                "message": "Failed: Scheduled time must be in the future",
                "error": f"Scheduled time ({scheduled_datetime_str}) is in the past or now"
            }
        

        
        # Create unique campaign ID using timestamp
        campaign_id = f"scheduled_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Save schedule configuration to JSON file for later retrieval
        schedule_config = {
            "campaign_id": campaign_id,
            "csv_file": csv_file,
            "email_template": email_template,
            "subject_template": subject_template,
            "scheduled_datetime": scheduled_datetime_str,
            "attachment_paths": attachment_paths,
            "is_html": is_html,
            "created_at": datetime.now().isoformat(),
            "status": "scheduled"
        }
        
        # Save to schedule file
        schedule_file = f"data/schedule_{campaign_id}.json"
        os.makedirs(os.path.dirname(schedule_file), exist_ok=True)
        
        with open(schedule_file, 'w') as f:
            json.dump(schedule_config, f, indent=4)
        
        # Calculate wait time
        wait_time = scheduled_datetime - now
        wait_hours = wait_time.total_seconds() / 3600
        
        print(f"✓ Email campaign scheduled successfully")
        print(f"  Campaign ID: {campaign_id}")
        print(f"  Scheduled for: {scheduled_datetime_str}")
        print(f"  Wait time: {wait_hours:.1f} hours")
        print(f"  Recipients: {len(read_csv_recipients(csv_file))}")
        print(f"  Config saved to: {schedule_file}")
        
        return {
            "is_scheduled": True,
            "scheduled_time": scheduled_datetime_str,
            "campaign_id": campaign_id,
            "message": f"Campaign '{campaign_id}' scheduled successfully for {scheduled_datetime_str}",
            "wait_hours": wait_hours,
            "config_file": schedule_file
        }
        
    except ValueError as e:
        return {
            "is_scheduled": False,
            "scheduled_time": None,
            "campaign_id": None,
            "message": "Failed: Invalid date/time format",
            "error": f"Date must be YYYY-MM-DD, Time must be HH:MM. Error: {e}"
        }
    except Exception as e:
        print(f"Error scheduling emails: {e}")
        return {
            "is_scheduled": False,
            "scheduled_time": None,
            "campaign_id": None,
            "message": "Failed: Unknown error",
            "error": str(e)
        }


def execute_scheduled_campaign(campaign_id: str) -> Dict:
    
    try:
        schedule_file = f"data/schedule_{campaign_id}.json"
        
        if not os.path.exists(schedule_file):
            return {
                "success": False,
                "error": f"Schedule file not found for campaign: {campaign_id}"
            }
        
        # Load schedule configuration
        with open(schedule_file, 'r') as f:
            schedule_config = json.load(f)
        
        print(f"Executing scheduled campaign: {campaign_id}")
        
        # Send emails using existing bulk send function
        results = send_bulk_emails(
            csv_file=schedule_config["csv_file"],
            email_template=schedule_config["email_template"],
            subject_template=schedule_config["subject_template"],
            attachment_paths=schedule_config.get("attachment_paths"),
            is_html=schedule_config["is_html"]
        )
        
        # Update schedule status
        schedule_config["status"] = "completed"
        schedule_config["executed_at"] = datetime.now().isoformat()
        
        with open(schedule_file, 'w') as f:
            json.dump(schedule_config, f, indent=4)
        
        print(f"Campaign {campaign_id} executed. Results: {results}")
        return results
        
    except Exception as e:
        print(f"Error executing scheduled campaign: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============= BACKGROUND SCHEDULER =============

def check_and_execute_due_campaigns(callback=None):
    
    executed = []
    schedule_dir = "data"
    
    if not os.path.exists(schedule_dir):
        return executed
    
    now = datetime.now()
    
    try:
        for file_name in os.listdir(schedule_dir):
            if file_name.startswith("schedule_") and file_name.endswith(".json"):
                file_path = os.path.join(schedule_dir, file_name)
                
                try:
                    with open(file_path, 'r') as f:
                        schedule_config = json.load(f)
                    
                    # Skip if not scheduled status
                    if schedule_config.get("status") != "scheduled":
                        continue
                    
                    # Parse scheduled time
                    scheduled_time = datetime.strptime(
                        schedule_config["scheduled_datetime"], 
                        "%Y-%m-%d %H:%M"
                    )
                    
                    # Check if it's time to execute (within 1 minute window)
                    if scheduled_time <= now:
                        print(f"[SCHEDULER] Executing due campaign: {schedule_config['campaign_id']}")
                        
                        # Mark as executing to prevent duplicate runs
                        schedule_config["status"] = "executing"
                        with open(file_path, 'w') as f:
                            json.dump(schedule_config, f, indent=4)
                        
                        # Execute the campaign
                        result = execute_scheduled_campaign(schedule_config["campaign_id"])
                        result["campaign_id"] = schedule_config["campaign_id"]
                        executed.append(result)
                        
                        # Notify callback if provided
                        if callback:
                            callback(schedule_config["campaign_id"], result)
                        
                        print(f"[DONE] Campaign {schedule_config['campaign_id']} executed: {result}")
                        
                except Exception as e:
                    print(f"Error processing schedule file {file_path}: {e}")
                    
    except Exception as e:
        print(f"Error checking due campaigns: {e}")
    
    return executed


def start_background_scheduler(check_interval: int = 30, callback=None):
    
    global scheduler_thread, scheduler_stop_event
    
    # Stop existing scheduler if running
    stop_background_scheduler()
    
    scheduler_stop_event.clear()
    
    def scheduler_loop():
        print(f"[SCHEDULER] Background scheduler started (checking every {check_interval}s)")
        
        while not scheduler_stop_event.is_set():
            try:
                # Check and execute due campaigns
                executed = check_and_execute_due_campaigns(callback)
                
                if executed:
                    print(f"Scheduler executed {len(executed)} campaign(s)")
                    
            except Exception as e:
                print(f"Scheduler error: {e}")
            
            # Wait for next check or stop signal
            scheduler_stop_event.wait(timeout=check_interval)
        
        print("[SCHEDULER] Background scheduler stopped")
    
    scheduler_thread = Thread(target=scheduler_loop, daemon=True, name="EmailScheduler")
    scheduler_thread.start()
    
    return scheduler_thread


def stop_background_scheduler():
    """Stop the background scheduler thread."""
    global scheduler_thread, scheduler_stop_event
    
    if scheduler_thread and scheduler_thread.is_alive():
        print("Stopping background scheduler...")
        scheduler_stop_event.set()
        scheduler_thread.join(timeout=5)
        scheduler_thread = None


def is_scheduler_running() -> bool:
    """Check if the background scheduler is currently running."""
    global scheduler_thread
    return scheduler_thread is not None and scheduler_thread.is_alive()


# Register cleanup on exit
atexit.register(stop_background_scheduler)



def read_csv_recipients(csv_file: str) -> List[Dict]:
    """Read recipient data from CSV file."""
    recipients = []
    
    if not os.path.exists(csv_file):
        print(f"CSV file not found: {csv_file}")
        return recipients
    
    try:
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Ensure required fields exist
                if 'name' in row and 'email' in row:
                    recipients.append({
                        'name': row.get('name', '').strip(),
                        'email': row.get('email', '').strip(),
                        'custom_message': row.get('custom_message', '').strip(),
                        'subject': row.get('subject', '').strip()
                    })
                else:
                    print(f"Skipping row with missing required fields: {row}")
                    
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        
    return recipients

# ============= EMAIL FORMATTING =============

def format_email_content(recipient: Dict, template: str, subject_template: str = "") -> tuple:
    """Format email content using template and recipient data."""
    name = recipient.get('name', 'Valued Customer')
    custom_message = recipient.get('custom_message', '')
    
    # Format subject
    if subject_template:
        subject = subject_template.replace('{name}', name)
    else:
        subject = recipient.get('subject', 'Important Message')
    
    # Format body
    body = template.replace('{name}', name)
    if '{custom_message}' in body and custom_message:
        body = body.replace('{custom_message}', custom_message)
    else:
        body = body.replace('{custom_message}', '')
    
    return subject, body

# ============= BULK EMAIL SENDING WITH RATE LIMITING =============

def send_bulk_emails(csv_file: str, email_template: str, 
                     subject_template: str = "", 
                     attachment_paths: Optional[List[str]] = None,
                     is_html: bool = False) -> Dict:
    
    config = get_config()
    delay = config.get("delay_between_emails", 2)
    
    recipients = read_csv_recipients(csv_file)
    
    if not recipients:
        print("No valid recipients found")
        return {"total": 0, "sent": 0, "failed": 0, "errors": ["No valid recipients found"]}
    

    
    results = {
        "total": len(recipients),
        "sent": 0,
        "failed": 0,
        "errors": [],
        "start_time": datetime.now().isoformat()
    }
    
    # Log the start of bulk sending with configuration info
    print(f"Starting bulk email send to {len(recipients)} recipients")
    print(f"Delay between emails: {delay}s | Max retries: {config.get('max_retries', 3)}")
    
    # Log attachment info if present
    if attachment_paths:
        for path in attachment_paths:
            print(f"Attachment: {os.path.basename(path)}")
    
    for index, recipient in enumerate(recipients, 1):
        try:
            # Format email content
            subject, body = format_email_content(recipient, email_template, subject_template)
            
            # Send email
            try:
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                from email.mime.base import MIMEBase
                from email import encoders
                
                # Create message
                msg = MIMEMultipart()
                msg['From'] = f"{config['sender_name']} <{config['sender_email']}>"
                msg['To'] = recipient['email']
                msg['Subject'] = subject
                
                # Add body
                body_type = 'html' if is_html else 'plain'
                msg.attach(MIMEText(body, body_type))
                
                # Add attachments if present
                if attachment_paths:
                    for attachment_path in attachment_paths:
                        if os.path.exists(attachment_path):
                            with open(attachment_path, "rb") as attachment:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(attachment.read())
                                encoders.encode_base64(part)
                                part.add_header(
                                    'Content-Disposition',
                                    f'attachment; filename= {os.path.basename(attachment_path)}'
                                )
                                msg.attach(part)
                
                # Connect to server and send email
                server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=10)
                
                if config['use_tls']:
                    server.starttls()
                
                server.login(config['sender_email'], config['sender_password'])
                
                text = msg.as_string()
                server.sendmail(config['sender_email'], recipient['email'], text)
                server.quit()
                
                # Log success
                results["sent"] += 1
                print(f"[{index}/{len(recipients)}] ✓ Sent to {recipient['email']}")
                
            except Exception as e:
                results["failed"] += 1
                error_msg = f"Failed to send to {recipient['name']} ({recipient['email']}): {e}"
                results["errors"].append(error_msg)
                print(f"[{index}/{len(recipients)}] ✗ {error_msg}")
            
            # Rate limiting - delay before next email
            if index < len(recipients):
                print(f"Waiting {delay}s before next email...")
                # Pause execution for specified seconds
                time.sleep(delay)
                    
        except Exception as e:
            results["failed"] += 1
            error_msg = f"Error processing {recipient.get('email', 'unknown')}: {e}"
            results["errors"].append(error_msg)
            print(error_msg)
    
    # Log summary with visual formatting
    results["end_time"] = datetime.now().isoformat()
    print(f"\n{'='*60}")  # Separator line
    print(f"BULK EMAIL SUMMARY")

    print(f"{'='*60}")
    print(f"Total Recipients: {results['total']}")
    print(f"Successfully Sent: {results['sent']}")
    print(f"Failed: {results['failed']}")
    print(f"{'='*60}\n")
    
    return results
