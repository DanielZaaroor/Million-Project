from wuzapi_client import send_alert
from configs import cursor, conn, ALERT_GROUP_JID
import configs
from utils import log, extractText
import json
import time
import re

# --- Helper Functions ---

def get_CurrData():
    """Fetch the last valid number and sender from the DB."""
    cursor.execute("SELECT number, sender, push_name, msg_id FROM valid_counts ORDER BY timestamp DESC LIMIT 1")
    return cursor.fetchone()


def save_valid_count(number, sender, push_name, msg_id):
    """Inserts the new number into the DB."""
    cursor.execute("""
        INSERT OR REPLACE INTO valid_counts (number, sender, push_name, timestamp, msg_id) 
        VALUES (?, ?, ?, ?, ?)
    """, (number, sender, push_name, time.time(), msg_id))
    conn.commit()


def set_suspended(is_suspended: bool, delete: bool):
    """Updates the single row in the state table."""
    if is_suspended:
        configs.IS_SUSPENDED = True
        val = 1
    else:
        configs.IS_SUSPENDED = False
        val = 0
    cursor.execute("UPDATE bot_state SET is_suspended = ? WHERE id = 1", (val,))
    
    if delete:
        cursor.execute("DELETE FROM pending_messages") # buffer is not needed anymore

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


def checkEditedPending(target_id, PushName, data):        
    cursor.execute("SELECT id FROM pending_messages WHERE msg_id = ?", (target_id,))
    pending_row = cursor.fetchone()
    if pending_row:
        cursor.execute("UPDATE pending_messages SET data = ? WHERE msg_id = ?", (json.dumps(data), target_id))
        conn.commit()
        log(f" [*] Mistake Window. Edited message by {PushName} updated in buffer.")
        return True
    
def checkEditedValidDB(target_id, PushName, found_numbers):
    cursor.execute("SELECT number FROM valid_counts WHERE msg_id = ?", (target_id,))
    valid_row = cursor.fetchone()
    if valid_row:
        old_number = valid_row[0]
        if numberCheck(found_numbers, old_number) < 0:
            send_alert(f"‼️ Panic!! {PushName} edited their message to change the valid number ({old_number})!!", ALERT_GROUP_JID)
        return True



# --- Core Logic ---

def Verdict(valid_number_found, sender, pushname, currData, msg_id):
    """Boolean: Checks if found numbers are valid"""
    
    # RULE: No double messages from same sender
    sender = sender
    PushName = pushname
    last_number, last_sender, last_pushname, last_msg_id = currData

    if sender == last_sender:
        send_alert(f"⚠️ Double Count! {PushName} sent 2 messages in a row.", ALERT_GROUP_JID)
        return False #don't suspend, next number will be correct, admin will delete this one.
    
    if(valid_number_found > 0):
        # SUCCESS
        save_valid_count(valid_number_found, sender, PushName, msg_id)
        log(f" [✓] Valid count: {valid_number_found} by {PushName}")
        return True
    
    # No numbers
    if valid_number_found == -1:
        send_alert(f"⚠️ {PushName} sent a message with NO numbers!, expected {last_number+1}.", ALERT_GROUP_JID, 300)        
    #only wrong number found
    if valid_number_found == -2:
        send_alert(f"⚠️ Wrong Number by {PushName}! Expected {last_number+1}.", ALERT_GROUP_JID, 300)           

    set_suspended(True,False)
    return False

def checkPendingMessage():
    """After Mistake Window - checks all buffered messages."""
    log(" [*] Processing buffered messages...")
    cursor.execute("SELECT id, msg_id, data FROM pending_messages ORDER BY id ASC")
    rows = cursor.fetchall() 
    
    for row in rows:
        row_id = row[0]
        msg_id = row[1]
        data = json.loads(row[2])
        try:
            event = data.get("event", {})
            info = event.get("Info", {})
            message_content = event.get("Message", {})
            sender = info.get("Sender")
            PushName = info.get("PushName")
            
            extracted = extractText(message_content) 
            if len(extracted) == 3:
                text, is_edited, target_id = extracted
            else:
                text, is_edited = extracted
                
            found_numbers = re.findall(r'\d+', text)
            
            currData = get_CurrData()                
            last_number, last_sender, last_pushname, last_msg_id = currData
            valid_number_found = numberCheck(found_numbers, last_number + 1)
            
            # Run Verdict
            if is_edited:
                checkEditedPending(last_msg_id, PushName, data)
                checkEditedValidDB(last_msg_id, PushName, found_numbers)
                
            success = Verdict(valid_number_found, sender, PushName, currData, msg_id)
            
            cursor.execute("DELETE FROM pending_messages WHERE id = ?", (row_id,))
            conn.commit()
            
            if not success:
                log(" [*] Buffered message failed validation. Re-suspending.")
                break

        except Exception as e:
            log(f" [!] Error processing buffered message ID {row_id}: {e}")



def handleNewCount(data):
    """Recieves every new message from the million group"""
    try:
        # Filter: no Stickers
        if data.get("isSticker"):
            send_alert("⚠️ Stickers Shall Not Pass!!!", ALERT_GROUP_JID)
            return True

        event = data.get("event", {})   
        info = event.get("Info", {})
        msg_id = info.get("ID")

        # 1. Extract Text and find numbers in it
        message_content = event.get("Message", {})
        extracted = extractText(message_content)
        if len(extracted) == 3:
            text, is_edited, target_id = extracted
        else:
            text, is_edited = extracted
            
        if text == None: #probably reaction emoji or some shit
            return True

        found_numbers = re.findall(r'\d+', text)

        # 2. Get Curr Data and check for suspended
        currData = get_CurrData()
        sender = info.get("Sender")
        PushName = info.get("PushName")

        if not currData:
            # First run: Use the first number we find as the seed
            if not found_numbers:
                return True
            seed_num = int(found_numbers[0])
            save_valid_count(seed_num, sender, PushName, msg_id)
            log(f" [!] Initialized DB with start number: {seed_num}")
            return True


        last_number, last_sender, last_pushname, last_msg_id = currData

        valid_number_found = numberCheck(found_numbers, last_number + 1)

        # check if group suspended - Mistake Window
        if configs.IS_SUSPENDED:
            if valid_number_found > 0:
                send_alert(f"✅ Mistake fixed by {PushName}", ALERT_GROUP_JID)
                if is_edited: #check all in buffer
                    save_valid_count(valid_number_found, sender, PushName, last_msg_id)
                    set_suspended(False, False)
                    checkPendingMessage()
                else:
                    save_valid_count(valid_number_found, sender, PushName, msg_id)
                    set_suspended(False,True) #also delete buffer
            else:
                if is_edited:
                    checkEditedPending(last_msg_id, PushName, data)
                    checkEditedValidDB(last_msg_id, PushName, found_numbers)

                else:
                    cursor.execute("INSERT INTO pending_messages (msg_id, data) VALUES (?, ?)", (msg_id, json.dumps(data)))
                    conn.commit()
                    log(f" [*] Mistake Window. Message by {PushName} buffered.")
            return

        if is_edited:
            checkEditedValidDB(last_msg_id,PushName,found_numbers)
        Verdict(valid_number_found, sender, PushName, currData, msg_id)
        return True
    


    except Exception as e:
        log(f" [!] Error processing count: {e}")
        return False