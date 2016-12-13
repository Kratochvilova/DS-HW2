#!/usr/bin/python
"""
Created on Thu Dec  1 15:41:13 2016

@author: pavla kratochvilova
"""
# Setup Python logging --------------------------------------------------------
import logging
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Imports----------------------------------------------------------------------
import serverlib
import common
from common import send_message
from game import Game
from argparse import ArgumentParser
from time import sleep
import threading
import pika
# Constants -------------------------------------------------------------------
___NAME = 'Battleship Game Client'
___VER = '0.1.0.0'
___DESC = 'Battleship Game Client'
___BUILT = '2016-11-10'
# Classes ---------------------------------------------------------------------
class GameList():
    '''List of game sessions.
    '''
    def __init__(self, channel, server_args, clients):
        # Dict of running games
        self.games = {}
        
        # Communication
        self.server_args = server_args
        self.server_name = server_args.name
        self.clients = clients
        self.channel = channel
        self.games_queue = channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.games_queue,
                                routing_key=common.make_key_games(
                                    self.server_name))
        self.channel.basic_consume(self.reply_request,
                                   queue=self.games_queue,
                                   no_ack=True)
        
    def add_game(self, name, owner, width, height):
        '''Add game to the dict of games.
        @param name: name of game
        @param owner: owner of game
        @param width: width of field of game
        @param height: height of field of game
        '''
        # Create game in new thread
        game = Game(self, self.server_args, name, owner, width, height)
        self.games[name] = game
        game.start()
        
        # Send event about added game
        msg = serverlib.make_e_game_open(name)
        send_message(self.channel, msg,
                     common.make_key_game_advert(self.server_name))
        
        return game

    def remove_game(self, name):
        '''Remove game from the dict of games.
        @param name: name of game
        '''
        try:
            del self.games[name]
            # Send event about removed game
            msg = serverlib.make_e_game_end(name)
            send_message(self.channel, msg,
                         common.make_key_game_advert(self.server_name))
        except KeyError:
            pass
    
    def get_games(self, state=None):
        '''Get list of games, optionally filtering by state.
        @param state: state of game
        @return list: list of games
        '''
        if state == None:
            return self.games
        return [game for game in self.games.values() if game.state == state]
    
    def process_request(self, msg_parts, properties):
        '''Process request about list of games.
        @param msg_parts: parsed message
        @param properties: pika.spec.BasicProperties
        @return String, response
        '''
        # Get list of games request
        if msg_parts[0] == common.REQ_LIST_OPENED:
            game_names = [game.name for game in self.get_games('opened')]
            return serverlib.make_rsp_list_opened(game_names)
        if msg_parts[0] == common.REQ_LIST_CLOSED:
            game_names = [game.name for game in self.get_games('closed')]
            return serverlib.make_rsp_list_closed(game_names)
        
        # Create game request
        if msg_parts[0] == common.REQ_CREATE_GAME:
            if len(msg_parts) != 5 or msg_parts[1].strip() == '' or\
                msg_parts[3].strip() == '' or msg_parts[4].strip() == '':
                return serverlib.make_rsp_invalid_request()
            
            game_name = msg_parts[1]
            client_name = msg_parts[2]
            width = msg_parts[3]
            height = msg_parts[4]
            
            if game_name in self.games:
                return serverlib.make_rsp_name_exists()
            if client_name not in self.clients.client_set:
                return serverlib.make_rsp_permission_denied()
            
            game = self.add_game(game_name, client_name, width, height)
            game.wait_for_ready()
            game.client_queues[client_name] = properties.reply_to
            return serverlib.make_rsp_game_entered(game_name, 1)
        
        # Join game request
        if msg_parts[0] == common.REQ_JOIN_GAME:
            if len(msg_parts) != 3:
                return serverlib.make_rsp_invalid_request()
            
            game_name = msg_parts[1]
            client_name = msg_parts[2]
            
            if game_name not in self.games:
                return serverlib.make_rsp_name_doesnt_exist()
            if client_name not in self.clients.client_set:
                return serverlib.make_rsp_permission_denied()
            
            self.games[game_name].client_queues[client_name] =\
                properties.reply_to
            if client_name not in self.games[game_name].players:
                self.games[game_name].players.add(client_name)
                # Send event that new player was added
                msg = serverlib.make_e_new_player(client_name)
                send_message(self.channel, msg,
                             common.make_key_game_events(self.server_name,
                                                         game_name))
            
            return serverlib.make_rsp_game_entered(game_name, 0)
        
        # Spectating game request
        if msg_parts[0] == common.REQ_SPECTATE_GAME:
            if len(msg_parts) != 3:
                return serverlib.make_rsp_invalid_request()
            
            game_name = msg_parts[1]
            client_name = msg_parts[2]
            
            if game_name not in self.games:
                return serverlib.make_rsp_name_doesnt_exist()
            if client_name not in self.clients.client_set:
                return serverlib.make_rsp_permission_denied()
            if client_name in self.games[game_name].players:
                return serverlib.make_rsp_permission_denied()
            
            game = self.games[game_name]
            game.spectators.add(client_name)
            return serverlib.make_rsp_game_spectate(game_name, 0,
                                                    game.spectator_queue)

    def reply_request(self, ch, method, properties, body):
        '''Reply to request about list of games.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Processing game list request.')
        LOG.debug('Received message: %s', body)
        msg_parts = body.split(common.SEP)
        response = self.process_request(msg_parts, properties)
        
        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s', response)

class Clients():
    '''Process client connections.
    '''
    def __init__(self, channel, server_name):
        '''Set a set of client usernames, communication channel, and consuming.
        @param channel: pika connection channel
        @param server_name: name of server
        '''
        # Set of client usernames
        self.client_set = set()
        
        self.server_name = server_name
        
        # Communication
        self.channel = channel
        self.connect_queue = channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.connect_queue,
                                routing_key=self.server_name)
        self.channel.basic_consume(self.process_client,
                                   queue=self.connect_queue,
                                   no_ack=True)
    
    def process_client(self, ch, method, properties, body):
        '''Process client's connection request.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode        
        '''
        LOG.debug('Processing connection request.')
        LOG.debug('Received message: %s', body)
        msg_parts = body.split(common.SEP)
        response = None
        
        # Connect request
        if msg_parts[0] == common.REQ_CONNECT:
            if len(msg_parts) != 2:
                response = serverlib.make_rsp_invalid_request()
            else:
                client_name = msg_parts[1].strip()
                if client_name in self.client_set:
                    response = serverlib.make_rsp_username_taken()
                else:
                    self.client_set.add(msg_parts[1].strip())
                    response = serverlib.make_rsp_connected(self.server_name,
                                                            client_name)
        
        # Disconnect request
        elif msg_parts[0] == common.REQ_DISCONNECT:
            try:
                self.client_set.remove(msg_parts[1])
            except KeyError:
                pass
            response = serverlib.make_rsp_disconnected()
        
        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s', response)

# Functions -------------------------------------------------------------------
def __info():
    return '%s version %s (%s)' % (___NAME, ___VER, ___BUILT)

def publish_server_advertisements(server_on, channel, message):
    while server_on[0]:
        channel.basic_publish(exchange='direct_logs', 
                              routing_key=common.make_key_server_advert(), 
                              body=message)
        sleep(2)

def stop_server(channel, message):
    channel.basic_publish(exchange='direct_logs', 
                          routing_key=common.make_key_server_stop(), 
                          body=message)

# Main function ---------------------------------------------------------------
if __name__ == '__main__':
    # Parsing arguments
    parser = ArgumentParser()
    parser.add_argument('-H','--host', \
                        help='Addres of the RabitMQ server, '\
                        'defaults to %s' % common.DEFAULT_SERVER_INET_ADDR, \
                        default=common.DEFAULT_SERVER_INET_ADDR)
    parser.add_argument('-p','--port', \
                        help='Port of the RabitMQ server, '\
                        'defaults to %d' % common.DEFAULT_SERVER_PORT, \
                        default=common.DEFAULT_SERVER_PORT)
    parser.add_argument('-n','--name', \
                        help='Server name.',\
                        required=True)
    args = parser.parse_args()

    # Connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=args.host, port=args.port))
    channel = connection.channel()
    channel.exchange_declare(exchange='direct_logs', type='direct')

    # Client connections
    clients = Clients(channel, args.name)
    
    # Server advertisements
    server_on = [True]
    t = threading.Thread(target=publish_server_advertisements,
                         args=(server_on, channel, args.name))
    t.setDaemon(True)
    t.start()
    LOG.debug('Started server advertising.')
    
    # Dict of games
    game_list = GameList(channel, args, clients)
    
    try:
        while True:
            channel.start_consuming()
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating server ...')
    
    server_on[0] = False
    stop_server(channel, args.name)
    LOG.debug('Stopped advertising.')
    
    # Send message to all games control queues to stop consuming.
    for game in game_list.games.values():
        channel.basic_publish(exchange='direct_logs',
                              routing_key=game.control_queue,
                              body='')
