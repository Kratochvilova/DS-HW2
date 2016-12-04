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
import common
from argparse import ArgumentParser
from time import sleep
import threading
import pika
import Tkinter
# Constants -------------------------------------------------------------------
___NAME = 'Battleship Game Client'
___VER = '0.1.0.0'
___DESC = 'Battleship Game Client'
___BUILT = '2016-11-10'
# Functions -------------------------------------------------------------------
def __info():
    return '%s version %s (%s)' % (___NAME, ___VER, ___BUILT)

# Classes ---------------------------------------------------------------------
class AvailableServers(object):
    def __init__(self):
        self.servers = set()

    def update(self, ch, method, properties, body):
        if method.routing_key == common.SERVER_ADVERT:
            self.servers.add(body)
        if method.routing_key == common.SERVER_STOP:
            try:
                self.servers.remove(body)
            except KeyError:
                LOG.debug('Ignoring server %s removal, not in set.' % body)

# Functions -------------------------------------------------------------------
def listen_advertisements(channel):
    channel.start_consuming()

def update_listbox(updating_listbox, listbox, server_list):
    while updating_listbox[0]:
        listbox.delete(0, Tkinter.END)
        for server in server_list:
            listbox.insert(Tkinter.END, server)
        sleep(3)

# Main method -----------------------------------------------------------------
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
                        help='User nickname.',\
                        required=True)
    args = parser.parse_args()

    # Connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=args.host, port=args.port))
    channel = connection.channel()
    channel.exchange_declare(exchange='direct_logs', type='direct')
    
    # Server advertisements
    channel.queue_declare('server_advertisements')
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key=common.SERVER_ADVERT)
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key=common.SERVER_STOP)
                       
    # GUI - List of servers
    root = Tkinter.Tk()
    root.title('List of servers')
    listbox = Tkinter.Listbox(root)
    listbox.pack()

    available_servers = AvailableServers()
    channel.basic_consume(available_servers.update,
                          queue='server_advertisements',
                          no_ack=True)
    t = threading.Thread(target=listen_advertisements, args=(channel,))
    t.setDaemon(True)
    t.start()
    updating_listbox = [True]
    t = threading.Thread(target=update_listbox, args=(updating_listbox, listbox, available_servers.servers))
    t.setDaemon(True)
    t.start()
    
    try:
        Tkinter.mainloop()
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating server ...')
    
    updating_listbox[0] = False
