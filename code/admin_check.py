from utils import extractText, log
from counting_check import save_valid_count, set_suspended, get_CurrData
from wuzapi_client import send_alert
import configs


def adminActions(data):
  """ Handle messages for admin group"""
  event = data.get("event", {})   
  # info = event.get("Info", {})
  message_content = event.get("Message", {})

  extracted = extractText(message_content)
  if len(extracted) == 3:
      text, _, _ = extracted
  else:
      text, _ = extracted
  if text == None:
      return False
  
  if("Insert-" in text):
     return numOverride(text)
  if("Status" in text):
     return statsReport()
  

  return True



def numOverride(text):
    """Initiate number override in the million group"""
    try:
      num = int(text[7:])
      save_valid_count(num, "admin", "admin", "admin_override")
      set_suspended(False,True) #also deletes buffer
      log(f" [✓] Admin Override with number - {num}")
      return True
       
    except ValueError as e:
      log(f" [!] Invalid override number: {e}")
      return False
    
def statsReport():
    """Prints the latest group status"""
    currData = get_CurrData()
    if not currData:
      return send_alert("❔ empthy DB, couldn't find last number.", configs.ADMIN_GROUP_JID)
    
    last_number, _, last_pushname, _ = currData
    if configs.IS_SUSPENDED:
      return send_alert(f"🚫 suspended from: {last_number}, by - {last_pushname}", configs.ADMIN_GROUP_JID)
    return send_alert(f"🆙 last number: {last_number}, by - {last_pushname}", configs.ADMIN_GROUP_JID)