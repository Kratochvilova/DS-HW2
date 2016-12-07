import threading

def listen(channel):
    t = threading.Thread(target=channel.start_consuming, 
                         name='Listening on channel')
    t.start()
    return t

def stop_consuming(ch, method, properties, body):
    ch.stop_consuming()
    