# -*- coding: utf-8 -*-
"""
Created on Tue Dec  6 21:29:21 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
from . import listen
import pika
import Tkinter
import tkMessageBox
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger()
# Classes ---------------------------------------------------------------------
class ServerWindow(object):
    def __init__(self, channel, server_advertisements, client_queue, events):
        self.events = events
        self.lobby_window = None
        
        # GUI
        self.root = Tkinter.Tk()
        self.root.title('Battleships')
        
        frame = Tkinter.Frame(self.root)
        frame.pack()
        
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
        
        # Communication
        self.channel = channel
        self.server_advertisements = server_advertisements
        self.client_queue = client_queue
        
        self.on_show()
    
    def show(self):
        self.root.deiconify()
        self.on_show()

    def on_show(self):
        # Binding queues
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.server_advertisements,
                                routing_key='server_advert')
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.server_advertisements,
                                routing_key='server_stop')
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.client_queue,
                                routing_key=self.client_queue)
        self.channel.basic_consume(self.update, 
                                   queue=self.server_advertisements,
                                   no_ack=True)
        self.channel.basic_consume(self.on_response, 
                                   queue=self.client_queue,
                                   no_ack=True)
        self.listening_thread = listen(self.channel)

    def hide(self):
        self.root.withdraw()
        self.on_hide()
        self.events.put('server')

    def on_hide(self):
        # Unbinding queues
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.server_advertisements,
                                  routing_key='server_advert')
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.server_advertisements,
                                  routing_key='server_stop')
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.client_queue,
                                  routing_key=self.client_queue)
        self.channel.stop_consuming()
    
    def add_server(self, name):
        if name in self.listbox.get(0, Tkinter.END):
            return
        self.listbox.insert(Tkinter.END, name)
    
    def remove_server(self, name):
        if name not in self.listbox.get(0, Tkinter.END):
            LOG.debug('Ignoring server %s removal, not in set.' % name)
            return
        listbox_index = self.listbox.get(0, Tkinter.END).index(name)
        self.listbox.delete(listbox_index)
    
    def update(self, ch, method, properties, body):
        if method.routing_key == 'server_advert':
            self.add_server(body)
        if method.routing_key == 'server_stop':
            self.remove_server(body)
       
    def connect_server(self):
        if self.listbox.curselection() == ():
            return
        server_name = self.listbox.get(self.listbox.curselection())
        username = self.username_entry.get()
        if username.strip() == '':
            tkMessageBox.showinfo('Username', 'Please enter username')
            return
        
        # Sending connect request
        message = common.REQ_CONNECT + common.MSG_SEPARATOR + username
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=server_name,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=message)

    def on_response(self, ch, method, properties, body):
        if body == common.RSP_OK:
            self.hide()
        if body == common.RSP_USERNAME_TAKEN:
            tkMessageBox.showinfo('Username', 'The username is already '+\
                                  'taken on this server')
        return
