import threading
import requests #installed in dockerfile
import configs
from utils import log

def send_alert(message, dest, delay=0):
    """Sends a warning message to the group via WuzAPI."""
    if(delay > 0):
        threading.Timer(delay, send_alert, args=(message, -1)).start()
        return

    if (delay == -1 and configs.IS_SUSPENDED == False): 
        return   #called back after 5 minutes and group not suspended anymore

    log(f" [!] SENDING ALERT: {message}")
    url = f"{configs.WUZAPI_HOST}/chat/send/text"
    headers = { "Token": configs.ADMIN_TOKEN, "Content-Type": "application/json",}
    payload = { "Phone": dest, "Body": f"{message}" }
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        log(f" [!!] Failed to send alert: {e}")  