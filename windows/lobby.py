# -*- coding: utf-8 -*-
"""
Created on Tue Dec  7 16:27:21 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import clientlib
import common
from common import send_message
from . import listen
import threading
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
        self.width_entry = Tkinter.Scale(frame, from_=1, to=20, 
                                         orient=Tkinter.HORIZONTAL)
        self.width_entry.pack()
        self.height_entry = Tkinter.Scale(frame, from_=1, to=20, 
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
        
        self.listbox_label = Tkinter.Label(frame,text="List of running games:")
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
                                routing_key=common.make_key_games(
                                      self.server_name))
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_advertisements,
                                routing_key=common.make_key_game_advert(
                                      self.server_name))
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
                                  routing_key=common.make_key_games(
                                      self.server_name))
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_advertisements,
                                  routing_key=common.make_key_game_advert(
                                      self.server_name))
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
        msg = clientlib.make_req_disconnect(self.client_name)
        routing_key = common.make_key_server(self.server_name)
        send_message(self.channel, msg, routing_key, self.client_queue)
    
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
        msg_parts = body.split(common.SEP)
        if msg_parts[0] == common.E_GAME_OPEN:
            self.add_game(msg_parts[1], 'open')
        if msg_parts[0] == common.E_GAME_CLOSE:
            self.remove_game(msg_parts[1], 'open')
            self.add_game(msg_parts[1], 'close')
        if msg_parts[0] == common.E_GAME_END:
            self.remove_game(msg_parts[1], 'open')
            self.remove_game(msg_parts[1], 'close')

    def get_games_list(self):
        '''Send requests to server to get list of all game sessions.
        '''
        routing_key = common.make_key_games(self.server_name)
        # Sending request to get list of opened games
        msg = clientlib.make_req_list_opened()
        send_message(self.channel, msg, routing_key, self.client_queue)
        # Sending request to get list of closed games
        msg = clientlib.make_req_list_closed()
        send_message(self.channel, msg, routing_key, self.client_queue)
    
    def create_game(self):
        '''Send game creation request to server.
        '''
        game_name = self.gamename_entry.get()
        if game_name.strip() == '':
            tkMessageBox.showinfo('Name', 'Please enter name of the game')
            return
        width = self.width_entry.get()
        height = self.height_entry.get()
        
        # Sending request to create game
        msg = clientlib.make_req_create_game(game_name, self.client_name,
                                                 width, height)
        routing_key = common.make_key_games(self.server_name)
        send_message(self.channel, msg, routing_key, self.client_queue)
    
    def join_game(self):
        '''Send join game request to server.
        '''
        if self.listbox_opened.curselection() == ():
            return
        game_name = self.listbox_opened.get(self.listbox_opened.curselection())
        
        # Sending request to join game
        msg = clientlib.make_req_join_game(game_name, self.client_name)
        routing_key = common.make_key_games(self.server_name)
        send_message(self.channel, msg, routing_key, self.client_queue)

    def spectate_game(self):
        '''Send spectate game request to server.
        '''
        if self.listbox_closed.curselection() == ():
            return
        game_name = self.listbox_closed.get(self.listbox_closed.curselection())
        
        # Sending request to spectate game
        msg = clientlib.make_req_spectate_game(game_name, self.client_name)
        routing_key = common.make_key_games(self.server_name)
        send_message(self.channel, msg, routing_key, self.client_queue)
    
    def on_response(self, ch, method, properties, body):
        '''React on server response.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Received message: %s', body)
        msg_parts = body.split(common.SEP)
        
        if msg_parts[0] == common.RSP_DISCONNECTED or\
            msg_parts[0] == common.RSP_NAME_DOESNT_EXIST:
            self.hide()
            self.events.put(('server', None, None))
        
        if msg_parts[0] == common.RSP_LIST_OPENED:
            for game_name in msg_parts[1:]:
                if game_name.strip() != '':
                    self.add_game(game_name, 'open')
        
        if msg_parts[0] == common.RSP_LIST_CLOSED:
            for game_name in msg_parts[1:]:
                if game_name.strip() != '':
                    self.add_game(game_name, 'close')
        if msg_parts[0] == common.RSP_USERNAME_TAKEN:
            tkMessageBox.showinfo('Username', 'The username is already '+\
                                  'taken on this server')
        
        if msg_parts[0] == common.RSP_GAME_ENTERED:
            # If game entered, hide lobby window and put event for the game
            # window with necessary arguments (server name, client name, game 
            # name, is_owner, spectator, spectator_queue)
            self.hide()
            self.events.put(('game', threading.current_thread(),
                             [self.server_name, self.client_name, msg_parts[1],
                              int(msg_parts[2]), False, '']))

        if msg_parts[0] == common.RSP_GAME_SPECTATE:
            # If game entered, hide lobby window and put event for the game
            # window with necessary arguments (server name, client name, game 
            # name, is_owner, spectator, spectator_queue)
            self.hide()
            self.events.put(('game', threading.current_thread(),
                             [self.server_name, self.client_name, msg_parts[1],
                              int(msg_parts[2]), True, msg_parts[3]]))
