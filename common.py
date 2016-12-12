#!/usr/bin/python
"""
Created on Thu Dec  1 21:38:50 2016

@author: pavla kratochvilova
"""
# Imports ---------------------------------------------------------------------
import pika
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Connection related constants ------------------------------------------------
DEFAULT_SERVER_PORT = 5672
DEFAULT_SERVER_INET_ADDR = '127.0.0.1'

# Routing keys ----------------------------------------------------------------
KEY_SERVER_ADVERT = 'server_advert'
KEY_SERVER_STOP = 'server_stop'
KEY_GAMES = 'games' # server_name + SEP + KEY_GAMES
KEY_GAME_OPEN = 'game open' # server_name + SEP + KEY_GAME_OPEN
KEY_GAME_CLOSE = 'game close' # server_name + SEP + KEY_GAME_CLOSE
KEY_GAME_END = 'game end' # server_name + SEP + KEY_GAME_END
KEY_GAME_EVENTS = 'game events' # server_name + SEP + game_name + SEP + 
                                # KEY_GAME_EVENTS

# Connecting ------------------------------------------------------------------
# Requests
REQ_CONNECT = 'connect'
REQ_DISCONNECT = 'disconnect'
# Responses
RSP_CONNECTED = 'connected'
RSP_DISCONNECTED = 'disconnected'
RSP_USERNAME_TAKEN = 'username taken'
RSP_USERNAME_DOESNT_EXIST = 'username doesnt exist'

# Game list -------------------------------------------------------------------
# Requests
REQ_GET_LIST_OPENED = 'get list opened'
REQ_GET_LIST_CLOSED = 'get list closed'
REQ_CREATE_GAME = 'create game'
REQ_JOIN_GAME = 'join game'
REQ_SPECTATE_GAME = 'spectate game'
# Responses
RSP_LIST_OPENED = 'list opened'
RSP_LIST_CLOSED = 'list closed'
RSP_GAME_ENTERED = 'game entered'
RSP_INVALID_USERNAME = 'invalid username'
RSP_PERMISSION_DENIED = 'permission denied'
RSP_NAME_EXISTS = 'name exists'
RSP_NAME_DOESNT_EXIST = 'name doesnt exist'

# Game ------------------------------------------------------------------------
# Requests
REQ_LEAVE_GAME = 'leave game'
REQ_GET_DIMENSIONS = 'get dimensions'
REQ_GET_PLAYERS = 'get players'
REQ_GET_PLAYERS_READY = 'get players ready'
REQ_GET_OWNER = 'get owner'
REQ_GET_TURN = 'get turn'
REQ_GET_FIELD = 'get field'
REQ_GET_HITS = 'get hits'
REQ_SET_READY = 'set ready'
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
RSP_HITS = 'hits'
RSP_READY = 'ready'
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
E_END_GAME = 'end game'
E_SESSION_RESTARTS = 'session restarts'

# Common responses ------------------------------------------------------------
RSP_OK = 'ok'
RSP_INVALID_REQUEST = 'invalid request'

# Separator -------------------------------------------------------------------
SEP = ':'
FIELD_SEP = ','

# Field item types ------------------------------------------------------------
FIELD_WATER = 'water'
FIELD_SHIP = 'ship'
FIELD_HIT_SHIP = 'hit_ship'
FIELD_SINK_SHIP = 'sink ship'
FIELD_UNKNOWN = 'unknown'

# Common functions ------------------------------------------------------------
def send_message(channel, msg_args, routing_args, reply_to=None):
    '''Compose message and routing key, and send request.
    @param channel: pika communication channel
    @param msg_args: message arguments
    @param routing_key_args: routing key arguments
    @param reply_to: queue expecting reply
    '''
    message = SEP.join(msg_args)
    routing_key = SEP.join(routing_args)
    properties = pika.BasicProperties(reply_to = reply_to)
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
                result.append(FIELD_SEP.join([str(key[0]), str(key[1]),value]))
        
        return result
