# -*- coding: utf-8 -*-
"""
Created on Fri Dec  9 20:55:58 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
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
        
        self.row = row
        self.column = column
        
        self.color = None
        
        # Colors
        self.colors = {
            common.FIELD_WATER: '#675BEB',
            common.FIELD_SHIP: '#A56721',
            common.FIELD_HIT_SHIP: '#C00000',
            common.FIELD_SINK_SHIP: '#000000',
            common.FIELD_UNKNOWN: '#E4E4E4',
            'shot': '#A1A1A1'}
        
        if self.parent == 'player':
            self.change_color(common.FIELD_WATER)
        if self.parent == 'opponent':
            self.change_color(common.FIELD_UNKNOWN)

    def change_color(self, color):
        '''Change color of button and its backgrounds.
        @param color: color
        '''
        self.color = color
        self.config(bg=self.colors[color],
                    activebackground=self.colors[color])
    
    def button_pressed(self):
        '''Reaction on pressing the button.
        '''
        if self.game_window.spectator:
            return
        
        LOG.debug('Pressed button on position: %s, %s', self.row, self.column)
        # If in positioning ships phase
        if self.game_window.client_name not in self.game_window.players_ready:
            if self.parent == 'opponent':
                return
            
            # Add ship
            if self.color == common.FIELD_WATER and\
                self.game_window.ships_remaining != 0:
                self.change_color(common.FIELD_SHIP)
                self.game_window.ships_remaining -= 1
                # Update ready_label
                self.game_window.ready_label.destroy()
                self.game_window.ready_label = Tkinter.Label(
                    self.game_window.frame_player, 
                    text='Ships remaining: %s' %\
                        self.game_window.ships_remaining)
                self.game_window.ready_label.grid(
                    row=self.game_window.height+2,
                    columnspan=self.game_window.width)
                # Update field
                self.game_window.fields[self.game_window.client_name].add_item(
                    self.row, self.column, common.FIELD_SHIP)
            
            # Remove ship
            elif self.color == common.FIELD_SHIP:
                self.change_color(common.FIELD_WATER)
                self.game_window.ships_remaining += 1
                # Update ready_label
                self.game_window.ready_label.destroy()
                self.game_window.ready_label = Tkinter.Label(
                    self.game_window.frame_player, 
                    text='Ships remaining: %s' %\
                        self.game_window.ships_remaining)
                self.game_window.ready_label.grid(
                    row=self.game_window.height+2,
                    columnspan=self.game_window.width)
                # Update field
                self.game_window.fields[
                    self.game_window.client_name].remove_item(self.row,
                                                              self.column)
        
        # If game started and on turn
        if self.game_window.on_turn == self.game_window.client_name:
            if self.parent == 'player' or self.game_window.opponent == None:
                return
            
            # Dont allow shooting at known positions
            if self.color != 'unknown':
                return
            
            # Mark as shot and send request to server
            self.change_color('shot')
            send_message(self.game_window.channel,
                         [common.REQ_SHOOT, self.game_window.client_name,
                          self.game_window.opponent,
                          str(self.row), str(self.column)],
                         [self.game_window.server_name,
                          self.game_window.game_name],
                          self.game_window.client_queue)
        
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
        
        # Attributes of the game
        self.players = set()
        self.players_ready = set()
        self.on_turn = None
        self.ships_remaining = None
        
        # Fields
        self.player_buttons = {}
        self.opponent_buttons = {}
        self.opponent = None
        self.fields = {}

        # Spectator option
        self.spectator = False
        
        self.ready_event = threading.Event()
        
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
        
        self.frame_opponent = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_opponent.pack()
        
        # Communication
        self.channel = channel
        self.client_queue = client_queue
        self.events_queue = events_queue
        
        self.root.withdraw()
    
    def show(self, arguments):
        '''Show the game window.
        @param arguments: arguments passed from previous window: 
                          [server_name, client username, game name, is_owner,
                          spectator, spectator_queue]
        '''
        LOG.debug('Showing game window.')
        self.server_name = arguments[0]
        self.client_name = arguments[1]
        self.game_name = arguments[2]
        self.is_owner = arguments[3]
        self.spectator = arguments[4]
        self.spectator_queue = arguments[5]
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
        if self.spectator:
            self.channel.queue_bind(exchange='direct_logs',
                                    queue=self.events_queue,
                                    routing_key=self.spectator_queue)
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
        self.send_simple_request(common.REQ_GET_DIMENSIONS)
        self.send_simple_request(common.REQ_GET_PLAYERS)
        self.send_simple_request(common.REQ_GET_PLAYERS_READY)
        self.send_simple_request(common.REQ_GET_OWNER)
        self.send_simple_request(common.REQ_GET_TURN)
        
        self.wait_for_ready()
        if self.on_turn is not None:
            print 'Want to start game'
            self.at_game_start(self.on_turn)
            self.send_name_request(common.REQ_GET_FIELD)
            self.send_name_request(common.REQ_GET_HITS)

        if self.spectator:
            self.send_name_request(common.REQ_GET_ALL_FIELDS)

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

    def wait_for_ready(self):
        '''To synchronize game communication.
        '''
        self.ready_event.wait()
        
    def disconnect(self):
        '''Disconnect from server.
        '''
        send_message(self.channel, [common.REQ_DISCONNECT, self.client_name],
                     [self.server_name], self.client_queue)
        send_message(self.channel, [common.REQ_DISCONNECT, self.client_name],
                     [self.server_name, self.game_name], self.client_queue)
    
    def leave(self):
        '''Leave game session.
        '''
        send_message(self.channel, [common.REQ_LEAVE_GAME, self.client_name], 
                     [self.server_name, self.game_name], self.client_queue)

    def send_simple_request(self, request):
        '''Send request to get info from server
        '''
        send_message(self.channel, [request],
                     [self.server_name, self.game_name], self.client_queue)
    
    def send_name_request(self, request):
        '''Send request to get information about fields from server
        '''
        send_message(self.channel, [request, self.client_name],
                     [self.server_name, self.game_name], self.client_queue)
    
    def reset_setting(self):
        '''Resets frames, dimensions, list of players
        '''
        # Reset frames
        self.frame_player.destroy()
        self.frame_opponent.destroy()
        
        self.frame_player = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_player.pack()
        
        self.frame_opponent = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_opponent.pack()
        
        self.opponent_menu = Tkinter.OptionMenu(self.frame_opponent, '', '')
        
        # Reset game attributes
        self.width = None
        self.height = None
        self.is_owner = False
        self.players = set()
        self.on_turn = None
        self.ships_remaining = None
        self.player_buttons = {}
        self.opponent_buttons = {}
        self.opponent = None
        self.fields = {}

    def set_setting(self, width, height, ships):
        '''Sets all widgets.
        '''
        # Set number of ships to position
        self.ships_remaining = int(ships)
        
        # Set dimensions
        self.width = int(width)
        self.height = int(height)
        
        # Set client field
        self.fields[self.client_name] = common.Field(self.width, self.height)
        
        # Player frame
        self.game_label = Tkinter.Label(self.frame_player,
                                        text=self.client_name)
        self.game_label.grid(columnspan=self.width)
        
        for i in range(self.height):
            for j in range(self.width):
                b = GameButton(self.frame_player, i, j, 'player', self)
                b.grid(row=i+1, column=j)
                self.player_buttons[(i, j)] = b

        if not self.spectator:
            self.ready_label = Tkinter.Label(self.frame_player,
                                             text='Ships remaining: %s' %\
                                                 self.ships_remaining)
            self.ready_label.grid(row=self.height+2, columnspan=self.width)
            
            self.button_ready = Tkinter.Button(self.frame_player, text="Ready",
                                               command=self.get_ready)
            self.button_ready.grid(row=self.height+3, columnspan=self.width)
        
        # Start button in case of owner
        if self.is_owner:
            self.button_start = Tkinter.Button(self.frame_player,
                                               text="Start game",
                                               command=self.start_game)
            self.button_start.grid(row=self.height+4, columnspan=self.width)
            
        # Opponent frame
        self.opponent_menu = Tkinter.OptionMenu(self.frame_opponent, '', '')
        self.opponent_menu.grid(columnspan=self.width)
        self.opponent_label = Tkinter.Label(self.frame_opponent,
                                            text='None selected')
        self.opponent_label.grid(row=1, columnspan=self.width)
        
        for i in range(self.height):
            for j in range(self.width):
                b = GameButton(self.frame_opponent, i, j, 'opponent',self)
                b.grid(row=i+2, column=j)
                self.opponent_buttons[(i, j)] = b
            
        # Kick button in case of owner
        if self.is_owner:
            self.button_kick = Tkinter.Button(self.frame_opponent, 
                                              text="Kick out", 
                                              command=self.start_game) #TODO
            self.button_kick.grid(row=self.height+4,
                                  columnspan=self.width)

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
        self.opponent_menu['menu'].delete(0, 'end')
        
        # Insert new player list (tk._setit hooks them up to var)
        for opp in self.players:
            self.opponent_menu['menu'].add_command(label=opp,
                command=lambda opp=opp: self.opponent_selected(opp))
    
    def remove_player(self, name):
        '''Remove player from list of players and actualize the opponent_menu.
        @param name: name of player
        '''
        # Remove player from list
        try:
            self.players.remove(name)
        except KeyError:
            return
        
        # Reset currently selected and delete old options
        self.opponent_menu['menu'].delete(0, 'end')
        
        # Insert new player list (tk._setit hooks them up to var)
        for opp in self.players:
            self.opponent_menu['menu'].add_command(label=opp,
                command=Tkinter._setit(self.opponent, opp))
    
    def opponent_selected(self, name):
        '''When opponent is selected, either ready indicator should appear 
        (if in the stage of positioning ships), or the field should actualize
        (if playing).
        @param name: name of the selected opponent
        '''
        self.opponent = name
        self.opponent_label.destroy()
        self.opponent_label = Tkinter.Label(self.frame_opponent, text=name)
        self.opponent_label.grid(row=1, columnspan=self.width)
            
        if self.on_turn is None:
            if name in self.players_ready:
                label = 'Ready'
            else:
                label = 'Not ready'
            
            try:
                self.ready_label_op.destroy()
            except AttributeError:
                pass
            self.ready_label_op = Tkinter.Label(self.frame_opponent,text=label)
            self.ready_label_op.grid(row=self.height+3, columnspan=self.width)
        else:
            self.update_buttons()
    
    def kick_out(self):
        pass
    
    def get_ready(self):
        '''Confirm the ship positioning to the server.
        '''
        if self.client_name in self.players_ready:
            return
        elif self.ships_remaining != 0:
             tkMessageBox.showinfo('Game', 'Ships remaining: %s' %\
                 self.ships_remaining)
        else:
            # Send request to server
            ships = self.fields[self.client_name].get_all_items('ship')
            send_message(self.channel,
                         [common.REQ_SET_READY, self.client_name] + ships,
                         [self.server_name, self.game_name], self.client_queue)
            # Color the button
            self.button_ready.config(bg='#68c45c',activebackground = '#68c45c')
    
    def start_game(self):
        '''Check if all players are ready and start the game.
        '''
        if self.players.issubset(self.players_ready) and\
            self.client_name in self.players_ready:
            # Send start game request to server
            send_message(self.channel,
                         [common.REQ_START_GAME, self.client_name],
                         [self.server_name, self.game_name], self.client_queue)
        else:
            tkMessageBox.showinfo('Game', 'Not all players are ready')
    
    def at_game_start(self, on_turn):
        '''Actions on game start.
        '''
        LOG.debug('Game started.')
        if not self.spectator:
            self.ready_label.destroy()
            self.button_ready.destroy()
        try:
            self.ready_label_op.destroy()
        except AttributeError:
            pass
        if self.is_owner:
            self.button_start.destroy()
            
        self.on_turn = on_turn
        self.turn_label = Tkinter.Label(self.frame_player,
                                        text='Turn: %s' % self.on_turn)
        self.turn_label.grid(row=self.height+2, columnspan=self.width)
        # Initialize fields for other players
        for player in self.players:
            self.fields[player] = common.Field(self.width, self.height)
    
    def update_buttons(self):
        for key, value in self.fields[self.client_name].field_dict.items():
            self.player_buttons[key].change_color(value)
        if self.on_turn is not None and self.opponent is not None:
            for button in self.opponent_buttons.values():
                if self.spectator:
                    button.change_color(common.FIELD_WATER)
                else:
                    button.change_color(common.FIELD_UNKNOWN)
            for key, value in self.fields[self.opponent].field_dict.items():
                self.opponent_buttons[key].change_color(value)
    
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
        
        # If got dimensions, create the game fields
        if msg_parts[0] == common.RSP_DIMENSIONS:
            if self.ships_remaining is not None:
                return
            self.set_setting(*msg_parts[1:])
        
        # If got list of players, add players
        if msg_parts[0] == common.RSP_LIST_PLAYERS:
            self.add_players(msg_parts[1:])
        
        # If got list of players ready, add to palyers_ready
        if msg_parts[0] == common.RSP_LIST_PLAYERS_READY:
            self.players_ready = set(msg_parts[1:])
            if self.client_name in self.players_ready:
                self.button_ready.config(bg='#68c45c',
                                         activebackground = '#68c45c')
        
        # If got owner, set if is_owner
        if msg_parts[0] == common.RSP_OWNER:
            if msg_parts[1] == self.client_name:
                if not self.is_owner:
                    # Display owner-specific widgets
                    self.button_start = Tkinter.Button(self.frame_player, 
                                                       text="Start game", 
                                                       command=self.start_game)
                    self.button_start.grid(row=self.height+4,
                                           columnspan=self.width)
                                           
                    self.button_kick = Tkinter.Button(self.frame_opponent, 
                                                      text="Kick out", 
                                                      command=self.kick_out)
                    self.button_kick.grid(row=self.height+4,
                                          columnspan=self.width)
                self.is_owner = 1
        
        # If got current turn info, update on_turn
        if msg_parts[0] == common.RSP_TURN:
            if len(msg_parts) == 1:
                self.on_turn = None
            else:
                self.on_turn = msg_parts[1]
            self.ready_event.set()
        
        # If got field, update field
        if msg_parts[0] == common.RSP_FIELD:
            field = self.fields[self.client_name]
            for item in msg_parts[1:]:
                item_parts = item.split(common.FIELD_SEP)
                for item in item_parts:
                    field.add_item(int(item_parts[0]), int(item_parts[1]),
                                   item_parts[2])
            self.update_buttons()
        
        if msg_parts[0] == common.RSP_HITS:
            for hit in msg_parts[1:]:
                self.fields[hit[0]].add_item(*hit[1:])
            self.update_buttons()

        # If got fields, update fields
        if msg_parts[0] == common.RSP_ALL_FIELDS:
            for item in msg_parts[1:]:
                item_parts = item.split(common.FIELD_SEP)
                if len(item_parts) == 1:
                    current_player = item_parts[0]
                    field = self.fields[current_player]
                else:
                    for item in item_parts:
                        field.add_item(int(item_parts[0]), int(item_parts[1]),
                                       item_parts[2])
            self.update_buttons()
        
        # If response with ready, get ready
        if msg_parts[0] == common.RSP_READY:
            self.players_ready.add(self.client_name)
        
        # If response shot
        if msg_parts[0] == common.RSP_HIT:
            field = self.fields[msg_parts[2]]
            if field.get_item(int(msg_parts[3]), int(msg_parts[4])) !=\
                common.FIELD_SINK_SHIP:
                field.add_item(int(msg_parts[3]), int(msg_parts[4]),
                               common.FIELD_HIT_SHIP)
                self.update_buttons()
            # TODO: inform who shot
        
        if msg_parts[0] == common.RSP_MISS:
            field = self.fields[msg_parts[2]]
            field.add_item(int(msg_parts[3]), int(msg_parts[4]),
                           common.FIELD_WATER)
            self.update_buttons()
    
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
                    # Display owner-specific widgets
                    self.button_start = Tkinter.Button(self.frame_player, 
                                                       text="Start game", 
                                                       command=self.start_game)
                    self.button_start.grid(row=self.height+4,
                                           columnspan=self.width)
                                           
                    self.button_kick = Tkinter.Button(self.frame_opponent, 
                                                      text="Kick out", 
                                                      command=self.kick_out)
                    self.button_kick.grid(row=self.height+4,
                                          columnspan=self.width)
                self.is_owner = 1
        
        if msg_parts[0] == common.E_PLAYER_READY:
            self.players_ready.add(msg_parts[1])

        if msg_parts[0] == common.E_GAME_STARTS:
            self.at_game_start(msg_parts[1])
        
        if msg_parts[0] == common.E_ON_TURN:
            self.on_turn = msg_parts[1]
            self.turn_label.destroy()
            self.turn_label = Tkinter.Label(self.frame_player,
                                            text='Turn: %s' % self.on_turn)
            self.turn_label.grid(row=self.height+2, columnspan=self.width)

        if msg_parts[0] == common.E_HIT:
            self.fields[msg_parts[2]].add_item(int(msg_parts[3]),
                                               int(msg_parts[4]),
                                               common.FIELD_HIT_SHIP)
        
        if msg_parts[0] == common.E_SINK:
            field = self.fields[msg_parts[1]]
            for sink_ship in msg_parts[2:]:
                sink_ship_pos = sink_ship.split(common.FIELD_SEP)
                field.add_item(int(sink_ship_pos[0]), int(sink_ship_pos[1]),
                               common.FIELD_SINK_SHIP)
            self.update_buttons()

        if msg_parts[0] == common.E_PLAYER_END:
            if msg_parts[1] == self.client_name:
                if tkMessageBox.askyesno('Game', 'You lost! Leave game?'):
                    self.leave()
                else:
                    self.spectator = True
                    self.send_name_request(common.REQ_GET_SPECTATOR_QUEUE)
                    self.send_name_request(common.REQ_GET_ALL_FIELDS)
            else:
                self.remove_player(msg_parts[1])

        if msg_parts[0] == common.E_END_GAME:
            s = self.fields[self.client_name].get_all_items(common.FIELD_SHIP)
            if s != []:
                tkMessageBox.showinfo('Game', 'Congratulations, you won!')
            else:
                tkMessageBox.showinfo('Game', 'Game ended!')
            if self.is_owner:
                if tkMessageBox.askyesno('Game', 'Restart session?'):
                    self.send_simple_request(common.REQ_RESTART_SESSION)

        if msg_parts[0] == common.E_SESSION_RESTARTS:
            self.hide()
            self.show([self.server_name, self.client_name, self.game_name,
                      self.is_owner])
