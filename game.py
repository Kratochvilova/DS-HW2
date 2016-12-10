# -*- coding: utf-8 -*-
"""
Created on Sat Dec 10 12:54:37 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger(__name__)
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
        self.channel.basic_consume(self.process_event,
                                   queue=self.game_queue,
                                   no_ack=True)
        
    def process_event(self, ch, method, properties, body):
        '''Process game event.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        pass