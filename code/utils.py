from datetime import datetime

def log(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")

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
    elif "protocolMessage" in message_content:
        if "editedMessage" in message_content["protocolMessage"]:
            is_edited = True
            text = message_content["protocolMessage"]["editedMessage"].get("conversation", "")
    else :
        text = None
    return text, is_edited