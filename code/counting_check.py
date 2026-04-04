from wuzapi_client import send_alert
from configs import cursor, conn, MILLION_GROUP_JID
import configs
from utils import log, extractText
import json
import time
import re

# --- Helper Functions ---

def get_CurrData():
    """Fetch the last valid number and sender from the DB."""
    cursor.execute("SELECT number, sender FROM valid_counts ORDER BY timestamp DESC LIMIT 1")
    return cursor.fetchone()


def save_valid_count(number, sender, push_name):
    """Inserts the new number into the DB."""
    cursor.execute("""
        INSERT OR REPLACE INTO valid_counts (number, sender, push_name, timestamp) 
        VALUES (?, ?, ?, ?)
    """, (number, sender, push_name, time.time()))
    conn.commit()


def set_suspended(is_suspended: bool):
    """Updates the single row in the state table."""
    if is_suspended:
        configs.IS_SUSPENDED = True
        val = 1
    else:
        configs.IS_SUSPENDED = False
        val = 0

    cursor.execute("UPDATE bot_state SET is_suspended = ? WHERE id = 1", (val,))
    conn.commit()
    

def numberCheck(num_list, to_find):
    """returns: [number] if found in list. [-1] list is empty. [-2] no number match goal"""
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
        return False #don't suspend, next number will be correct, admin will delete this one.
    
    if(valid_number_found > 0):
        # SUCCESS
        save_valid_count(valid_number_found, sender, PushName)
        log(f" [✓] Valid count: {valid_number_found} by {PushName}")
        return True
    
    # No numbers
    if valid_number_found == -1:
        send_alert(f"{PushName} sent a message with NO numbers!, expected {last_number+1}.", 300)        
    #only wrong number found
    if valid_number_found == -2:
        send_alert(f"Wrong Number by {PushName}! Expected {last_number+1}.", 300)           

    set_suspended(True)
    return False

def checkPendingMessage():
    """After Mistake Window - checks all buffered messages."""
    log(" [*] Processing buffered messages...")
    cursor.execute("SELECT id, data FROM pending_messages ORDER BY id ASC")
    rows = cursor.fetchall()
    
    for row in rows:
        msg_id = row[0]
        data = json.loads(row[1])
        try:
            event = data.get("event", {})
            info = event.get("Info", {})
            message_content = event.get("Message", {})
            
            text, is_edited = extractText(message_content) 
            found_numbers = re.findall(r'\d+', text)
            
            currData = get_CurrData()                
            last_number, last_sender = currData
            valid_number_found = numberCheck(found_numbers, last_number + 1)
            
            # Run Verdict
            success = Verdict(valid_number_found, info, currData)
            
            cursor.execute("DELETE FROM pending_messages WHERE id = ?", (msg_id,))
            conn.commit()
            
            if not success:
                log(" [*] Buffered message failed validation. Re-suspending.")
                break

        except Exception as e:
            log(f" [!] Error processing buffered message ID {msg_id}: {e}")



def handleNewCount(data):
    """Recieves every new message from the million group"""

    # Filter: no Stickers
    if data.get("isSticker"):
        send_alert(f"Stickers Shall Not Pass!!!")
        return False
    
    event = data.get("event", {})   
    info = event.get("Info", {})

    # 1. Extract Text and find numbers in it
    message_content = event.get("Message", {})
    text, is_edited = extractText(message_content)
    if text == None:
        return False

    found_numbers = re.findall(r'\d+', text)

    # 2. Get Curr Data and check for suspended
    currData = get_CurrData()
    sender = info.get("Sender")
    PushName = info.get("PushName")


    if not currData:
        # First run: Use the first number we find as the seed
        if not found_numbers:
            return False
        seed_num = int(found_numbers[0])
        save_valid_count(seed_num, sender, PushName)
        log(f" [!] Initialized DB with start number: {seed_num}")
        return True


    last_number, last_sender = currData
    
    valid_number_found = numberCheck(found_numbers, last_number + 1)
    
    # check if group suspended - Mistake Window
    if configs.IS_SUSPENDED:
        if valid_number_found > 0:
            save_valid_count(valid_number_found, sender, PushName)
            set_suspended(False)
            if is_edited: #check all in buffer
                checkPendingMessage()
            else:
                cursor.execute("DELETE FROM pending_messages") # buffer is not needed anymore
                conn.commit()
        else:
            cursor.execute("INSERT INTO pending_messages (data) VALUES (?)", (json.dumps(data),))
            conn.commit()
            log(f" [*] Mistake Winddow. Message buffered - {text}.")
        return
    
    
    Verdict(valid_number_found, info , currData)

    return True