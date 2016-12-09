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
REQ_CONNECT = '1'
REQ_DISCONNECT = '2'
MSG_SEPARATOR = ':'
# Responses
RSP_OK = '0'
RSP_USERNAME_TAKEN = '1'
RSP_CLIENT_NOT_CONNECTED = '2'
RSP_INVALID_REQUEST = '3'
# Game list -------------------------------------------------------------------
# Requests
REQ_GET_LIST_OPENED = '0'
REQ_GET_LIST_CLOSED = '1'
REQ_CREATE_GAME = '2'
REQ_JOIN_GAME = '3'
MSG_SEPARATOR = ':'
# Responses
RSP_LIST_OPENED = '0'
RSP_LIST_CLOSED = '1'
RSP_OK = '2'
RSP_NAME_EXISTS = '3'
RSP_INVALID_USERNAME = '4'
RSP_PERMISSION_DENIED = '5'
RSP_INVALID_REQUEST = '6'
