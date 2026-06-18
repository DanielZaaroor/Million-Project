from wuzapi_client import send_alert
from configs import cursor, conn, ALERT_GROUP_JID
import configs
from utils import log, extractText, extractTextEdited
import json
import time
import re

ALERT_DELAY = 60

# --- Helper Functions ---

def get_CurrData():
    """Fetch the last valid number and sender from the DB."""
    cursor.execute("SELECT number, sender, push_name, msg_id FROM valid_counts ORDER BY timestamp DESC LIMIT 1")
    return cursor.fetchone()

def getMessageSecret(msg_id):
    """Fetch the secret of the message with the following ID"""
    cursor.execute("SELECT msg_secret FROM valid_counts WHERE msg_id = ? LIMIT 1", (msg_id,))
    row = cursor.fetchone()
    if row and row[0]:
        return row[0]
        
    # Check pending messages buffer if the original message was a "wrong number" mistake
    cursor.execute("SELECT data FROM pending_messages WHERE msg_id = ? LIMIT 1", (msg_id,))
    p_row = cursor.fetchone()
    if p_row:
        try:
            p_data = json.loads(p_row[0])
            message_content = p_data.get("event", {}).get("Message", {})
            _, secret = extractText(message_content)
            return secret
        except Exception as e:
            log(f" [!] Error parsing buffer for secret: {e}")
            
    return None


