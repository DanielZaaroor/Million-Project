import os
import json
import re
import sqlite3
import pika
import requests
import time
import threading

# --- Configuration ---
# from the docker-compose environment variables
RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
QUEUE_NAME = "whatsapp_events"
LOG_FILE = "message_log.json"
WUZAPI_HOST = os.getenv("WUZAPI_HOST")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
TARGET_GROUP_JID = os.getenv("TARGET_GROUP_JID") #"972585011102-1496246022@g.us"
ALERT_GROUP_JID = os.getenv("ALERT_GROUP_JID")

# --- Database Setup ---
DB_PATH = "/app/data/groupstate.db" 
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

IS_SUSPENDED = False

def init_database():
    """Create the table if it's the first time running"""
    global IS_SUSPENDED
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS state (
            group_jid TEXT PRIMARY KEY,
            last_number INTEGER,
            last_sender TEXT,
            is_suspended INTEGER DEFAULT 0,
            suspended_at REAL       
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_json TEXT
        )
    """)
    conn.commit()

    cursor.execute("SELECT group_jid, is_suspended FROM state WHERE group_jid = ?", (TARGET_GROUP_JID))
    row = cursor.fetchone()
    IS_SUSPENDED = bool(row[0])
    print(" [*] Database is ready and memory state loaded")

# --- Helper Functions ---

def get_CurrData(group_jid):
    """Fetch the last valid number and sender from the DB."""
    cursor.execute("SELECT last_number, last_sender FROM state WHERE group_jid=?", (group_jid,))
    return cursor.fetchone()

def update_state(number, sender, toSuspend=2):
    """Save the new valid number to the DB / suspend group in DB."""
    global IS_SUSPENDED

    match toSuspend:
        case 0: #unlock the group in memory and DB.
            IS_SUSPENDED = False
            cursor.execute("UPDATE state SET is_suspended = ? WHERE group_jid = ?", (0, TARGET_GROUP_JID))
        case 1: #Lock the group in memory and DB.
            IS_SUSPENDED = True
            cursor.execute("UPDATE state SET is_suspended = ? WHERE group_jid = ?", (1, TARGET_GROUP_JID))
        case _: #save valid count in DB
            cursor.execute("INSERT OR REPLACE INTO state (group_jid, last_number, last_sender) VALUES (?,?,?)",
                           (TARGET_GROUP_JID, number, sender))
    conn.commit()

def send_alert(message, delay=0):
    """Sends a warning message to the group via WuzAPI."""
    if(delay > 0):
        threading.Timer(delay, send_alert, args=(message, -1)).start()
        return

    if (delay == -1 and IS_SUSPENDED == False): 
        return   #called back after 5 minutes and group not suspended anymore

    print(f" [!] SENDING ALERT: {message}")
    url = f"{WUZAPI_HOST}/chat/send/text"
    headers = { "Token": ADMIN_TOKEN, "Content-Type": "application/json",}
    payload = { "Phone": ALERT_GROUP_JID, "Body": f"⚠️Counting Compromised: {message}" }
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f" [!!] Failed to send alert: {e}")

def extractText(message_content):
    """Extracts the text from any type of message."""
    text = ""
    is_edited = False
    if "conversation" in message_content:
        text = message_content["conversation"]
    elif "extendedTextMessage" in message_content:
        text = message_content["extendedTextMessage"].get("text", "")
    elif "imageMessage" in message_content:
        text = message_content["imageMessage"].get("caption", "")
    elif "pollCreationMessageV3" in message_content:
        text = message_content["pollCreationMessageV3"].get("name", "")
    elif "editedMessage" in message_content:
        is_edited = True
        text = message_content["editedMessage"].get("conversation", "")
    else :
        text = None
    return text, is_edited      

def numberCheck(num_list, to_find):
    """return [number] if found in list. [-1] for empty list. [-2] numbers don't match"""
    if not num_list:
        return -1
    for num_str in num_list:
        num = int(num_str)
        if num == to_find:
            return num
    return -2
# --- Core Logic ---

