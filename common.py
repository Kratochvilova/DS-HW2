#!/usr/bin/python
"""
Created on Thu Dec  1 21:38:50 2016

@author: pavla kratochvilova
"""
# Connection related constants ------------------------------------------------
DEFAULT_SERVER_PORT = 5672
DEFAULT_SERVER_INET_ADDR = '127.0.0.1'

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
RSP_NAME_EXISTS = 'name exists'
RSP_INVALID_USERNAME = 'invalid username'
RSP_PERMISSION_DENIED = 'permission denied'

# Common responses ------------------------------------------------------------
RSP_OK = 'ok'
RSP_INVALID_REQUEST = 'invalid request'
MSG_SEPARATOR = ':'
