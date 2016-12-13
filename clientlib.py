# -*- coding: utf-8 -*-
"""
Created on Tue Dec 13 11:59:38 2016

@author: pavla
"""
# Imports ---------------------------------------------------------------------
import common
import functools
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Request functions -----------------------------------------------------------
def do_str(f):
    @functools.wraps(f)
    def wrapped(*args):
        return common.SEP.join(f(*args))
    return wrapped

@do_str
def make_req_connect(client_name):
    return common.REQ_CONNECT, client_name

@do_str
def make_req_disconnect(client_name):
    return common.REQ_DISCONNECT, client_name

@do_str
def make_req_list_opened():
    return common.REQ_LIST_OPENED,

@do_str
def make_req_list_closed():
    return common.REQ_LIST_CLOSED,

@do_str
def make_req_create_game(game_name, client_name, width, height):
    return (common.REQ_CREATE_GAME, game_name, client_name,
            str(width), str(height))

@do_str
def make_req_join_game(game_name, client_name):
    return common.REQ_JOIN_GAME, game_name, client_name

@do_str
def make_req_spectate_game(game_name, client_name):
    return common.REQ_SPECTATE_GAME, game_name, client_name

@do_str
def make_req_leave_game(client_name):
    return common.REQ_LEAVE_GAME, client_name

@do_str
def make_req_get_dimensions():
    return common.REQ_GET_DIMENSIONS,

@do_str
def make_req_get_players():
    return common.REQ_GET_PLAYERS,

@do_str
def make_req_get_players_ready():
    return common.REQ_GET_PLAYERS_READY,

@do_str
def make_req_get_owner():
    return common.REQ_GET_OWNER,

@do_str
def make_req_get_turn():
    return common.REQ_GET_TURN,

@do_str
def make_req_get_field(client_name):
    return common.REQ_GET_FIELD, client_name

@do_str
def make_req_get_all_fields(client_name):
    return common.REQ_GET_ALL_FIELDS, client_name

@do_str
def make_req_get_spectator_queue(client_name):
    return common.REQ_GET_SPECTATOR_QUEUE, client_name

@do_str
def make_req_get_hits(client_name):
    return common.REQ_GET_HITS, client_name

@do_str
def make_req_set_ready(client_name, ships):
    return [common.REQ_SET_READY, client_name] + ships

@do_str
def make_req_start_game(client_name):
    return common.REQ_START_GAME, client_name

@do_str
def make_req_shoot(client_name, opponent_name, row, column):
    return common.REQ_SHOOT, client_name, opponent_name, str(row), str(column)

@do_str
def make_req_restart_session():
    return common.REQ_RESTART_SESSION,
