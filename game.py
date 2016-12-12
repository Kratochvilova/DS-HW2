# -*- coding: utf-8 -*-
"""
Created on Sat Dec 10 12:54:37 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
from windows import send_message
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
        self.players = {}
        self.players[self.owner] = {}
        self.on_turn = None
        self.player_hits = {}
        
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
            ship_position = ship.split(common.BUTTON_SEP)
            if int(ship_position[0]) < 0 or int(ship_position[1]) < 0 or\
                int(ship_position[0]) > self.height or\
                int(ship_position[1]) > self.width:
                return False
        
        return True
    
    def add_ships(self, player, ships):
        '''Add ships to player.
        @param ships: list of tuples (row, column)
        '''
        for ship in ships:
            ship_position = ship.split(common.BUTTON_SEP)
            self.players[player][(ship_position[0], ship_position[1])] = 'ship'

    def get_fields(self, player):
        '''Get field information for specific player.
        @param player: player
        '''
        result = []
        for position, value in self.players[player].items():
            result.append(common.BUTTON_SEP.join([player, position[0],
                                                 position[1], value]))
        try:
            for position, value in self.player_hits[player].items():
                result.append(common.BUTTON_SEP.join([value[0], position[0],
                                                     position[1], value[1]]))
        except KeyError:
            pass
        return result

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
            if len(self.players.keys()) <= 1:
                # Quit game
                self.channel.stop_consuming()
                self.game_list.remove_game(self.name)
                
            elif self.owner == msg_parts[1]:
                rest = [p for p in self.players.keys() if p != msg_parts[1]]
                new_owner = random.choice(rest)
                self.owner = new_owner
                # Send event that owner changed
                send_message(self.channel, [common.E_NEW_OWNER, new_owner],
                             [self.server_name, self.name,
                              common.KEY_GAME_EVENTS])
        
        # Leave game request
        if msg_parts[0] == common.REQ_LEAVE_GAME:
            if len(msg_parts) != 2:
                response = common.RSP_INVALID_REQUEST
            else:
                try:
                    del self.players[msg_parts[1]]
                except KeyError:
                    pass
                response = common.RSP_GAME_LEFT
                # Send event that player left
                send_message(self.channel, [common.E_PLAYER_LEFT,msg_parts[1]],
                             [self.server_name, self.name,
                              common.KEY_GAME_EVENTS])
                
                if len(self.players.keys()) == 0:
                    # Quit game
                    self.channel.stop_consuming()
                    self.game_list.remove_game(self.name)
                
                elif self.owner == msg_parts[1]:
                    new_owner = random.choice(self.players.keys())
                    self.owner = new_owner
                    # Send event that owner changed
                    send_message(self.channel, [common.E_NEW_OWNER, new_owner],
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
                                        self.players.keys())

        # Get players ready request
        if msg_parts[0] == common.REQ_GET_PLAYERS_READY:
            ready = [p for p in self.players if self.players[p] != {}]
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
        if msg_parts[0] == common.REQ_GET_FIELDS:
            response = common.SEP.join([common.RSP_FIELDS] +\
                                        self.get_fields(msg_parts[1]))

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
            for player_field in self.players.values():
                if player_field == {}:
                    response = common.RSP_NOT_ALL_READY
            if response == common.RSP_OK:
                self.on_turn = self.owner
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
                response = common.RSP_SHOT
                # TODO: determine hit
                # TODO: notify msg_parts[2]
                # TODO: send event if ship sinked
                # TODO: check end-game condition
                # TODO: change turn
        
        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s', response)
