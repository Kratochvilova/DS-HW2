#!/usr/bin/python
"""
Created on Thu Dec  1 15:41:34 2016

@author: pavla kratochvilova
"""
# Setup Python logging ------------------ -------------------------------------
import logging
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
LOG = logging.getLogger()
# Imports----------------------------------------------------------------------
from argparse import ArgumentParser
from time import sleep
import threading
import pika
# Constants -------------------------------------------------------------------
___NAME = 'Battleship Game Client'
___VER = '0.1.0.0'
___DESC = 'Battleship Game Client'
___BUILT = '2016-11-10'
# Functions -------------------------------------------------------------------
def __info():
    return '%s version %s (%s)' % (___NAME, ___VER, ___BUILT)

def process_advertisements(ch, method, properties, body):
    print(" [x] %r:%r" % (method.routing_key, body))

def listen_advertisements(channel):
    channel.start_consuming()

# Main method -----------------------------------------------------------------
if __name__ == '__main__':
    # Parsing arguments
    parser = ArgumentParser()
    parser.add_argument('-n','--name', \
                        help='User nickname.',\
                        required=True)
    args = parser.parse_args()

    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))
    channel = connection.channel()
    
    channel.exchange_declare(exchange='direct_logs', type='direct')
    channel.queue_declare('server_advertisements')
    
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key='server_advertisements')

    channel.basic_consume(process_advertisements,
                          queue='server_advertisements',
                          no_ack=True)

    t = threading.Thread(target=listen_advertisements, args=(channel,))
    t.setDaemon(True)
    t.start()
    
    try:
        sleep(100)
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating server ...')
    