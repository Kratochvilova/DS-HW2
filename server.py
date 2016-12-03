#!/usr/bin/python
"""
Created on Thu Dec  1 15:41:13 2016

@author: pavla kratochvilova
"""
# Setup Python logging ------------------ -------------------------------------
import logging
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
LOG = logging.getLogger()
# Imports----------------------------------------------------------------------
import common
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

def publish_advertisements(channel, message):
    while True:
        channel.basic_publish(exchange='direct_logs', 
                              routing_key='server_advertisements', 
                              body=message)
        sleep(5)

def end_server(channel, message):
    channel.basic_publish(exchange='direct_logs', 
                          routing_key='server_advertisements', 
                          body=message)

# Main function ---------------------------------------------------------------
if __name__ == '__main__':
    # Parsing arguments
    parser = ArgumentParser()
    parser.add_argument('-H','--host', \
                        help='Addres of the RabitMQ server, '\
                        'defaults to %s' % common.DEFAULT_SERVER_INET_ADDR, \
                        default=common.DEFAULT_SERVER_INET_ADDR)
    parser.add_argument('-p','--port', \
                        help='Port of the RabitMQ server, '\
                        'defaults to %d' % common.DEFAULT_SERVER_PORT, \
                        default=common.DEFAULT_SERVER_PORT)
    args = parser.parse_args()

    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host='localhost'))
    channel = connection.channel()
    
    channel.exchange_declare(exchange='direct_logs', type='direct')
    channel.queue_declare(queue='server_advertisements')
    
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key='server_advertisements')
    
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key='server_advertisements')
                   
    t = threading.Thread(target=publish_advertisements, 
                         args=(channel, 'server 1'))
    t.setDaemon(True)
    t.start()
    
    try:
        sleep(100)
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating server ...')
    
    end_server(channel, 'end server 1')
