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
# Classes ---------------------------------------------------------------------
class Clients():
    def __init__(self, channel):
        self.client_set = set()
    
    def process_client(self, ch, method, properties, body):
        msg_parts = body.split(common.MSG_SEPARATOR, 1)
        print msg_parts
        print self.client_set
        if msg_parts[0] == common.REQ_CONNECT:
            if msg_parts[1] in self.client_set:
                response = common.RSP_USERNAME_TAKEN
            else:
                self.client_set.add(msg_parts[1])
                response = common.RSP_OK
        elif msg_parts[0] == common.REQ_DISCONNECT:
            try:
                self.client_set.remove(msg_parts[1])
                response = common.RSP_OK
            except KeyError:
                response = common.RSP_CLIENT_NOT_CONNECTED
        else:
            response = common.RSP_INVALID_REQUEST
        
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
    
# Functions -------------------------------------------------------------------
def __info():
    return '%s version %s (%s)' % (___NAME, ___VER, ___BUILT)

def publish_advertisements(channel, message):
    while True:
        channel.basic_publish(exchange='direct_logs', 
                              routing_key='server_advert', 
                              body=message)
        sleep(5)

def stop_server(channel, message):
    channel.basic_publish(exchange='direct_logs', 
                          routing_key='server_stop', 
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
    parser.add_argument('-n','--name', \
                        help='Server name.',\
                        required=True)
    args = parser.parse_args()

    # Connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=args.host, port=args.port))
    channel = connection.channel()
    channel.exchange_declare(exchange='direct_logs', type='direct')
    
    # Server advertisements
    channel.queue_declare(queue='server_advertisements')
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key='server_advert')
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key='server_stop')
    
    t = threading.Thread(target=publish_advertisements,
                         args=(channel, args.name))
    t.setDaemon(True)
    t.start()
    
    # Client connections
    clients = Clients(channel)
    channel.queue_declare(queue='servers')
    channel.queue_bind(exchange='direct_logs',
                       queue='servers',
                       routing_key=args.name)
    channel.basic_consume(clients.process_client, queue='servers', no_ack=True)
    
    try:
        while True:
            channel.start_consuming()
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating server ...')
    
    stop_server(channel, args.name)
