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
        self.owner = owner
        self.players = set()
        self.fields = {}
        self.players.add(self.owner)
        self.on_turn = None
        self.player_hits = {}
        self.client_queues = {}
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
        self.game_queue =\
            self.channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_queue,
                                routing_key=self.server_name + common.SEP +\
                                    self.name)
        self.channel.basic_consume(self.process_request,
                                   queue=self.game_queue,
                                   no_ack=True)
        
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
            self.fields[player].add_item(ship_position[0], ship_position[1],
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
            response = common.SEP.join([common.RSP_FIELD] +\
                                        self.get_hits(msg_parts[1]))        
        
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
                # Send event about game start
                send_message(self.channel, [self.name],
                             [self.server_name, common.KEY_GAME_CLOSE])
                # Determine player order
                self.on_turn = self.owner
                self.player_order.append(self.owner)
                not_sorted = list(self.players)
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
                item = self.fields[msg_parts[2]].get_item(msg_parts[3],
                                                          msg_parts[4])
                if item is None:
                    response = common.SEP.join([common.RSP_MISS]+msg_parts[1:])
                else:
                    response = common.SEP.join([common.RSP_HIT]+msg_parts[1:])
                    # Notify the hit player
                    send_message(self.channel, [common.RSP_HIT]+msg_parts[1:],
                                 [self.client_queues[msg_parts[2]]])
                # TODO: send event if ship sinked
                # TODO: check end-game condition
                # Change turn
                next_index = self.player_order.index(self.on_turn) + 1
                if next_index >= len(self.player_order):
                    next_index = 0
                self.on_turn = self.player_order[next_index]
                send_message(self.channel, [common.E_ON_TURN, self.on_turn],
                             [self.server_name, self.name,
                              common.KEY_GAME_EVENTS])
        
        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s', response)
