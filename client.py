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
import threading
import pika
import Tkinter
import tkMessageBox
# Constants -------------------------------------------------------------------
___NAME = 'Battleship Game Client'
___VER = '0.1.0.0'
___DESC = 'Battleship Game Client'
___BUILT = '2016-11-10'
# Functions -------------------------------------------------------------------
def __info():
    return '%s version %s (%s)' % (___NAME, ___VER, ___BUILT)

# Classes ---------------------------------------------------------------------
class ServerDialog(object):
    def __init__(self, frame):
        self.updating_listbox = True
        
        self.username_label = Tkinter.Label(frame, text="Enter username:")
        self.username_label.pack()
        self.username_entry = Tkinter.Entry(frame)
        self.username_entry.pack()
        
        self.listbox_label = Tkinter.Label(frame, text="List of servers:")
        self.listbox_label.pack()
        self.listbox = Tkinter.Listbox(frame, width=40, height=20)
        self.listbox.pack()
                
        self.button_connect = Tkinter.Button(
            frame, text="Connect", command=self.connect_server)
        self.button_connect.pack()    
    
    def add_server(self, name):
        if not self.updating_listbox:
            return
        if name in self.listbox.get(0, Tkinter.END):
            return
        self.listbox.insert(Tkinter.END, name)
    
    def remove_server(self, name):
        if not self.updating_listbox:
            return
        if name not in self.listbox.get(0, Tkinter.END):
            LOG.debug('Ignoring server %s removal, not in set.' % name)
            return
        listbox_index = self.listbox.get(0, Tkinter.END).index(name)
        self.listbox.delete(listbox_index)
    
    def update(self, ch, method, properties, body):
        if method.routing_key == common.SERVER_ADVERT:
            self.add_server(body)
        if method.routing_key == common.SERVER_STOP:
            self.remove_server(body)
    
    def connect_server(self):
        if self.listbox.curselection() == ():
            return
        server_name = self.listbox.get(self.listbox.curselection())
        username = self.username_entry.get()
        if username.strip() == '':
            tkMessageBox.showinfo('Username', 'Please enter username')
            return
        print('TODO: connecting to server %s as %s' % (server_name, 
                                                       username.strip()))

# Functions -------------------------------------------------------------------
def listen_advertisements(channel):
    channel.start_consuming()

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
    args = parser.parse_args()

    # Connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=args.host, port=args.port))
    channel = connection.channel()
    channel.exchange_declare(exchange='direct_logs', type='direct')
    
    # GUI
    root = Tkinter.Tk()
    root.title('Battleships')
    
    frame = Tkinter.Frame(root)
    frame.pack()
    
    # Server advertisements
    server_dialog = ServerDialog(frame)
    channel.queue_declare('server_advertisements')
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key=common.SERVER_ADVERT)
    channel.queue_bind(exchange='direct_logs',
                       queue='server_advertisements',
                       routing_key=common.SERVER_STOP)
    channel.basic_consume(server_dialog.update,
                          queue='server_advertisements',
                          no_ack=True)
    t_adds = threading.Thread(target=listen_advertisements, args=(channel,))
    t_adds.setDaemon(True)
    t_adds.start()
    
    try:
        Tkinter.mainloop()
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating server ...')
    
    server_dialog.updating_listbox = False
