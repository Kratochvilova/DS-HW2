# -*- coding: utf-8 -*-
"""
Created on Tue Dec  7 16:27:21 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
from . import listen, closing_windows
import threading
import pika
import Tkinter
import tkMessageBox
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger()
# Classes ---------------------------------------------------------------------
class LobbyWindow(object):
    '''Window for displaying game sessions, and creating new sessions.
    '''
    def __init__(self, channel, server_advertisements, client_queue,
                 events, parent):
        '''Set next window, gui elements, communication channel, and queues.
        Show the lobby window.
        @param channel: pika connection channel
        @param server_advertisements: queue for server advertisements
        @param client_queue: queue for messages to client
        @param events: Queue of events for window control
        '''
        # Next window
        self.server_window = None
        self.game_window = None
        
        # Queue of events for window control
        self.events = events
        
        # GUI
        self.root = Tkinter.Toplevel(master=parent.root)
        self.root.title('Battleships')
        self.root.protocol("WM_DELETE_WINDOW", lambda: closing_windows(events))
        
        frame = Tkinter.Frame(self.root)
        frame.pack()
        
        self.create_label = Tkinter.Label(frame, text="Create new game:")
        self.create_label.pack()
        self.gamename_entry = Tkinter.Entry(frame)
        self.gamename_entry.pack()
        self.width_entry = Tkinter.Scale(frame, from_=0, to=20, 
                                         orient=Tkinter.HORIZONTAL)
        self.width_entry.pack()
        self.height_entry = Tkinter.Scale(frame, from_=0, to=20, 
                                          orient=Tkinter.HORIZONTAL)
        self.height_entry.pack()
        
        self.button_create = Tkinter.Button(
            frame, text="Create", command=self.create_game)
        self.button_create.pack()
        
        self.listbox_label = Tkinter.Label(frame, text="List of games:")
        self.listbox_label.pack()
        self.listbox = Tkinter.Listbox(frame, width=40, height=20)
        self.listbox.pack()
        
        self.button_join = Tkinter.Button(
            frame, text="Join", command=self.join_game)
        self.button_join.pack()
        
        # Communication
        self.channel = channel
        self.server_advertisements = server_advertisements
        self.client_queue = client_queue
        
        self.root.withdraw()
    
    def show(self):
        '''Show the lobby window.
        '''
        self.root.deiconify()
        self.on_show()

    def on_show(self):
        '''Bind queues, set consuming and listen.
        '''
        # Clear listbox
        self.listbox.delete(0, Tkinter.END)
        # Binding queues TODO: bind correct stuff
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
        
        # Get list of games
        self.get_games_list()

    def hide(self):
        '''Hide the server window and put event for the lobby sindow.
        '''
        self.root.withdraw()
        self.on_hide()
        self.events.put(('lobby', threading.current_thread()))

    def on_hide(self):
        '''Unbind queues, stop consuming.
        '''
        # Unbinding queues TODO: unbind correct stuff
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.server_advertisements,
                                  routing_key='server_stop')
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.client_queue,
                                  routing_key=self.client_queue)
        # Stop consuming
        self.channel.stop_consuming()
    
    def add_session(self, name):
        '''Add game session name into the listbox.
        @param name: game session name
        '''
        if name in self.listbox.get(0, Tkinter.END):
            return
        self.listbox.insert(Tkinter.END, name)
    
    def remove_session(self, name):
        '''Remove game session name from the listbox.
        @param name: game session name
        '''
        if name not in self.listbox.get(0, Tkinter.END):
            LOG.debug('Ignoring game session %s removal, not in set.' % name)
            return
        listbox_index = self.listbox.get(0, Tkinter.END).index(name)
        self.listbox.delete(listbox_index)
    
    def update(self, ch, method, properties, body):
        '''Update listbox of game session names.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        # TODO: game session update
        pass

    def get_games_list(self):
        # TODO: get list of games from server
        pass
    
    def create_game(self):
        gamename = self.gamename_entry.get()
        if gamename.strip() == '':
            tkMessageBox.showinfo('Name', 'Please enter name of the game')
            return
        width = self.width_entry.get()
        height = self.height_entry.get()
        # TODO: send request
    
    def join_game(self):
        if self.listbox.curselection() == ():
            return
        session_name = self.listbox.get(self.listbox.curselection())
        # TODO: send request

    def on_response(self, ch, method, properties, body):
        '''React on server response.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        # TODO
        pass