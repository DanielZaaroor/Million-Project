from multiprocessing.util import info

import pika  #installed in dockerfile
import json
import time
from configs import init_database, RABBIT_URL, MILLION_GROUP_JID, ADMIN_GROUP_JID
from utils import log
from counting_check import handleNewCount
from admin_check import adminActions

# --- Configuration --- #
QUEUE_NAME = "whatsapp_events"

def callback(ch, method, properties, body):
    """Handles all non-ack events in the queue from wuzapi"""
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

        # 2. Route by group / chat
        event = data.get("event", {})   
        info = event.get("Info", {})
        msg_chat = info.get("Chat")

        # Filter out reaction icons
        if info.get("Type") == "reaction":
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        res = True
        if msg_chat == MILLION_GROUP_JID:
            res = handleNewCount(data)
        elif msg_chat == ADMIN_GROUP_JID:
            res = adminActions(data)
        
        if res == False:
            log(f" [!] Message on group {msg_chat} failed to proccess")
        
        ch.basic_ack(delivery_tag=method.delivery_tag) #ack the message anyway
        return 

    except Exception as e:
        log(f" [!] Error processing message: {e}")

def main():
    init_database()
    log(f" [*] Logic Engine Starting... Connecting to {RABBIT_URL}")
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
            
            log(" [*] Connected! Waiting for messages...")
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError:
            log(" [!] RabbitMQ not ready yet, retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            log(f" [!] Critical Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