def Verdict(valid_number_found, info, currData):
    """Boolean: Checks if found numbers are valid"""
    
    # RULE: No double messages from same sender
    sender = info.get("Sender")
    PushName = info.get("PushName")
    last_number, last_sender = currData

    if sender == last_sender:
        send_alert(f"Double Count! {PushName} sent 2 messages in a row.")
        return False
    
    if(valid_number_found > 0):
        # SUCCESS
        update_state(valid_number_found, sender)
        print(f" [✓] Valid count: {valid_number_found} by {PushName}")
        return True
    
    # No numbers
    if valid_number_found == -1:
        send_alert(f"{PushName} sent a message with NO numbers!, expected {last_number+1}.")        
    #only wrong number found
    if valid_number_found == -2:
        send_alert(f"Wrong Number by {PushName}! Expected {last_number+1}.")           
        
    update_state(last_number+1,sender,1)
    return False

def checkPendingMessage():
    """After Mistake Window - checks all buffered messages."""
    print(" [*] Processing buffered messages...")
    cursor.execute("SELECT id, raw_json FROM pending_messages ORDER BY id ASC")
    rows = cursor.fetchall()
    
    for row in rows:
        msg_id = row[0]
        raw_json = row[1]
        
        try:
            body = json.loads(raw_json)

            event = body.get("event", {})
            info = event.get("Info", {})
            message_content = event.get("Message", {})
            
            text, is_edited = extractText(message_content)
                
            found_numbers = re.findall(r'\d+', text)
            
            currData = get_CurrData(TARGET_GROUP_JID)
                
            last_number, last_sender = currData
            valid_number_found = numberCheck(found_numbers, last_number + 1)
            
            # Run Verdict
            success = Verdict(valid_number_found, info, currData)
            
            if not success:
                print(" [*] Buffered message failed validation. Re-suspending.")
                break

            cursor.execute("DELETE FROM pending_messages WHERE id = ?", (msg_id,))
            conn.commit()
                
        except Exception as e:
            print(f" [!] Error processing buffered message ID {msg_id}: {e}")

def callback(ch, method, properties, body):
    try:
        raw_event = json.loads(body)

        if "jsonData" in raw_event:
            data = json.loads(raw_event["jsonData"])
        else:
            data = raw_event
        
        # 1. Filter: Only Message events
        if data.get("type") != "Message":
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # 2. Filter: Target Group Only
        event = data.get("event", {})   
        info = event.get("Info", {})
        msg_chat = info.get("Chat") 
        if msg_chat != TARGET_GROUP_JID:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        # Filter: no Stickers
        if data.get("isSticker"):
            send_alert(f"Stickers Shall Not Pass!!!")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # 3. Extract Text and find numbers in it
        message_content = event.get("Message", {})
        text, is_edited = extractText(message_content)
        if text == None:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        found_numbers = re.findall(r'\d+', text)

        # 4. Get Curr Data and check for suspended
        currData = get_CurrData(TARGET_GROUP_JID)
        sender = info.get("Sender")

        if not currData:
            # First run: Use the first number we find as the seed
            seed_num = int(found_numbers[0])
            update_state(seed_num, sender)
            print(f" [!] Initialized DB with start number: {seed_num}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        last_number, last_sender = currData
        
        valid_number_found = numberCheck(found_numbers, last_number + 1)
        
        # check if group suspended - Mistake Window
        if IS_SUSPENDED:
            if valid_number_found > 0:
                update_state(last_number,sender,0)
                if is_edited: #check all in buffer
                    checkPendingMessage()
                else:         
                    cursor.execute("DELETE FROM pending_messages") # fixed without edit, we dont need the buffer
                    conn.commit()
            else:
                cursor.execute("INSERT INTO pending_messages (raw_json) VALUES (?)", (body.decode('utf-8'),))
                conn.commit()
                print(f" [*] Mistake Winddow. Message buffered - {text}.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        
        Verdict(valid_number_found, info , currData)

        ch.basic_ack(delivery_tag=method.delivery_tag) #last acknowledge

    except Exception as e:
        print(f" [!] Error processing message: {e}")

# --- Startup Boilerplate ---
def main():
    init_database()
    print(f" [*] Logic Engine Starting... Connecting to {RABBIT_URL}")
    while True:
        try:
            params = pika.URLParameters(RABBIT_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            
            # Declare the queue defined in docker-compose
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            
            # Bind to the WuzAPI exchange so we receive events
            channel.exchange_declare(exchange='wuzapi', exchange_type='fanout', durable=True)
            channel.queue_bind(exchange='wuzapi', queue=QUEUE_NAME)
            
            print(" [*] Connected! Waiting for messages...")
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError:
            print(" [!] RabbitMQ not ready yet, retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f" [!] Critical Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