def save_valid_count(number, sender, push_name, msg_id, msg_secret=None):
    """Inserts the new number into the DB."""
    cursor.execute("""
        INSERT OR REPLACE INTO valid_counts (number, sender, push_name, timestamp, msg_id, msg_secret) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (number, sender, push_name, time.time(), msg_id, msg_secret))
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
    cursor.execute("SELECT id, data FROM pending_messages WHERE msg_id = ?", (target_id,))
    pending_row = cursor.fetchone()
    if pending_row:
        # --- Preserve original message secret for future decryption ---
        try:
            old_data = json.loads(pending_row[1])
            old_secret = old_data.get("event", {}).get("Message", {}).get("messageContextInfo", {}).get("messageSecret")
            if old_secret:
                if "messageContextInfo" not in data["event"]["Message"]:
                    data["event"]["Message"]["messageContextInfo"] = {}
                data["event"]["Message"]["messageContextInfo"]["messageSecret"] = old_secret
        except Exception as e:
            log(f" [!] Failed to preserve secret in buffer: {e}")
        # ------------------------------------------------------------
        
        cursor.execute("UPDATE pending_messages SET data = ? WHERE msg_id = ?", (json.dumps(data), target_id))
        conn.commit()
        log(f" [*] Mistake Window. Edited message by {PushName} updated in buffer.")
        return
    
def checkEditedValidDB(target_id, PushName, found_numbers):
    cursor.execute("SELECT number FROM valid_counts WHERE msg_id = ?", (target_id,))
    valid_row = cursor.fetchone()
    if valid_row:
        old_number = valid_row[0]
        if numberCheck(found_numbers, old_number) < 0:
            # log(f" [!!] Sabotage, {PushName} edited away the valid number ({old_number})!!")
            send_alert(f"❗ Sabotage, {PushName} edited the valid number - [{old_number}]", ALERT_GROUP_JID)
    return

def checkPendingMessage():
    """After Mistake Window - checks all buffered messages."""
    log(" [*] Processing buffered messages...")
    cursor.execute("SELECT id, msg_id, data FROM pending_messages ORDER BY id ASC")
    rows = cursor.fetchall() 
    
    for row in rows:
        row_id = row[0]
        data = json.loads(row[2])
        
        cursor.execute("DELETE FROM pending_messages WHERE id = ?", (row_id,))
        conn.commit()
        
        handleNewCount(data)
        
        if configs.IS_SUSPENDED:
            log(" [*] Buffered message failed validation. Re-suspending.")
            break

# --- Core Logic ---

def Verdict(valid_number_found, sender, PushName, currData, msg_id, msg_secret, data):
    """Boolean: Checks if found numbers are valid"""
    
    # RULE: No double messages from same sender
    last_number, last_sender, _, _ = currData
    if sender == last_sender:
        send_alert(f"⚠️ Double Count! {PushName} sent 2 messages in a row.", ALERT_GROUP_JID)
        return False #don't suspend, next number will be correct, admin will delete this one.
    
    if(valid_number_found > 0):
        # SUCCESS
        save_valid_count(valid_number_found, sender, PushName, msg_id, msg_secret)
        log(f" [✓] Valid count: {valid_number_found} by {PushName}")
        return True
    
    # No numbers
    if valid_number_found == -1:
        send_alert(f"⚠️ NO numbers! message by {PushName}, expected {last_number+1}.", ALERT_GROUP_JID, ALERT_DELAY)        
    #only wrong number found
    if valid_number_found == -2:
        send_alert(f"⚠️ Wrong Number by {PushName}! Expected {last_number+1}.", ALERT_GROUP_JID, ALERT_DELAY)           

    # Buffer the wrong message. If the user edits it, we will need its msg_secret to decrypt the edit.
    cursor.execute("INSERT INTO pending_messages (msg_id, data) VALUES (?, ?)", (msg_id, json.dumps(data)))

    set_suspended(True,False)
    return False


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
        sender = info.get("Sender")
        PushName = info.get("PushName")

        # 1. Extract Text and find numbers in it
        EditField = str(info.get("Edit", ""))
        match EditField:
            case "1":
                is_edited = True
            case "2" | "3": # message pinned | newlatter
                return True
            case "7" | "8":
                # is_deleted = False # add deleteion checks on next version!!!
                return True 
            case _:
                is_edited = False    

        message_content = event.get("Message", {})

        if(is_edited):
            text, edit_target_id, message_secret = extractTextEdited(message_content, sender)
        else:
            text, message_secret = extractText(message_content)
            
        if text == None: #probably reaction emoji or some shit
            return True

        found_numbers = re.findall(r'\d+', text)

        # 2. Get Curr Data and check for suspended
        currData = get_CurrData()
        if not currData:
            # First run: Use the first number we find as the seed
            if not found_numbers:
                return True
            seed_num = int(found_numbers[0])
            save_valid_count(seed_num, sender, PushName, msg_id, message_secret)
            log(f" [!] Initialized DB with start number: {seed_num}")
            return True

        last_number, last_sender, _, last_msgid = currData
        if msg_id == last_msgid:
            return True #probably an wuzapi duplicate, ignore

        valid_number_found = numberCheck(found_numbers, last_number + 1)

        # check if group suspended - Mistake Window
        if configs.IS_SUSPENDED:
            if valid_number_found > 0:
                if sender == last_sender:
                    send_alert(f"⚠️ Double Count! {PushName} tried to fix {last_number+1}, but sent 2 messages in a row.", ALERT_GROUP_JID)
                    return True   
                send_alert(f"✅ Mistake fixed by {PushName}", ALERT_GROUP_JID)
                if is_edited: #check all in buffer
                    # Remove the original wrong message so it doesn't re-suspend during buffer check
                    cursor.execute("DELETE FROM pending_messages WHERE msg_id = ?", (edit_target_id,))
                    conn.commit()
                    save_valid_count(valid_number_found, sender, PushName, edit_target_id, message_secret)
                    set_suspended(False, False)
                    checkPendingMessage()
                else:
                    save_valid_count(valid_number_found, sender, PushName, msg_id, message_secret)
                    set_suspended(False,True) #also delete buffer
            else:
                if is_edited:
                    checkEditedPending(edit_target_id, PushName, data)
                    checkEditedValidDB(edit_target_id, PushName, found_numbers)

                else:
                    cursor.execute("INSERT INTO pending_messages (msg_id, data) VALUES (?, ?)", (msg_id, json.dumps(data)))
                    conn.commit()
                    log(f" [*] Mistake Window. Message by {PushName} buffered.")
            return

        if is_edited:
            checkEditedValidDB(edit_target_id, PushName, found_numbers)
        else:
            Verdict(valid_number_found, sender, PushName, currData, msg_id, message_secret, data)
        return True
    


    except Exception as e:
        log(f" [!] Error processing count: {e}")
        return False