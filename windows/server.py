# -*- coding: utf-8 -*-
"""
Created on Tue Dec  6 21:29:21 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
from . import listen, send_message
import threading
import Tkinter
import tkMessageBox
import sys
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger(__name__)
# Classes ---------------------------------------------------------------------
class ServerWindow(object):
    '''Window for displaying active servers, entering username, and connecting
    to servers.
    '''
    def __init__(self, channel, server_advertisements, client_queue, events):
        '''Set next window, gui elements, communication channel, and queues.
        Show the server window.
        @param channel: pika connection channel
        @param server_advertisements: queue for server advertisements
        @param client_queue: queue for messages to client
        @param events: Queue of events for window control
        '''
        # Next window
        self.lobby_window = None
        self.game_window = None
        
        # Queue of events for window control
        self.events = events
        
        # GUI
        self.root = Tkinter.Tk()
        self.root.title('Battleships')
        self.root.protocol("WM_DELETE_WINDOW", sys.exit)
        
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
    
    def show(self, arguments=None):
        '''Show the server window.
        @param arguments: arguments passed from previous window
        '''
        LOG.debug('Showing server window.')
        self.root.deiconify()
        self.on_show()

    def on_show(self):
        '''Bind queues, set consuming and listen.
        '''
        # Clear listbox
        self.listbox.delete(0, Tkinter.END)
        # Binding queues
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.server_advertisements,
                                routing_key=common.KEY_SERVER_ADVERT)
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.server_advertisements,
                                routing_key=common.KEY_SERVER_STOP)
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.client_queue,
                                routing_key=self.client_queue)
        # Set consuming
        self.channel.basic_consume(self.update, 
                                   queue=self.server_advertisements,
                                   no_ack=True)
        self.channel.basic_consume(self.on_response, 
                                   queue=self.client_queue,
                                   no_ack=True)
        # Listening
        self.listening_thread = listen(self.channel, 'server')

    def hide(self):
        '''Hide the server window.
        '''
        LOG.debug('Hiding server window.')
        self.root.withdraw()
        self.on_hide()

    def on_hide(self):
        '''Unbind queues, stop consuming.
        '''
        # Unbinding queues
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.server_advertisements,
                                  routing_key=common.KEY_SERVER_ADVERT)
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.server_advertisements,
                                  routing_key=common.KEY_SERVER_STOP)
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.client_queue,
                                  routing_key=self.client_queue)
        # Stop consuming
        if threading.current_thread() == self.listening_thread:
            self.channel.stop_consuming()
        else:
            LOG.error('ServerWindow.on_hide called from non-listening thread.')
    
    def add_server(self, name):
        '''Add server name into the listbox.
        @param name: server name
        '''
        if name in self.listbox.get(0, Tkinter.END):
            return
        self.listbox.insert(Tkinter.END, name)
    
    def remove_server(self, name):
        '''Remove server name from the listbox.
        @param name: server name
        '''
        if name not in self.listbox.get(0, Tkinter.END):
            LOG.debug('Ignoring server %s removal, not in set.', name)
            return
        listbox_index = self.listbox.get(0, Tkinter.END).index(name)
        self.listbox.delete(listbox_index)
    
    def update(self, ch, method, properties, body):
        '''Update listbox of server names.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        if method.routing_key == common.KEY_SERVER_ADVERT:
            self.add_server(body)
        if method.routing_key == common.KEY_SERVER_STOP:
            self.remove_server(body)
       
    def connect_server(self):
        '''Send connection request to server selected in the listbox.
        '''
        if self.listbox.curselection() == ():
            return
        server_name = self.listbox.get(self.listbox.curselection())
        username = self.username_entry.get()
        if username.strip() == '':
            tkMessageBox.showinfo('Username', 'Please enter username')
            return
        
        # Sending connect request
        send_message(self.channel, [common.REQ_CONNECT, username],
                     [server_name], self.client_queue)

    def on_response(self, ch, method, properties, body):
        '''React on server response about connecting.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Received message: %s', body)
        msg_parts = body.split(common.SEP)
        if msg_parts[0] == common.RSP_CONNECTED:
            # If response ok, hide server window and put event for the lobby
            # window with necessary arguments (server name, client name)
            self.hide()
            self.events.put(('lobby', threading.current_thread(), 
                             [msg_parts[1], msg_parts[2]]))
        if msg_parts[0] == common.RSP_USERNAME_TAKEN:
            tkMessageBox.showinfo('Username', 'The username is already '+\
                                  'taken on this server')
