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
    def __init__(self, channel, game_advertisements, client_queue,
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
        
        self.server_name = None 
        self.client_name = None
        
        # Queue of events for window control
        self.events = events
        
        # GUI
        self.root = Tkinter.Toplevel(master=parent.root)
        self.root.title('Battleships')
        self.root.protocol("WM_DELETE_WINDOW", 
                           lambda: closing_windows(events, [self.server_name, 
                                                            self.client_name]))
        
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
        
        self.listbox_label = Tkinter.Label(frame, text="List of opened games:")
        self.listbox_label.pack()
        self.listbox_open = Tkinter.Listbox(frame, width=40, height=20)
        self.listbox_open.pack()
        
        self.button_join = Tkinter.Button(
            frame, text="Join", command=self.join_game)
        self.button_join.pack()
        
        self.listbox_label = Tkinter.Label(frame, text="List of closed games:")
        self.listbox_label.pack()
        self.listbox_close = Tkinter.Listbox(frame, width=40, height=20)
        self.listbox_close.pack()
        
        self.button_join = Tkinter.Button(
            frame, text="Spectate", command=self.join_game) # TODO: command for spectating
        self.button_join.pack()
        
        # Communication
        self.channel = channel
        self.game_advertisements = game_advertisements
        self.client_queue = client_queue
        
        self.root.withdraw()
    
    def show(self, arguments):
        '''Show the lobby window.
        @param arguments: arguments passed from previous window: [server_name]
        '''
        self.root.deiconify()
        self.server_name = arguments[0]
        self.client_name = arguments[1]
        self.on_show()

    def on_show(self):
        '''Bind queues, set consuming and listen.
        '''
        # Clear listbox
        self.listbox_open.delete(0, Tkinter.END)
        self.listbox_close.delete(0, Tkinter.END)
        # Binding queues
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_advertisements,
                                routing_key='game_open')
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_advertisements,
                                routing_key='game_close')
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_advertisements,
                                routing_key='game_end')
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.client_queue,
                                routing_key=self.client_queue)
        # Set consuming
        self.channel.basic_consume(self.update,
                                   queue=self.game_advertisements,
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
        self.events.put(('lobby', threading.current_thread(), None))

    def on_hide(self):
        '''Unbind queues, stop consuming.
        '''
        # Unbinding queues TODO: unbind correct stuff
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_advertisements,
                                  routing_key='game_open')
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_advertisements,
                                  routing_key='game_close')
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_advertisements,
                                  routing_key='game_end')
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.client_queue,
                                  routing_key=self.client_queue)
        # Stop consuming
        self.channel.stop_consuming()
    
    def add_game(self, name, state):
        '''Add game session name into the listbox.
        @param name: game session name
        '''
        if state == 'open':
            if name in self.listbox_open.get(0, Tkinter.END):
                return
            else:
                self.listbox_open.insert(Tkinter.END, name)
        if state == 'close':
            if name in self.listbox_close.get(0, Tkinter.END):
                return
            else:
                self.listbox_close.insert(Tkinter.END, name)
    
    def remove_game(self, name, state):
        '''Remove game session name from the listbox.
        @param name: game session name
        '''
        if state == 'open':
            if name not in self.listbox_open.get(0, Tkinter.END):
                LOG.debug('Ignoring game session %s removal.' % name)
                return
            else:
                index = self.listbox_open.get(0, Tkinter.END).index(name)
                self.listbox_open.delete(index)
        if state == 'close':
            if name not in self.listbox_close.get(0, Tkinter.END):
                LOG.debug('Ignoring game session %s removal.' % name)
                return
            else:
                index = self.listbox_close.get(0, Tkinter.END).index(name)
                self.listbox_close.delete(index)
    
    def update(self, ch, method, properties, body):
        '''Update listbox of game session names.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        if method.routing_key == 'game_open':
            self.add_game(body, 'open')
        if method.routing_key == 'game_close':
            self.remove_game(body, 'open')
            self.add_game(body, 'close')
        if method.routing_key == 'game_end':
            self.remove_game(body, 'close')

    def get_games_list(self):
        # Sending connect request
        msg = common.REQ_GET_LIST_OPENED
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name + '.games',
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
        msg = common.REQ_GET_LIST_CLOSED
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name + '.games',
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
        LOG.debug('Sent message to server %s: %s' % (self.server_name, msg))
    
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
        session_name = self.listbox_open.get(self.listbox.curselection())
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