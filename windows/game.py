# -*- coding: utf-8 -*-
"""
Created on Fri Dec  9 20:55:58 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
from . import listen
import threading
import pika
import Tkinter
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger(__name__)
# Classes ---------------------------------------------------------------------
class GameButton(Tkinter.Button):
    '''Button in the game field.
    '''
    def __init__(self, master, row, column, parent, game_window):
        '''Init GameButton.
        @param master: master Tkinter widget
        @param row: row in the field
        @param column: column in the field
        @param parent: String, player or opponent - type of game field
        @param game_window: GameWindow
        '''
        Tkinter.Button.__init__(self, master, command=self.button_pressed)
        self.parent = parent
        self.game_window = game_window

    def button_pressed(self):
        '''Reaction on pressing the button.
        '''
        if self.parent == 'player':
            self.config(bg='blue')
        if self.parent == 'opponent':
            self.config(bg='red')

class GameWindow(object):
    '''Window for displaying game.
    '''
    def __init__(self, channel, client_queue, events_queue, events, parent):
        '''Set next window, gui elements, communication channel, and queues.
        Hides the game window.
        @param channel: pika connection channel
        @param client_queue: queue for messages to client
        @param events: Queue of events for window control
        '''
        # Next window
        self.server_window = None
        self.game_window = None
        
        # Arguments from server_window
        self.server_name = None 
        self.client_name = None
        self.game_name = None
        self.is_owner = False
        self.players = set()
        
        # Queue of events for window control
        self.events = events
        
        # GUI
        self.root = Tkinter.Toplevel(master=parent.root)
        self.root.title('Battleships')
        self.root.protocol("WM_DELETE_WINDOW", self.disconnect)
        
        self.frame = Tkinter.Frame(self.root)
        self.frame.pack()
        
        self.button_leave = Tkinter.Button(self.frame, text="Leave", 
                                           command=self.leave)
        self.button_leave.pack()
        
        self.frame_player = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_player.pack()
        
        self.frame_oponent = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_oponent.pack()
        
        # Communication
        self.channel = channel
        self.client_queue = client_queue
        self.events_queue = events_queue
        
        self.root.withdraw()
    
    def show(self, arguments):
        '''Show the game window.
        @param arguments: arguments passed from previous window: 
                          [server_name, client username, game name, is_owner]
        '''
        LOG.debug('Showing game window.')
        self.server_name = arguments[0]
        self.client_name = arguments[1]
        self.game_name = arguments[2]
        self.is_owner = arguments[3]
        self.on_show()
        self.root.deiconify()

    def on_show(self):
        '''Bind queues, set consuming and listen.
        '''
        # Binding queues
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.client_queue,
                                routing_key=self.client_queue)
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.events_queue,
                                routing_key=self.server_name + common.SEP +\
                                    self.game_name + common.SEP +\
                                    common.KEY_GAME_EVENTS)
        # Set consuming
        self.channel.basic_consume(self.on_response, 
                                   queue=self.client_queue,
                                   no_ack=True)
        self.channel.basic_consume(self.on_event, 
                                   queue=self.events_queue,
                                   no_ack=True)
        # Listening
        self.listening_thread = listen(self.channel, 'game')
        
        # Get field dimensions and players
        self.reset_setting()
        self.get_dimensions()
        self.get_players()

    def hide(self):
        '''Hide the game window.
        '''
        LOG.debug('Hiding game window.')
        self.root.withdraw()
        self.on_hide()

    def on_hide(self):
        '''Unbind queues, stop consuming.
        '''
        # Unbinding queues
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.client_queue,
                                  routing_key=self.client_queue)
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.events_queue,
                                  routing_key=self.server_name + common.SEP +\
                                     self.game_name + common.SEP +\
                                  common.KEY_GAME_EVENTS)
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
        LOG.debug('Sent message to server %s: %s', self.server_name, msg)
    
    def leave(self):
        '''Leave game session.
        '''
        msg = common.SEP.join([common.REQ_LEAVE_GAME, self.client_name])
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name + common.SEP +\
                                       self.game_name,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
        LOG.debug('Sent message to server %s: %s', self.server_name, msg)

    def reset_setting(self):
        '''Resets frames, dimensions, list of players
        '''
        # Reset frames
        self.frame_player.destroy()
        self.frame_oponent.destroy()
        
        self.frame_player = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_player.pack()
        
        self.frame_oponent = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_oponent.pack()
        
        # Reset dimensions and list of players
        self.width = None
        self.height = None
        self.players = set()

    def add_players(self, names):
        '''Add players to list of players and actualize the opponent_menu.
        @param names: names of players
        '''
        # Add player to list and remove self
        for name in names:
            self.players.add(name)
        try:
            self.players.remove(self.client_name)
        except KeyError:
            pass
        
        # Reset currently selected and delete old options
        self.opponent.set('')
        self.opponent_menu['menu'].delete(0, 'end')
        
        # Insert new player list (tk._setit hooks them up to var)
        for opp in self.players:
            self.opponent_menu['menu'].add_command(label=opp,
                command=Tkinter._setit(self.opponent, opp))
    
    def remove_player(self, name):
        '''Remove player from list of players and actualize the opponent_menu.
        @param name: name of player
        '''
        # Remove player from list
        try:
            del self.players[self.players.index(name)]
        except:
            return
        
        # Reset currently selected and delete old options
        self.opponent.set('')
        self.opponent_menu['menu'].delete(0, 'end')
        
        # Insert new player list (tk._setit hooks them up to var)
        for opp in self.players:
            self.opponent_menu['menu'].add_command(label=opp,
                command=Tkinter._setit(self.opponent, opp))
    
    def get_dimensions(self):
        '''Send get dimensions request to server.
        '''
        msg = common.REQ_GET_DIMENSIONS
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name + common.SEP +\
                                       self.game_name,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
        LOG.debug('Sent message to server %s, game %s: %s',
                  self.server_name, self.game_name, msg)
    
    def get_players(self):
        '''Send get players request to server.
        '''
        msg = common.REQ_GET_PLAYERS
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name + common.SEP +\
                                       self.game_name,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
        LOG.debug('Sent message to server %s, game %s: %s',
                  self.server_name, self.game_name, msg)
    
    def start_game(self):
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
        
        # If disconnected
        if msg_parts[0] == common.RSP_DISCONNECTED:
            self.hide()
            self.events.put(('server', None, None))
        
        # If left
        if msg_parts[0] == common.RSP_GAME_LEFT:
            self.hide()
            self.events.put(('lobby', None, 
                             [self.server_name, self.client_name]))
        
        # If response with dimensions, create the game fields
        if msg_parts[0] == common.RSP_DIMENSIONS:
            if self.width is not None:
                return
            self.width = int(msg_parts[1])
            self.height = int(msg_parts[2])
            self.game_label = Tkinter.Label(self.frame_player,
                                            text=self.client_name)
            self.game_label.grid(columnspan=self.width)
            for i in range(self.height):
                for j in range(self.width):
                    b = GameButton(self.frame_player, i+1, j, 'player', self)
                    b.grid(row=i+1, column=j)
            
            if self.is_owner:
                self.button_start = Tkinter.Button(self.frame_player, 
                                                   text="Start game", 
                                                   command=self.start_game)
                self.button_start.grid(row=self.height+2,
                                       columnspan=self.width)
            
            # Oponent game field
            self.opponent = Tkinter.StringVar(self.frame_oponent)
            self.opponent.set('')
            self.opponent_menu = Tkinter.OptionMenu(self.frame_oponent, 
                                                    self.opponent, '')
            self.opponent_menu.grid(columnspan=self.width)
            for i in range(self.height):
                for j in range(self.width):
                    b = GameButton(self.frame_oponent, i+1, j, 'opponent',self)
                    b.grid(row=i+1, column=j)
        
        # If response with players, add players
        if msg_parts[0] == common.RSP_LIST_PLAYERS:
            self.add_players(msg_parts[1:])
    
    def on_event(self, ch, method, properties, body):
        '''React on game event.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Received event: %s', body)
        msg_parts = body.split(common.SEP)
        
        if msg_parts[0] == common.E_NEW_PLAYER:
            self.add_players(msg_parts[1:])

        if msg_parts[0] == common.E_PLAYER_LEFT:
            self.remove_player(msg_parts[1])
        
        if msg_parts[0] == common.E_NEW_OWNER:
            if msg_parts[1] == self.client_name:
                if not self.is_owner:
                    self.button_start = Tkinter.Button(self.frame_player, 
                                                       text="Start game", 
                                                       command=self.start_game)
                    self.button_start.grid(row=self.height+2,
                                           columnspan=self.width)
                self.is_owner = 1
            
