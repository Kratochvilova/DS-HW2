# -*- coding: utf-8 -*-
"""
Created on Tue Dec  7 16:27:21 2016

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
LOG = logging.getLogger(__name__)
# Classes ---------------------------------------------------------------------
class LobbyWindow(object):
    '''Window for displaying game sessions, and creating new sessions.
    '''
    def __init__(self, channel, game_advertisements, client_queue,
                 events, parent):
        '''Set next window, gui elements, communication channel, and queues.
        Hide the lobby window.
        @param channel: pika connection channel
        @param server_advertisements: queue for server advertisements
        @param client_queue: queue for messages to client
        @param events: Queue of events for window control
        '''
        # Next window
        self.server_window = None
        self.game_window = None
        
        # Arguments from server_window
        self.server_name = None 
        self.client_name = None
        
        # Queue of events for window control
        self.events = events
        
        # GUI
        self.root = Tkinter.Toplevel(master=parent.root)
        self.root.title('Battleships')
        self.root.protocol("WM_DELETE_WINDOW", self.disconnect)
        
        frame = Tkinter.Frame(self.root)
        frame.pack()
        
        self.button_disconnect = Tkinter.Button(
            frame, text="Disconnect", command=self.disconnect)
        self.button_disconnect.pack()
        
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
        self.listbox_opened = Tkinter.Listbox(frame, width=40, height=10)
        self.listbox_opened.pack()
        
        self.button_join = Tkinter.Button(
            frame, text="Join", command=self.join_game)
        self.button_join.pack()
        
        self.listbox_label = Tkinter.Label(frame, text="List of running games:")
        self.listbox_label.pack()
        self.listbox_closed = Tkinter.Listbox(frame, width=40, height=10)
        self.listbox_closed.pack()
        
        self.button_join = Tkinter.Button(
            frame, text="Spectate", command=self.spectate_game)
        self.button_join.pack()
        
        # Communication
        self.channel = channel
        self.game_advertisements = game_advertisements
        self.client_queue = client_queue
        
        self.root.withdraw()
    
    def show(self, arguments):
        '''Show the lobby window.
        @param arguments: arguments passed from previous window: 
                          [server_name, client username]
        '''
        LOG.debug('Showing lobby window.')
        self.server_name = arguments[0]
        self.client_name = arguments[1]
        self.on_show()
        self.root.deiconify()

    def on_show(self):
        '''Bind queues, set consuming and listen.
        '''
        # Clear listboxes
        self.listbox_opened.delete(0, Tkinter.END)
        self.listbox_closed.delete(0, Tkinter.END)
        
        # Binding queues
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_advertisements,
                                routing_key=self.server_name + common.SEP +\
                                    common.KEY_GAMES)
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_advertisements,
                                routing_key=self.server_name + common.SEP +\
                                    common.KEY_GAME_OPEN)
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_advertisements,
                                routing_key=self.server_name + common.SEP +\
                                    common.KEY_GAME_CLOSE)
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_advertisements,
                                routing_key=self.server_name + common.SEP +\
                                    common.KEY_GAME_END)
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
        self.listening_thread = listen(self.channel, 'lobby')
        
        # Get list of games
        self.get_games_list()

    def hide(self):
        '''Hide the lobby window.
        '''
        LOG.debug('Hiding lobby window.')
        self.root.withdraw()
        self.on_hide()

    def on_hide(self):
        '''Unbind queues, stop consuming.
        '''
        # Unbinding queues
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_advertisements,
                                  routing_key=self.server_name + common.SEP +\
                                      common.KEY_GAMES)
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_advertisements,
                                  routing_key=self.server_name + common.SEP +\
                                      common.KEY_GAME_OPEN)
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_advertisements,
                                  routing_key=self.server_name + common.SEP +\
                                      common.KEY_GAME_CLOSE)
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_advertisements,
                                  routing_key=self.server_name + common.SEP +\
                                      common.KEY_GAME_END)
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.client_queue,
                                  routing_key=self.client_queue)
        # Stop consuming
        if threading.current_thread() == self.listening_thread:
            self.channel.stop_consuming()
        else:
            LOG.error('LobbyWindow.on_hide called from non-listening thread.')
    
    def disconnect(self):
        '''Disconnect from server.
        '''
        msg = common.REQ_DISCONNECT + common.SEP + self.client_name
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
    
    def add_game(self, name, state):
        '''Add game session name into listbox.
        @param name: game session name
        '''
        if state == 'open':
            if name in self.listbox_opened.get(0, Tkinter.END):
                return
            else:
                self.listbox_opened.insert(Tkinter.END, name)
        if state == 'close':
            if name in self.listbox_closed.get(0, Tkinter.END):
                return
            else:
                self.listbox_closed.insert(Tkinter.END, name)
    
    def remove_game(self, name, state):
        '''Remove game session name from listbox.
        @param name: game session name
        '''
        if state == 'open':
            if name not in self.listbox_opened.get(0, Tkinter.END):
                LOG.debug('Ignoring game session %s removal.', name)
                return
            else:
                index = self.listbox_opened.get(0, Tkinter.END).index(name)
                self.listbox_opened.delete(index)
        if state == 'close':
            if name not in self.listbox_closed.get(0, Tkinter.END):
                LOG.debug('Ignoring game session %s removal.', name)
                return
            else:
                index = self.listbox_closed.get(0, Tkinter.END).index(name)
                self.listbox_closed.delete(index)
    
    def update(self, ch, method, properties, body):
        '''Update listbox of game session names.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        key_parts = method.routing_key.split(common.SEP)
        if key_parts[1] == common.KEY_GAME_OPEN:
            self.add_game(body, 'open')
        if key_parts[1] == common.KEY_GAME_CLOSE:
            self.remove_game(body, 'open')
            self.add_game(body, 'close')
        if key_parts[1] == common.KEY_GAME_END:
            self.remove_game(body, 'close')

    def get_games_list(self):
        '''Send requests to server to get list of all game sessions.
        '''
        # Sending request to get list of opened games
        msg = common.REQ_GET_LIST_OPENED
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name + common.SEP +\
                                       common.KEY_GAMES,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
        LOG.debug('Sent message to server %s: %s', self.server_name, msg)
        
        # Sending request to get list of closed games
        msg = common.REQ_GET_LIST_CLOSED
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name + common.SEP +\
                                       common.KEY_GAMES,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
        LOG.debug('Sent message to server %s: %s', self.server_name, msg)
    
    def create_game(self):
        '''Send game creation request to server.
        '''
        gamename = self.gamename_entry.get()
        if gamename.strip() == '':
            tkMessageBox.showinfo('Name', 'Please enter name of the game')
            return
        width = self.width_entry.get()
        height = self.height_entry.get()
        
        # Sending request to create game
        msg = common.SEP.join([common.REQ_CREATE_GAME, gamename, 
                               self.client_name, str(width), str(height)])
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name + common.SEP +\
                                       common.KEY_GAMES,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
        LOG.debug('Sent message to server %s: %s', self.server_name, msg)
    
    def join_game(self):
        if self.listbox_opened.curselection() == ():
            return
        session_name = self.listbox_opened.get(self.listbox_opened.curselection())
        # TODO: send request

    def spectate_game(self):
        pass
    
    def on_response(self, ch, method, properties, body):
        '''React on server response.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Received message: %s', body)
        msg_parts = body.split(common.SEP)
        
        if msg_parts[0] == common.RSP_DISCONNECTED:
            self.hide()
            self.events.put(('server', None, None))
        
        if msg_parts[0] == common.RSP_LIST_OPENED:
            for game_name in msg_parts[1:]:
                self.add_game(game_name, 'open')
        
        if msg_parts[0] == common.RSP_LIST_CLOSED:
            for game_name in msg_parts[1:]:
                self.add_game(game_name, 'close')
        if msg_parts[0] == common.RSP_USERNAME_TAKEN:
            tkMessageBox.showinfo('Username', 'The username is already '+\
                                  'taken on this server')
        
        # TODO: responses on create, join or spectate requests
