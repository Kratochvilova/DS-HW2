# -*- coding: utf-8 -*-
"""
Created on Sat Dec 10 12:54:37 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
from common import send_message
import random
import pika
import threading
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Classes ---------------------------------------------------------------------
class Game(threading.Thread):
    '''Game session.
    '''
    def __init__(self, game_list, server_args, name, owner, width, height):
        super(Game, self).__init__(name='Game thread: %s' % name)
        
        self.game_list = game_list
        
        # Game attributes
        self.name = name
        self.state = 'opened'
        self.width = width
        self.height = height
        self.ship_number = int(self.width) * int(self.height) / 3
        
        # Players
        self.client_queues = {}
        
        self.players = set()
        self.spectators = set()
        
        self.owner = owner
        self.players.add(self.owner)
        
        self.fields = {}
        self.player_hits = {}
        
        self.on_turn = None
        self.player_order = []
        
        # Communication
        self.server_name = server_args.name
        self.host = server_args.host
        self.port = server_args.port
        
        # To synchronize creation of the game communication, and sending enter
        # game event to client
        self.ready_event = threading.Event()
    
    def run(self):
        '''Method for running the thread.
        '''
        # Connection
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=self.host, port=self.port))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='direct_logs', type='direct')
        
        # Game queue
        self.game_queue =\
            self.channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_queue,
                                routing_key=self.server_name + common.SEP +\
                                    self.name)
        self.channel.basic_consume(self.process_request,
                                   queue=self.game_queue,
                                   no_ack=True)
        
        # Spectator queue
        self.spectator_queue =\
            self.channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.spectator_queue,
                                routing_key=self.spectator_queue)
        
        # Control queue for quiting consuming
        self.control_queue =\
            self.channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.control_queue,
                                routing_key=self.control_queue)
        self.channel.basic_consume(self.quit_game,
                                   queue=self.control_queue,
                                   no_ack=True)
        
        self.ready_event.set()
        self.channel.start_consuming()
        self.game_list.remove_game(self.name)

    def quit_game(self, ch, method, properties, body):
        '''To quit the game from different thread.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        self.channel.stop_consuming()

    def wait_for_ready(self):
        '''To synchronize creation of the game communication, and sending enter
        game event to client
        '''
        self.ready_event.wait()
    
    def check_ships(self, ships):
        if len(ships) != self.ship_number:
            return False
        
        for ship in ships:
            ship_position = ship.split(common.FIELD_SEP)
            if int(ship_position[0]) < 0 or int(ship_position[1]) < 0 or\
                int(ship_position[0]) > self.height or\
                int(ship_position[1]) > self.width:
                return False
        
        return True
    
    def add_ships(self, player, ships):
        '''Add ships to player field.
        @param player: player name
        @param ships: list of tuples (row, column)
        '''
        self.fields[player] = common.Field(self.width, self.height)
        for ship in ships:
            ship_position = ship.split(common.FIELD_SEP)
            self.fields[player].add_item(int(ship_position[0]),
                                         int(ship_position[1]),
                                         common.FIELD_SHIP)

    def get_field(self, player):
        '''Get field information for specific player.
        @param player: player
        '''
        result = []
        if player not in self.fields:
            return result
        return self.fields[player].get_all_items()

    def get_hits(self, player):
        '''Get hit information for specific player.
        @param player: player
        '''
        result = []
        if player not in self.player_hits:
            return result
        return self.player_hits[player]
    
    def check_sink_ship(self, field, row, column, searched, hit_ships):
        '''Check recursively if the ship sunk.
        @param field: Field
        @param row: row
        @param column: column
        @param searched: list of searched positions
        @hit_ships: list of positions where the ship has been hit
        @return None if found position where the ship is still unhit, list of
        hit_ships otherwise
        '''
        searched.append((row, column))
        if field.get_item(row, column) == common.FIELD_SHIP:
            return None
        if field.get_item(row, column) == common.FIELD_HIT_SHIP:
            hit_ships.append((row, column))
            if (row-1, column) not in searched:
                result = self.check_sink_ship(field, row-1, column, 
                                              searched, hit_ships)
                if result is None:
                    return None
            if (row+1, column) not in searched:
                result = self.check_sink_ship(field, row+1, column,
                                              searched, hit_ships)
                if result is None:
                    return None
            if (row, column-1) not in searched:
                result = self.check_sink_ship(field, row, column-1,
                                              searched, hit_ships)
                if result is None:
                    return None
            if (row, column+1) not in searched:
                result = self.check_sink_ship(field, row, column+1,
                                              searched, hit_ships)
                if result is None:
                    return None

        return hit_ships
    
    def sink_ship(self, field, hit_ships):
        '''Make ship sinked.
        @param field: Field
        @param hit_ships: list of positions where the ship has been hit
        @return list of strings encoding positions where the ship has been hit
        '''
        # Make ship sinked and make strings
        hit_ships_string = []
        for ship in hit_ships:
            hit_ships_string.append(
                str(ship[0]) + common.FIELD_SEP + str(ship[1]))
            field.change_item(ship[0], ship[1], common.FIELD_HIT_SHIP,
                              common.FIELD_SINK_SHIP)
        return hit_ships_string
    
    def count_player_ships(self, player):
        ships = self.fields[player].get_all_items(common.FIELD_SHIP)
        return len(ships)
    
    def check_end_game(self):
        number_unfinished_players = 0
        for field in self.fields.values():
            if field.get_all_items(common.FIELD_SHIP) != []:
                number_unfinished_players += 1
        return number_unfinished_players <= 1
    
    def player_left(self, player):
        '''Actions on player leaving or disconnecting from the game
        @param player: name of player
        '''
        # Remove player's client queue
        try:
            del self.client_queues[player]
        except KeyError:
            pass
        
        # If noone is in the game
        if len(self.client_queues.keys()) == 0:
            # Quit game
            self.channel.stop_consuming()
            self.game_list.remove_game(self.name)
        
        # Else we might need to change the owner
        elif self.owner == player:
            new_owner = random.choice(self.client_queues.keys())
            self.owner = new_owner
            # Send event that owner changed
            send_message(self.channel, [common.E_NEW_OWNER, new_owner],
                         [self.server_name, self.name, common.KEY_GAME_EVENTS])

    def process_request(self, ch, method, properties, body):
        '''Process game request.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Processing game request.')
        LOG.debug('Received message: %s', body)
        msg_parts = body.split(common.SEP)
        response = ''
        
        # Disconnect request
        if msg_parts[0] == common.REQ_DISCONNECT:
            response = common.RSP_DISCONNECTED
            self.player_left(msg_parts[1])
        
        # Leave game request
        if msg_parts[0] == common.REQ_LEAVE_GAME:
            if len(msg_parts) != 2:
                response = common.RSP_INVALID_REQUEST
            else:
                try:
                    self.players.remove(msg_parts[1])
                except ValueError:
                    pass
                response = common.RSP_GAME_LEFT
                self.player_left(msg_parts[1])
                # Send event that player left
                send_message(self.channel, [common.E_PLAYER_LEFT,msg_parts[1]],
                             [self.server_name, self.name,
                              common.KEY_GAME_EVENTS])
                                               
        # Get dimensions request
        if msg_parts[0] == common.REQ_GET_DIMENSIONS:
            response = common.SEP.join([common.RSP_DIMENSIONS,
                                       self.width, self.height,
                                       str(self.ship_number)])
        
        # Get players request
        if msg_parts[0] == common.REQ_GET_PLAYERS:
            response = common.SEP.join([common.RSP_LIST_PLAYERS] +\
                                        list(self.players))

        # Get players ready request
        if msg_parts[0] == common.REQ_GET_PLAYERS_READY:
            ready = [p for p in self.fields if self.fields[p] != {}]
            response = common.SEP.join([common.RSP_LIST_PLAYERS_READY] + ready)
        
        # Get owner request
        if msg_parts[0] == common.REQ_GET_OWNER:
            response = common.SEP.join([common.RSP_OWNER, self.owner])
        
        # Get turn request
        if msg_parts[0] == common.REQ_GET_TURN:
            if self.on_turn == None:
                response = common.RSP_TURN
            else:
                response = common.RSP_TURN + common.SEP + self.on_turn
        
        # Get field request
        if msg_parts[0] == common.REQ_GET_FIELD:
            response = common.SEP.join([common.RSP_FIELD] +\
                                        self.get_field(msg_parts[1]))
        
        # Get hits request
        if msg_parts[0] == common.REQ_GET_HITS:
            response = common.SEP.join([common.RSP_HITS] +\
                                        self.get_hits(msg_parts[1]))    
        
        # Get all fields request
        if msg_parts[0] == common.REQ_GET_ALL_FIELDS:
            if msg_parts[1] not in self.spectators:
                response = common.RSP_PERMISSION_DENIED
            else:
                response = common.RSP_ALL_FIELDS
                for player in self.players:
                    items = self.fields[player].get_all_items()
                    response += common.SEP + common.SEP.join([player] + items)
        
        if msg_parts[0] == common.REQ_GET_SPECTATOR_QUEUE:
            if msg_parts[1] not in self.spectators:
                response = common.RSP_PERMISSION_DENIED
            else:
                response = common.RSP_SPECTATOR_QUEUE + common.SEP +\
                    self.spectator_queue
        
        # Set ready request
        if msg_parts[0] == common.REQ_SET_READY:
            if not self.check_ships(msg_parts[2:]):
                response = common.RSP_SHIPS_INCORRECT
            else:
                self.add_ships(msg_parts[1], msg_parts[2:])
                response = common.RSP_READY
                # Send event that player is ready
                send_message(self.channel,
                             [common.E_PLAYER_READY, msg_parts[1]],
                             [self.server_name, self.name,
                              common.KEY_GAME_EVENTS])
        
        # Start game request
        if msg_parts[0] == common.REQ_START_GAME:
            response = common.RSP_OK
            if not self.players.issubset(set(self.fields.keys())):
                response = common.RSP_NOT_ALL_READY
            else:
                self.state = 'closed'
                for player in self.players:
                    self.player_hits[player] = []
                # Send event about game start
                send_message(self.channel, [self.name],
                             [self.server_name, common.KEY_GAME_CLOSE])
                # Determine player order
                self.on_turn = self.owner
                self.player_order.append(self.owner)
                not_sorted = list(self.players)
                not_sorted.remove(self.owner)
                while len(not_sorted) > 0:
                    random_player = random.choice(not_sorted)
                    self.player_order.append(random_player)
                    not_sorted.remove(random_player)
                
                # Send event that game starts
                send_message(self.channel,
                             [common.E_GAME_STARTS, self.on_turn],
                             [self.server_name, self.name,
                              common.KEY_GAME_EVENTS])
        
        # Shoot request
        if msg_parts[0] == common.REQ_SHOOT:
            if msg_parts[1] != self.on_turn:
                response = common.RSP_NOT_ON_TURN
            else:
                item = self.fields[msg_parts[2]].get_item(int(msg_parts[3]),
                                                          int(msg_parts[4]))
                if item is None:
                    item = common.FIELD_WATER
                self.player_hits[msg_parts[1]].append(common.FIELD_SEP.join(
                    [msg_parts[2], msg_parts[3], msg_parts[4], item]))
                if item == common.FIELD_WATER:
                    response = common.SEP.join([common.RSP_MISS]+msg_parts[1:])
                else:
                    self.fields[msg_parts[2]].change_item(
                        int(msg_parts[3]), int(msg_parts[4]),
                        common.FIELD_SHIP, common.FIELD_HIT_SHIP)
                    response = common.SEP.join([common.RSP_HIT]+msg_parts[1:])
                    # Notify the hit player
                    send_message(self.channel, [common.RSP_HIT]+msg_parts[1:],
                                 [self.client_queues[msg_parts[2]]])
                    # Send secret event for spectators
                    send_message(self.channel, [common.E_HIT] + msg_parts[1:],
                                 [self.spectator_queue])
                                 
                    # Check if ship sinked
                    ships = self.check_sink_ship(self.fields[msg_parts[2]],
                                                 int(msg_parts[3]),
                                                 int(msg_parts[4]), [], [])
                    if ships is not None:
                        ships_string= self.sink_ship(self.fields[msg_parts[2]],
                                                     ships)
                        send_message(self.channel, [common.E_SINK,
                                     msg_parts[2]] + ships_string,
                                     [self.server_name, self.name,
                                      common.KEY_GAME_EVENTS])
                        
                        if self.count_player_ships(msg_parts[2]) == 0:
                            self.players.remove(msg_parts[2])
                            self.spectators.add(msg_parts[2])
                            send_message(self.channel, [common.E_PLAYER_END,
                                                        msg_parts[2]],
                                         [self.server_name, self.name,
                                          common.KEY_GAME_EVENTS])
                            if self.on_turn == msg_parts[2]:
                                # Change turn
                                i = self.player_order.index(self.on_turn) - 1
                                if i < 0 :
                                    i = len(self.player_order)
                                self.on_turn = self.player_order[i]
                            del self.player_order[self.player_order.index(
                                                                msg_parts[2])]
                            
                            # Check end-game condition
                            if self.check_end_game():
                                send_message(self.channel, [common.E_END_GAME],
                                             [self.server_name, self.name,
                                              common.KEY_GAME_EVENTS])
                    
                # Change turn
                next_index = self.player_order.index(self.on_turn) + 1
                if next_index >= len(self.player_order):
                    next_index = 0
                self.on_turn = self.player_order[next_index]
                # Send on turn event
                send_message(self.channel, [common.E_ON_TURN, self.on_turn],
                             [self.server_name, self.name,
                              common.KEY_GAME_EVENTS])

        # Restart session request
        if msg_parts[0] == common.REQ_RESTART_SESSION:
            if self.check_end_game():
                response = common.RSP_OK
                # Send restart session event
                send_message(self.channel, [common.E_SESSION_RESTARTS],
                             [self.server_name, self.name,
                              common.KEY_GAME_EVENTS])
                # Restart game
                self.fields = {}
                self.on_turn = None
                self.player_hits = {}
                self.player_order = []
        
        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s', response)
