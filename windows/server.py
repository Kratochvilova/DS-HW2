# -*- coding: utf-8 -*-
"""
Created on Tue Dec  6 21:29:21 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
from . import listen
import threading
import pika
import Tkinter
import tkMessageBox
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger()
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
        
        # Queue of events for window control
        self.events = events
        
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
        '''Show the server window.
        '''
        self.root.deiconify()
        self.on_show()

    def on_show(self):
        '''Bind queues, set consuming and listen.
        '''
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
        # Set consuming
        self.channel.basic_consume(self.update, 
                                   queue=self.server_advertisements,
                                   no_ack=True)
        self.channel.basic_consume(self.on_response, 
                                   queue=self.client_queue,
                                   no_ack=True)
        # Listening
        self.listening_thread = listen(self.channel)

    def hide(self):
        '''Hide the server window and put event for the lobby sindow.
        '''
        self.root.withdraw()
        self.on_hide()
        self.events.put(('lobby', threading.current_thread()))

    def on_hide(self):
        '''Unbind queues, stop consuming.
        '''
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
        # Stop consuming
        self.channel.stop_consuming()
    
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
            LOG.debug('Ignoring server %s removal, not in set.' % name)
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
        if method.routing_key == 'server_advert':
            self.add_server(body)
        if method.routing_key == 'server_stop':
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
        message = common.REQ_CONNECT + common.MSG_SEPARATOR + username
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=server_name,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=message)
        LOG.debug('Sent message to server %s: %s' % (server_name, message))

    def on_response(self, ch, method, properties, body):
        '''React on server response about connecting.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Received message: %s' % body)
        if body == common.RSP_OK:
            # If response ok, hide server window (and lobby window is shown)
            self.hide()
        if body == common.RSP_USERNAME_TAKEN:
            tkMessageBox.showinfo('Username', 'The username is already '+\
                                  'taken on this server')
        return
