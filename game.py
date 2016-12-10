# -*- coding: utf-8 -*-
"""
Created on Sat Dec 10 12:54:37 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
import random
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Classes ---------------------------------------------------------------------
class Game():
    '''Game session.
    '''
    def __init__(self, game_list, channel, server_name,
                 name, owner, width, height):
        self.game_list = game_list
        
        # Game attributes
        self.name = name
        self.state = 'opened'
        self.width = width
        self.height = height
        self.owner = owner
        self.players = set()
        self.players.add(owner)
        
        # Communication
        self.server_name = server_name
        self.channel = channel
        self.game_queue = channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_queue,
                                routing_key=self.server_name + common.SEP +\
                                    self.name)
        self.channel.basic_consume(self.process_request,
                                   queue=self.game_queue,
                                   no_ack=True)
    
    def __del__(self):
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.game_queue,
                                  routing_key=self.server_name + common.SEP +\
                                      self.name)
        
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
                    # TODO: destroy game
                    pass
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
                                       self.width, self.height])
        
        # Get players request
        if msg_parts[0] == common.REQ_GET_PLAYERS:
            response = common.RSP_LIST_PLAYERS + common.SEP +\
                common.SEP.join(self.players)

        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s', response)
