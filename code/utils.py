from datetime import datetime
import base64
import hmac
import hashlib
import blackboxprotobuf
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def log(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {msg}")

def extractText(message_content):
    """Extracts the text from any type of message."""
    text = message_secret = None

    if "messageContextInfo" in message_content:
       message_secret = message_content["messageContextInfo"].get("messageSecret", "")

    if "conversation" in message_content:
        text = message_content["conversation"]
    elif "extendedTextMessage" in message_content:
        text = message_content["extendedTextMessage"].get("text", "")
    elif "imageMessage" in message_content:
        text = message_content["imageMessage"].get("caption", "")
    elif "videoMessage" in message_content:
        text = message_content["videoMessage"].get("caption", "")
    elif "pollCreationMessageV3" in message_content:
        text = message_content["pollCreationMessageV3"].get("name", "")

    return text, message_secret


def extractTextEdited(message_content, sender):
    """Extracts the text from edited and deleted messages."""
    from counting_check import getMessageSecret
    text = target_id = targetMsgSecret = None
    if "protocolMessage" in message_content:  ##case edit not encrypted
        if "editedMessage" in message_content["protocolMessage"]:
            edited_msg = message_content["protocolMessage"]["editedMessage"]
            text, _ = extractText(edited_msg)
        else:   ## case deleted message
            text = "deleted"
        target_id = message_content["protocolMessage"]["key"].get("ID", "")
        targetMsgSecret = getMessageSecret(target_id)
            
    elif "secretEncryptedMessage" in message_content: ## case edit encrypted
        target_id = message_content["secretEncryptedMessage"]["targetMessageKey"].get("ID", "")
        targetMsgSecret = getMessageSecret(target_id)
        if not targetMsgSecret:
            log(f" [!] Missing message secret for target ID {target_id}. Cannot decrypt edit.")
            return None, target_id, None
            
        encPayload = message_content["secretEncryptedMessage"].get("encPayload","")
        encIV = message_content["secretEncryptedMessage"].get("encIV","")
        text = decryptEditedMessage(targetMsgSecret, encPayload, encIV, target_id, sender)
        
    return text, target_id, targetMsgSecret



def decryptEditedMessage(message_secret_b64, enc_payload_b64, enc_iv_b64, message_id, sender_jid):
    try:
        # Decode base64 to raw bytes
        secret = base64.b64decode(message_secret_b64)
        enc_payload = base64.b64decode(enc_payload_b64)
        enc_iv = base64.b64decode(enc_iv_b64)

        # 2. Recreate the specific WhatsApp signature for edits
        # Format: [ID] + [Sender] + [Sender] + "Message Edit" + [0x01]
        sign = (
            message_id.encode('utf-8') +
            sender_jid.encode('utf-8') +
            sender_jid.encode('utf-8') +
            b"Message Edit" +
            bytes([1])
        )

        # 3. Derive the decryption key using double HMAC-SHA256
        key_32_zeros = b'\x00' * 32
        
        # Step A: HMAC(32_zeros, secret)
        step1_key = hmac.new(key=key_32_zeros, msg=secret, digestmod=hashlib.sha256).digest()
        
        # Step B: HMAC(step1_key, signature)
        final_decryption_key = hmac.new(key=step1_key, msg=sign, digestmod=hashlib.sha256).digest()

        # 4. Decrypt using AES-GCM
        aesgcm = AESGCM(final_decryption_key)
        decrypted_bytes = aesgcm.decrypt(nonce=enc_iv, data=enc_payload, associated_data=None)
                
        # The result is a Protobuf object.
        try:
            message_dict, _ = blackboxprotobuf.decode_message(decrypted_bytes)
            edited_msg = message_dict.get('12', {}).get('14', {})
            ##example - {'12': {'14': {'3': {'3': b'Edited message',....
            def get_first_string(obj):
                """text will be in the first string in the object"""
                if isinstance(obj, bytes):
                    try:
                        text = obj.decode('utf-8')
                        if text.strip():
                            return text
                    except UnicodeDecodeError:
                        pass
                elif isinstance(obj, dict):
                    for v in obj.values():
                        res = get_first_string(v)
                        if res: return res
                elif isinstance(obj, list):
                    for v in obj:
                        res = get_first_string(v)
                        if res: return res
                return None

            return get_first_string(edited_msg)
        except Exception as e:
            log(f"Failed to strip protobuf: {e}")

    except Exception as e:
        log(f"❌ Decryption failed: {e}")