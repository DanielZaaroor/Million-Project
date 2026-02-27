import os
import json
import re
import sqlite3
import pika
import requests
import time

# --- Configuration ---
# We read these from the docker-compose environment variables
RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE_NAME = "whatsapp_events"
LOG_FILE = "message_log.json"
# Docker internal networking: we talk to the 'wuzapi' container directly
WUZAPI_HOST = "http://wuzapi:8080" 
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
TARGET_GROUP_JID = os.getenv("TARGET_GROUP_JID")
ALERT_GROUP_JID = os.getenv("ALERT_GROUP_JID")

# --- Database Setup (Persistence) ---
# This file lives in the mapped volume, so it survives restarts
DB_PATH = "/app/data/groupstate.db" 

# Ensure the directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
# Create the table if it's the first time running
cursor.execute("""
    CREATE TABLE IF NOT EXISTS state (
        group_jid TEXT PRIMARY KEY,
        last_number INTEGER,
        last_sender TEXT
    )
""")
conn.commit()

# --- Helper Functions ---

def get_CurrData(group_jid):
    """Fetch the last valid number and sender from the DB."""
    cursor.execute("SELECT last_number, last_sender FROM state WHERE group_jid=?", (group_jid,))
    return cursor.fetchone()

def update_state(group_jid, number, sender):
    """Save the new valid number to the DB."""
    cursor.execute("INSERT OR REPLACE INTO state (group_jid, last_number, last_sender) VALUES (?,?,?)",
                   (group_jid, number, sender))
    conn.commit()

def send_alert(message, mentions=None):
    """Sends a warning message to the group via WuzAPI."""
    print(f" [!] SENDING ALERT: {message}")
    url = f"{WUZAPI_HOST}/chat/send/text"
    headers = { "Token": ADMIN_TOKEN, "Content-Type": "application/json",}
    payload = { "Phone": ALERT_GROUP_JID, "Body": f"⚠️Counting Compromised: {message}" }
    if mentions:
        payload["Mentions"] = mentions
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f" [!!] Failed to send alert: {e}")


# --- Core Logic ---

def callback(ch, method, properties, body):
    try:
        event = json.loads(body)
        
        # 1. Filter: Only Message events
        if event.get("event") != "Message" and event.get("type") != "Message":
            return

        data = event.get("Data", {}) or event.get("Info", {})   
        
        # 2. Filter: Target Group Only
        msg_source = data.get("Chat")
        if msg_source != TARGET_GROUP_JID:
            return

        # 3. Extract Text
        message_content = event.get("Message", {})
        text = ""
        if "conversation" in message_content:
            text = message_content["conversation"]
        elif "extendedTextMessage" in message_content:
            text = message_content["extendedTextMessage"].get("text", "")
        elif "imageMessage" in message_content:
            text = message_content["imageMessage"].get("caption", "")
        
        sender = data.get("Sender")

        # 4. Find ALL numbers in the message
        # re.findall returns a list of all strings that match digits
        found_numbers = re.findall(r'\d+', text)
        
        # RULE: No number in message
        if not found_numbers:
            send_alert(f"@{sender.split('@')[0]} sent a message with NO numbers!", [sender])
            return

        # 5. Logic: Find the valid Number
        currData = get_CurrData(TARGET_GROUP_JID)
                
        if currData:
            last_number, last_sender = currData
        else: #first run
            return
        
        # RULE: No double messages from same sender
        if sender == last_sender:
            send_alert(f"Double Count! @{sender.split('@')[0]} sent 2 messages in a row.", [sender])
            return

        # Check if ANY of the found numbers is the correct next number (n+1)
        valid_number_found = None
        
        for num_str in found_numbers:
            num = int(num_str)
            if num == last_number + 1:
                valid_number_found = num
                break # Found it! Stop looking at other numbers in the same message.

        # 6. Verdict
        if valid_number_found:
            # SUCCESS
            update_state(TARGET_GROUP_JID, valid_number_found, sender)
            print(f" [✓] Valid count: {valid_number_found} by {sender}")
        else:
            # We found numbers, but none of them were the correct next number
            # Alert with what we found vs what we expected
            found_str = ", ".join(found_numbers)
            send_alert(f"Wrong Number! @{sender.split('@')[0]} wrote [{found_str}], expected {last_number + 1}.", [sender])

    except Exception as e:
        print(f" [!] Error processing message: {e}")

# --- Startup Boilerplate ---
def main():
    print(f" [*] Logic Engine Starting... Connecting to {RABBIT_URL}")
    while True:
        try:
            params = pika.URLParameters(RABBIT_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            
            # Declare the same queue we defined in docker-compose
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            
            # Bind to the WuzAPI exchange so we receive events
            # WuzAPI broadcasts to an exchange named 'wuzapi'
            channel.exchange_declare(exchange='wuzapi', exchange_type='fanout', durable=True)
            channel.queue_bind(exchange='wuzapi', queue=QUEUE_NAME)
            
            print(" [*] Connected! Waiting for messages...")
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=True)
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError:
            print(" [!] RabbitMQ not ready yet, retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f" [!] Critical Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
