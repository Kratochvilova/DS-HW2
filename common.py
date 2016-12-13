#!/usr/bin/python
"""
Created on Thu Dec  1 21:38:50 2016

@author: pavla kratochvilova
"""
# Imports ---------------------------------------------------------------------
import functools
import logging
import pika
# Logging ---------------------------------------------------------------------
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Connection related constants ------------------------------------------------
DEFAULT_SERVER_PORT = 5672
DEFAULT_SERVER_INET_ADDR = '127.0.0.1'

# Routing keys ----------------------------------------------------------------
KEY_SERVER_ADVERT = 'server_advert'
KEY_SERVER_STOP = 'server_stop'
KEY_GAMES = 'games'
KEY_GAME_ADVERT = 'game advert'
KEY_GAME_EVENTS = 'game events'

# Routing keys functions ------------------------------------------------------
def do_str(func):
    @functools.wraps(func)
    def wrapped(*args):
        return SEP.join(func(*args))
    return wrapped

@do_str
def make_key_server_advert():
    return KEY_SERVER_ADVERT,

@do_str
def make_key_server_stop():
    return KEY_SERVER_STOP,

@do_str
def make_key_server(server_name):
    return server_name,

@do_str
def make_key_games(server_name):
    return server_name, KEY_GAMES

@do_str
def make_key_game_advert(server_name):
    return server_name, KEY_GAME_ADVERT

@do_str
def make_key_game(server_name, game_name):
    return server_name, game_name

@do_str
def make_key_game_events(server_name, game_name):
    return server_name, game_name, KEY_GAME_EVENTS

# Connecting ------------------------------------------------------------------
# Requests
REQ_CONNECT = 'req connect'
REQ_DISCONNECT = 'req disconnect'
# Responses
RSP_CONNECTED = 'rsp connected'
RSP_DISCONNECTED = 'rsp disconnected'
RSP_USERNAME_TAKEN = 'rsp username taken'

# Game list -------------------------------------------------------------------
# Requests
REQ_LIST_OPENED = 'req list opened'
REQ_LIST_CLOSED = 'req list closed'
REQ_CREATE_GAME = 'req create game'
REQ_JOIN_GAME = 'req join game'
REQ_SPECTATE_GAME = 'req spectate game'
# Responses
RSP_LIST_OPENED = 'rsp list opened'
RSP_LIST_CLOSED = 'rsp list closed'
RSP_GAME_ENTERED = 'rsp game entered'
RSP_GAME_SPECTATE = 'rsp game spectate'
RSP_NAME_EXISTS = 'rsp name exists'
RSP_NAME_DOESNT_EXIST = 'rsp name doesnt exist'

# Game ------------------------------------------------------------------------
# Requests
REQ_LEAVE_GAME = 'leave game'
REQ_GET_DIMENSIONS = 'get dimensions'
REQ_GET_PLAYERS = 'get players'
REQ_GET_PLAYERS_READY = 'get players ready'
REQ_GET_OWNER = 'get owner'
REQ_GET_TURN = 'get turn'
REQ_GET_FIELD = 'get field'
REQ_GET_ALL_FIELDS = 'get all fields'
REQ_GET_SPECTATOR_QUEUE = 'get spectator queue'
REQ_GET_HITS = 'get hits'
REQ_SET_READY = 'set ready'
REQ_KICK_OUT = 'kick out'
REQ_START_GAME = 'start game'
REQ_SHOOT = 'shoot'
REQ_RESTART_SESSION = 'restart session'
# Responses
RSP_GAME_LEFT = 'game left'
RSP_DIMENSIONS = 'dimensions'
RSP_LIST_PLAYERS = 'list players'
RSP_LIST_PLAYERS_READY = 'list players ready'
RSP_OWNER = 'owner'
RSP_TURN = 'turn'
RSP_FIELD = 'field'
RSP_ALL_FIELDS = 'all fields'
RSP_SPECTATOR_QUEUE = 'spectator queue'
RSP_HITS = 'hits'
RSP_READY = 'ready'
RSP_WONT_KICK = 'wont kick'
RSP_SHIPS_INCORRECT = 'ships incorrect'
RSP_NOT_ALL_READY = 'not all ready'
RSP_NOT_ON_TURN = 'not on turn'
RSP_HIT = 'hit'
RSP_MISS = 'miss'

