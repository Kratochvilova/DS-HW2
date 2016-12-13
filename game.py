# -*- coding: utf-8 -*-
"""
Created on Sat Dec 10 12:54:37 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import random
import threading
import logging
import pika
# Custom imports --------------------------------------------------------------
import serverlib
import common
from common import send_message
# Logging ---------------------------------------------------------------------
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

        # Players
        self.client_queues = {}

        self.players = set()
        self.spectators = set()

        self.owner = owner
        self.players.add(self.owner)

        self.fields = {}
        self.player_hits = {}

        self.on_turn = None
        self.player_order = []

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
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host, port=self.port)
        )
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='direct_logs', type='direct')

        # Routing keys
        self.key_game = common.make_key_game(self.server_name, self.name)
        self.key_events = common.make_key_game_events(self.server_name,
                                                      self.name)
        self.key_adverts = common.make_key_game_advert(self.server_name)

        # Game queue
        self.game_queue =\
            self.channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.game_queue,
                                routing_key=self.key_game)
        self.channel.basic_consume(self.reply_request,
                                   queue=self.game_queue,
                                   no_ack=True)

        # Spectator queue
        self.spectator_queue =\
            self.channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.spectator_queue,
                                routing_key=self.spectator_queue)

        # Control queue for quiting consuming
        self.control_queue =\
            self.channel.queue_declare(exclusive=True).method.queue
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

    def check_ships(self, ships):
        '''Check if list of ships is correct.
        @param ships: list of ships
        @return True if list ok, else False
        '''
        if len(ships) != self.ship_number:
            return False

        for ship in ships:
            ship_position = ship.split(common.FIELD_SEP)
            if int(ship_position[0]) < 0 or int(ship_position[1]) < 0 or\
                int(ship_position[0]) > self.height or\
                int(ship_position[1]) > self.width:
                return False

        return True

    def add_ships(self, player, ships):
        '''Add ships to player field.
        @param player: player name
        @param ships: list of tuples (row, column)
        '''
        self.fields[player] = common.Field(self.width, self.height)
        for ship in ships:
            ship_position = ship.split(common.FIELD_SEP)
            self.fields[player].add_item(int(ship_position[0]),
                                         int(ship_position[1]),
                                         common.FIELD_SHIP)

    def get_field(self, player):
        '''Get field information for specific player.
        @param player: player
        '''
        result = []
        if player not in self.fields:
            return result
        return self.fields[player].get_all_items()

    def get_hits(self, player):
        '''Get hit information for specific player.
        @param player: player
        '''
        result = []
        if player not in self.player_hits:
            return result
        return self.player_hits[player]

    def check_sink_ship(self, field, row, column, searched, hit_ships):
        '''Check recursively if the ship sunk.
        @param field: Field
        @param row: row
        @param column: column
        @param searched: list of searched positions
        @hit_ships: list of positions where the ship has been hit
        @return None if found position where the ship is still unhit, list of
        hit_ships otherwise
        '''
        searched.append((row, column))
        if field.get_item(row, column) == common.FIELD_SHIP:
            return None
        if field.get_item(row, column) == common.FIELD_HIT_SHIP:
            hit_ships.append((row, column))
            if (row-1, column) not in searched:
                result = self.check_sink_ship(field, row-1, column,
                                              searched, hit_ships)
                if result is None:
                    return None
            if (row+1, column) not in searched:
                result = self.check_sink_ship(field, row+1, column,
                                              searched, hit_ships)
                if result is None:
                    return None
            if (row, column-1) not in searched:
                result = self.check_sink_ship(field, row, column-1,
                                              searched, hit_ships)
                if result is None:
                    return None
            if (row, column+1) not in searched:
                result = self.check_sink_ship(field, row, column+1,
                                              searched, hit_ships)
                if result is None:
                    return None

        return hit_ships

    def sink_ship(self, field, hit_ships):
        '''Make ship sinked.
        @param field: Field
        @param hit_ships: list of positions where the ship has been hit
        @return list of strings encoding positions where the ship has been hit
        '''
        # Make ship sinked and make strings
        hit_ships_string = []
        for ship in hit_ships:
            hit_ships_string.append(
                str(ship[0]) + common.FIELD_SEP + str(ship[1]))
            field.change_item(ship[0], ship[1], common.FIELD_HIT_SHIP,
                              common.FIELD_SINK_SHIP)
        return hit_ships_string

    def count_player_ships(self, player):
        '''Count ships that are not hit.
        @param player: name of player
        @return number of ships
        '''
        ships = self.fields[player].get_all_items(common.FIELD_SHIP)
        return len(ships)

    def check_end_game(self):
        '''Check end-game condition
        @return True if game ended, else False
        '''
        number_unfinished_players = 0
        for field in self.fields.values():
            if field.get_all_items(common.FIELD_SHIP) != []:
                number_unfinished_players += 1
        return number_unfinished_players <= 1

    def player_disconnected(self, player):
        '''Actions on player leaving or disconnecting from the game
        @param player: name of player
        '''
        # Remove player's client queue
        try:
            del self.client_queues[player]
        except KeyError:
            pass

        # If noone is in the game
        if len(self.client_queues.keys()) == 0:
            # Quit game
            self.channel.stop_consuming()
            self.game_list.remove_game(self.name)

        # Else we might need to change the owner
        elif self.owner == player:
            new_owner = random.choice(self.client_queues.keys())
            self.owner = new_owner
            # Send event that owner changed
            msg = serverlib.make_e_new_owner(new_owner)
            send_message(self.channel, msg, self.key_events)

    def player_left(self, player):
        '''Actions on player leaving from the game
        @param player: name of player
        '''
        try:
            self.players.remove(player)
        except KeyError:
            pass
        try:
            del self.fields[player]
        except KeyError:
            pass
        try:
            del self.player_hits[player]
        except KeyError:
            pass
        try:
            self.spectators.remove(player)
        except KeyError:
            pass

        # Send event that player left
        msg = serverlib.make_e_player_left(player)
        send_message(self.channel, msg, self.key_events)

    def change_turn(self):
        '''Change turn to next player and send event.
        '''
        next_index = self.player_order.index(self.on_turn) + 1
        if next_index >= len(self.player_order):
            next_index = 0
        self.on_turn = self.player_order[next_index]

        # Send on turn event
        msg = serverlib.make_e_on_turn(self.on_turn)
        send_message(self.channel, msg, self.key_events)

    def process_request(self, msg_parts):
        '''Process game request.
        @param msg_parts: parsed message
        @return String, response
        '''
        # Disconnect request
        if msg_parts[0] == common.REQ_DISCONNECT:
            self.player_disconnected(msg_parts[1])
            return serverlib.make_rsp_disconnected()

        # Leave game request
        if msg_parts[0] == common.REQ_LEAVE_GAME:
            if len(msg_parts) != 2:
                return serverlib.make_rsp_invalid_request()

            self.player_disconnected(msg_parts[1])
            self.player_left(msg_parts[1])
            return serverlib.make_rsp_game_left()

        # Get dimensions request
        if msg_parts[0] == common.REQ_GET_DIMENSIONS:
            return serverlib.make_rsp_dimensions(self.width, self.height,
                                                 self.ship_number)

        # Get players request
        if msg_parts[0] == common.REQ_GET_PLAYERS:
            return serverlib.make_rsp_list_players(list(self.players))

        # Get players ready request
        if msg_parts[0] == common.REQ_GET_PLAYERS_READY:
            players_ready = [p for p in self.fields if self.fields[p] != {}]
            return serverlib.make_rsp_list_players_ready(players_ready)

        # Get owner request
        if msg_parts[0] == common.REQ_GET_OWNER:
            return serverlib.make_rsp_owner(self.owner)

        # Get turn request
        if msg_parts[0] == common.REQ_GET_TURN:
            return serverlib.make_rsp_turn(self.on_turn)

        # Get field request
        if msg_parts[0] == common.REQ_GET_FIELD:
            return serverlib.make_rsp_field(self.get_field(msg_parts[1]))

        # Get hits request
        if msg_parts[0] == common.REQ_GET_HITS:
            return serverlib.make_rsp_hits(self.get_hits(msg_parts[1]))

        # Get all fields request
        if msg_parts[0] == common.REQ_GET_ALL_FIELDS:
            if msg_parts[1] not in self.spectators:
                return serverlib.make_rsp_permission_denied()

            all_fields = []
            for player in self.players:
                items = self.fields[player].get_all_items()
                all_fields += [player] + items
            return serverlib.make_rsp_all_fields(all_fields)

        if msg_parts[0] == common.REQ_GET_SPECTATOR:
            if msg_parts[1] in self.spectators:
                return serverlib.make_rsp_spectator(1)
            return serverlib.make_rsp_spectator(0)

        if msg_parts[0] == common.REQ_GET_SPECTATOR_QUEUE:
            if msg_parts[1] not in self.spectators:
                return serverlib.make_rsp_permission_denied()
            return serverlib.make_rsp_spectator_queue(self.spectator_queue)

        # Set ready request
        if msg_parts[0] == common.REQ_SET_READY:
            if not self.check_ships(msg_parts[2:]):
                return serverlib.make_rsp_ships_incorrect()

            self.add_ships(msg_parts[1], msg_parts[2:])
            # Send event that player is ready
            msg = serverlib.make_e_player_ready(msg_parts[1])
            send_message(self.channel, msg, self.key_events)
            return serverlib.make_rsp_ready()

        # Kick out request
        if msg_parts[0] == common.REQ_KICK_OUT:
            if msg_parts[1] != self.owner or\
                msg_parts[2] in self.client_queues:
                return serverlib.make_rsp_wont_kick()
            self.player_left(msg_parts[2])
            return serverlib.make_rsp_ok()

        # Start game request
        if msg_parts[0] == common.REQ_START_GAME:
            if not self.players.issubset(set(self.fields.keys())):
                return serverlib.make_rsp_not_all_ready()

            self.state = 'closed'
            for player in self.players:
                self.player_hits[player] = []

            # Determine player order
            self.on_turn = self.owner
            self.player_order.append(self.owner)
            not_sorted = list(self.players)
            not_sorted.remove(self.owner)
            while len(not_sorted) > 0:
                random_player = random.choice(not_sorted)
                self.player_order.append(random_player)
                not_sorted.remove(random_player)

            # Send advert about game start
            msg = serverlib.make_e_game_close(self.name)
            send_message(self.channel, msg, self.key_adverts)

            # Send event that game starts
            msg = serverlib.make_e_game_starts(self.on_turn)
            send_message(self.channel, msg, self.key_events)

            return serverlib.make_rsp_ok()

        # Shoot request
        if msg_parts[0] == common.REQ_SHOOT:
            if msg_parts[1] != self.on_turn:
                return serverlib.make_rsp_not_on_turn()

            # Get shot item
            item = self.fields[msg_parts[2]].get_item(int(msg_parts[3]),
                                                      int(msg_parts[4]))
            if item is None:
                item = common.FIELD_WATER

            # Update player_hits
            self.player_hits[msg_parts[1]].append(common.FIELD_SEP.join(
                [msg_parts[2], msg_parts[3], msg_parts[4], item]))

            # If miss
            if item == common.FIELD_WATER:
                self.change_turn()
                return serverlib.make_rsp_miss(*msg_parts[1:])

            # If hit
            self.fields[msg_parts[2]].change_item(
                int(msg_parts[3]), int(msg_parts[4]),
                common.FIELD_SHIP, common.FIELD_HIT_SHIP
            )

            # Notify the hit player
            msg = serverlib.make_e_hit(*msg_parts[1:])
            send_message(self.channel, msg, self.client_queues[msg_parts[2]])

            # Send secret event for spectators
            send_message(self.channel, msg, self.spectator_queue)

            ships = self.check_sink_ship(self.fields[msg_parts[2]],
                                         int(msg_parts[3]),
                                         int(msg_parts[4]), [], [])
            # If ship sinked
            if ships is not None:
                ships_string = self.sink_ship(self.fields[msg_parts[2]], ships)
                msg = serverlib.make_e_sink(msg_parts[2], ships_string)
                send_message(self.channel, msg, self.key_events)

                # If player lost
                if self.count_player_ships(msg_parts[2]) == 0:
                    self.players.remove(msg_parts[2])
                    self.spectators.add(msg_parts[2])
                    msg = serverlib.make_e_player_end(msg_parts[2])
                    send_message(self.channel, msg, self.key_events)

                    # Adjust turn and player order
                    if self.on_turn == msg_parts[2]:
                        i = self.player_order.index(self.on_turn) - 1
                        if i < 0:
                            i = len(self.player_order)
                        self.on_turn = self.player_order[i]
                        del self.player_order[self.player_order.index(
                            msg_parts[2])]

                    # If end of game
                    if self.check_end_game():
                        msg = serverlib.make_e_game_end(self.name)
                        send_message(self.channel, msg, self.key_events)

            self.change_turn()
            return serverlib.make_rsp_hit(*msg_parts[1:])

        # Restart session request
        if msg_parts[0] == common.REQ_RESTART_SESSION:
            if self.check_end_game():
                # Send restart session event
                msg = serverlib.make_e_game_restart()
                send_message(self.channel, msg, self.key_events)

                # Restart game
                self.fields = {}
                self.on_turn = None
                self.player_hits = {}
                self.player_order = []

                return serverlib.make_rsp_ok()

    def reply_request(self, ch, method, properties, body):
        '''Reply to game request.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Processing game request.')
        LOG.debug('Received message: %s', body)
        msg_parts = body.split(common.SEP)
        response = self.process_request(msg_parts)

        # Sending response
        ch.basic_publish(exchange='direct_logs',
                         routing_key=properties.reply_to,
                         body=response)
        LOG.debug('Sent response to client: %s', response)
