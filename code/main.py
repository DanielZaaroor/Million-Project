import os
import json
import re
import sqlite3
import pika
import requests
import time

# --- Configuration ---
# from the docker-compose environment variables
RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE_NAME = "whatsapp_events"
LOG_FILE = "message_log.json"
WUZAPI_HOST = os.getenv("WUZAPI_HOST")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
TARGET_GROUP_JID = os.getenv("TARGET_GROUP_JID") #"972585011102-1496246022@g.us"
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
        raw_event = json.loads(body)

        if "jsonData" in raw_event:
            data = json.loads(raw_event["jsonData"])
        else:
            data = raw_event
        
        # 1. Filter: Only Message events
        if data.get("type") != "Message":
            return
        
        # Filter: no Stickers
        if data.get("isSticker"):
            send_alert(f"Stickers Shall Not Pass!!!")
            return 

        # 2. Filter: Target Group Only
        event = data.get("event", {})   
        info = event.get("Info", {})
        msg_chat = info.get("Chat") 
        if msg_chat != TARGET_GROUP_JID:
            return
        
        sender = info.get("Sender")
        PushName = info.get("PushName")

        # RULE: No double messages from same sender
        if sender == last_sender:
            send_alert(f"Double Count! {PushName} sent 2 messages in a row.")
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
        elif "pollCreationMessageV3" in message_content:
            text = message_content["pollCreationMessageV3"].get("name", "")
        else :
            return

        # 4. Find ALL numbers in the message
        found_numbers = re.findall(r'\d+', text)
        
        # RULE: Message must have a number
        if not found_numbers:
            send_alert(f"{PushName} sent a message with NO numbers!")
            return        

        # 5. Logic: Find the valid Number
        currData = get_CurrData(TARGET_GROUP_JID)

        if not currData:
            # First run: Use the first number we find as the seed
            seed_num = int(found_numbers[0])
            update_state(TARGET_GROUP_JID, seed_num, sender)
            print(f" [!] Initialized DB with start number: {seed_num}")
            return

        last_number, last_sender = currData

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
            print(f" [✓] Valid count: {valid_number_found} by {PushName}")
        else:
            # found numbers, but none of them were the correct next number
            found_str = ", ".join(found_numbers)
            send_alert(f"Wrong Number! {PushName} wrote [{found_str}], expected {last_number + 1}.")

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