# Game events -----------------------------------------------------------------
E_NEW_PLAYER = 'new player'
E_PLAYER_LEFT = 'player left'
E_NEW_OWNER = 'new owner'
E_PLAYER_READY = 'player ready'
E_GAME_STARTS = 'game starts'
E_ON_TURN = 'on turn'
E_HIT = 'hit'
E_SINK = 'sink'
E_PLAYER_END = 'player end'
E_GAME_RESTART = 'game restart'

# Game advert events ----------------------------------------------------------
E_GAME_OPEN = 'game open'
E_GAME_CLOSE = 'game close'
E_GAME_END = 'game end'

# Common responses ------------------------------------------------------------
RSP_OK = 'ok'
RSP_PERMISSION_DENIED = 'permission denied'
RSP_INVALID_REQUEST = 'invalid request'

# Separator -------------------------------------------------------------------
SEP = '\n'
FIELD_SEP = '\t'

# Field item types ------------------------------------------------------------
FIELD_WATER = 'water'
FIELD_SHIP = 'ship'
FIELD_HIT_SHIP = 'hit_ship'
FIELD_SINK_SHIP = 'sink ship'
FIELD_UNKNOWN = 'unknown'

# Common functions ------------------------------------------------------------
def send_message(channel, message, routing_key, reply_to=None):
    '''Compose message and routing key, and send request.
    @param channel: pika communication channel
    @param message: message
    @param routing_key: routing key
    @param reply_to: queue expecting reply
    '''
    properties = pika.BasicProperties(reply_to=reply_to)
    channel.basic_publish(exchange='direct_logs', routing_key=routing_key,
                          properties=properties, body=message)
    LOG.debug('Sent message to "%s": "%s"', routing_key, message)

# Common classes --------------------------------------------------------------
class Field(object):
    '''Field class.
    '''
    def __init__(self, width, height):
        '''Initialize - field dimensions and dict of items.
        @param width: width
        @param height: height
        '''
        self.width = width
        self.height = height
        self.field_dict = {}

    def add_item(self, row, column, item):
        '''Add item to the dict.
        @param row: row
        @param column: column
        @param item: item
        @return False if (row, column) out of field, else True
        '''
        if row < 0 or row > self.height or column < 0 or column > self.width:
            return False

        self.field_dict[(row, column)] = item
        return True

    def remove_item(self, row, column):
        '''Remove item from the dict.
        @param row: row
        @param column: column
        @return False if (row, column) not in field, else True
        '''
        if row < 0 or row > self.height or column < 0 or column > self.width:
            return False

        if (row, column) not in self.field_dict:
            return False

        del self.field_dict[(row, column)]
        return True

    def change_item(self, row, column, old, new):
        '''Change item.
        @param row: row
        @param column: column
        @param old: old item
        @param new: new item
        '''
        if row < 0 or row > self.height or column < 0 or column > self.width:
            return False
        if (row, column) not in self.field_dict:
            return False
        if self.field_dict[(row, column)] != old:
            return False

        self.field_dict[(row, column)] = new
        return True

    def get_item(self, row, column):
        '''Gets item by position.
        param row: row
        @param column: column
        @return String, item
        '''
        if row < 0 or row > self.height or column < 0 or column > self.width:
            return None

        if (row, column) not in self.field_dict:
            return None

        return self.field_dict[(row, column)]

    def get_all_items(self, item=None):
        '''Gets all positions of item.
        @param item: item
        @return list, positions
        '''
        result = []
        for key, value in self.field_dict.items():
            if item is None or value == item:
                result.append(
                    FIELD_SEP.join([str(key[0]), str(key[1]), value])
                )

        return result
