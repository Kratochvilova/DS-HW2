# -*- coding: utf-8 -*-
"""
Created on Sat Dec 10 12:54:37 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
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
        self.players.add(owner)
        
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
        self.game_queue = self.channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_queue,
                                routing_key=self.server_name + common.SEP +\
                                    self.name)
        self.channel.basic_consume(self.process_request,
                                   queue=self.game_queue,
                                   no_ack=True)
        
        self.control_queue = self.channel.queue_declare(exclusive=True).method.queue
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
        response = None
        
        # Leave game request
        if msg_parts[0] == common.REQ_LEAVE_GAME:
            if len(msg_parts) != 2:
                response = common.RSP_INVALID_REQUEST
            else:
                try:
                    self.players.remove(msg_parts[1])
                except KeyError:
                    pass
                response = common.RSP_GAME_LEFT
                # Send event that player left
                msg = common.E_PLAYER_LEFT + common.SEP + msg_parts[1]
                self.channel.basic_publish(exchange='direct_logs',
                                       routing_key=self.server_name +\
                                           common.SEP + self.name +\
                                           common.SEP + common.KEY_GAME_EVENTS,
                                       body=msg)
                LOG.debug('Sent game event: %s', msg)
                if len(self.players) == 0:
                    # Quit game
                    self.channel.stop_consuming()
                
                elif self.owner == msg_parts[1]:
                    new_owner = random.choice(list(self.players))
                    self.owner = new_owner
                    # Send event that owner changed
                    msg = common.E_NEW_OWNER + common.SEP + new_owner
                    self.channel.basic_publish(exchange='direct_logs',
                                               routing_key=self.server_name +\
                                                   common.SEP + self.name +\
                                                   common.SEP +\
                                                   common.KEY_GAME_EVENTS,
                                               body=msg)
                                               
        # Get dimensions request
        if msg_parts[0] == common.REQ_GET_DIMENSIONS:
            response = common.SEP.join([common.RSP_DIMENSIONS,
                                       self.width, self.height,
                                       str(self.ship_number)])
        
        # Get players request
        if msg_parts[0] == common.REQ_GET_PLAYERS:
            response = common.RSP_LIST_PLAYERS + common.SEP +\
                common.SEP.join(self.players)

        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s', response)
