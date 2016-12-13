# -*- coding: utf-8 -*-
"""
Created on Tue Dec 13 14:51:28 2016

@author: pavla
"""
# Imports ---------------------------------------------------------------------
import functools
import logging
# Custom imports --------------------------------------------------------------
import common
# Logging ---------------------------------------------------------------------
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Response functions ----------------------------------------------------------
def do_str(func):
    @functools.wraps(func)
    def wrapped(*args):
        return common.SEP.join(func(*args))
    return wrapped

@do_str
def make_rsp_connected(server_name, client_name):
    return common.RSP_CONNECTED, server_name, client_name

@do_str
def make_rsp_disconnected():
    return common.RSP_DISCONNECTED,

@do_str
def make_rsp_username_taken():
    return common.RSP_USERNAME_TAKEN,

@do_str
def make_rsp_list_opened(game_names):
    return [common.RSP_LIST_OPENED] + game_names

@do_str
def make_rsp_list_closed(game_names):
    return [common.RSP_LIST_CLOSED] + game_names

@do_str
def make_rsp_game_entered(game_name, is_owner):
    return common.RSP_GAME_ENTERED, game_name, str(is_owner)

@do_str
def make_rsp_game_spectate(game_name, is_owner, spectator_queue):
    return common.RSP_GAME_SPECTATE, game_name, str(is_owner), spectator_queue

@do_str
def make_rsp_name_exists():
    return common.RSP_NAME_EXISTS,

@do_str
def make_rsp_name_doesnt_exist():
    return common.RSP_NAME_DOESNT_EXIST,

@do_str
def make_rsp_game_left():
    return common.RSP_GAME_LEFT,

@do_str
def make_rsp_dimensions(width, height, ship_number):
    return common.RSP_DIMENSIONS, str(width), str(height), str(ship_number)

@do_str
def make_rsp_list_players(players):
    return [common.RSP_LIST_PLAYERS] + players

@do_str
def make_rsp_list_players_ready(players_ready):
    return [common.RSP_LIST_PLAYERS_READY] + players_ready

@do_str
def make_rsp_owner(owner):
    return common.RSP_OWNER, owner

@do_str
def make_rsp_turn(on_turn=None):
    if on_turn is None:
        return common.RSP_TURN,
    else:
        return common.RSP_TURN, on_turn

@do_str
def make_rsp_field(field):
    return [common.RSP_FIELD] + field

@do_str
def make_rsp_all_fields(all_fields):
    return [common.RSP_ALL_FIELDS] + all_fields

@do_str
def make_rsp_hits(hits):
    return [common.RSP_HITS] + hits

@do_str
def make_rsp_spectator_queue(spectator_queue):
    return common.RSP_SPECTATOR_QUEUE, spectator_queue

@do_str
def make_rsp_ready():
    return common.RSP_READY,

@do_str
def make_rsp_wont_kick():
    return common.RSP_WONT_KICK,

@do_str
def make_rsp_ships_incorrect():
    return common.RSP_SHIPS_INCORRECT,

@do_str
def make_rsp_not_all_ready():
    return common.RSP_NOT_ALL_READY,

@do_str
def make_rsp_not_on_turn():
    return common.RSP_NOT_ON_TURN,

@do_str
def make_rsp_hit(client_name, opponent_name, row, column):
    return common.RSP_HIT, client_name, opponent_name, str(row), str(column)

@do_str
def make_rsp_miss(client_name, opponent_name, row, column):
    return common.RSP_MISS, client_name, opponent_name, str(row), str(column)

@do_str
def make_rsp_ok():
    return common.RSP_OK,

@do_str
def make_rsp_permission_denied():
    return common.RSP_PERMISSION_DENIED,

@do_str
def make_rsp_invalid_request():
    return common.RSP_INVALID_REQUEST,

# Game event functions --------------------------------------------------------
@do_str
def make_e_new_player(player):
    return common.E_NEW_PLAYER, player

@do_str
def make_e_player_left(player):
    return common.E_PLAYER_LEFT, player

@do_str
def make_e_new_owner(player):
    return common.E_NEW_OWNER, player

@do_str
def make_e_player_ready(player):
    return common.E_PLAYER_READY, player

@do_str
def make_e_game_starts(on_turn):
    return common.E_GAME_STARTS, on_turn

@do_str
def make_e_on_turn(on_turn):
    return common.E_ON_TURN, on_turn

@do_str
def make_e_hit(client_name, opponent_name, row, column):
    return common.E_HIT, client_name, opponent_name, str(row), str(column)

@do_str
def make_e_sink(player, ship_parts):
    return [common.E_SINK, player] + ship_parts

@do_str
def make_e_player_end(player):
    return common.E_PLAYER_END, player

@do_str
def make_e_game_restart():
    return common.E_GAME_RESTART,

@do_str
def make_e_game_open(game_name):
    return common.E_GAME_OPEN, game_name

@do_str
def make_e_game_close(game_name):
    return common.E_GAME_CLOSE, game_name

@do_str
def make_e_game_end(game_name):
    return common.E_GAME_END, game_name
