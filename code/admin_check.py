from utils import extractText, log
from counting_check import save_valid_count, set_suspended

def adminActions(data):
  """ Handle messages for admin group"""
  event = data.get("event", {})   
  # info = event.get("Info", {})
  message_content = event.get("Message", {})

  text, is_edited = extractText(message_content)
  if text == None:
      return False
  
  if("Insert-" in text):
     return numOverride(text)
  

  return True



def numOverride(text):
    """Initiate number override in the million group"""
    try:
      num = int(text[7:])
      save_valid_count(num, "admin","admin")
      set_suspended(False)
      log(f"[✓] Admin Override with number - {num}")
      return True
       
    except ValueError as e:
      log(f"[!] Invalid override number: {e}")
      return False