#!/usr/bin/python
"""
Created on Thu Dec  1 15:41:34 2016

@author: pavla kratochvilova
"""
# Imports----------------------------------------------------------------------
from argparse import ArgumentParser
import threading
import Queue
import logging
import pika
# Custom imports --------------------------------------------------------------
import common
from windows import thread_printing
from windows.server import ServerWindow
from windows.lobby import LobbyWindow
from windows.game import GameWindow
# Setup Python logging --------------------------------------------------------
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
# Constants -------------------------------------------------------------------
___NAME = 'Battleship Game Client'
___VER = '0.1.0.0'
___DESC = 'Battleship Game Client'
___BUILT = '2016-11-10'
# Functions -------------------------------------------------------------------
def __info():
    return '%s version %s (%s)' % (___NAME, ___VER, ___BUILT)

def window_control(events, server_window, lobby_window, game_window):
    '''Get events from queue and show windows accordingly. In case of close
    event, all windows are closed, and disconnect request is sent if necessary.
    @param events: Queue of events
    @param server_window: ServerWindow
    @param lobby_window: LobbyWindow
    @param game_window: GameWindow
    '''
    while True:
        try:
            event, old_thread, arguments = events.get(timeout=5)
            LOG.debug('Got window event: %s', event)
            if old_thread is not None:
                old_thread.join()
            # Showing windows
            if event == 'server':
                server_window.show()
            elif event == 'lobby':
                lobby_window.show(arguments)
            elif event == 'game':
                game_window.show(arguments)
            else:
                LOG.debug('Unknown event for window control: %s', event)
        except Queue.Empty:
            pass

# Main method -----------------------------------------------------------------
if __name__ == '__main__':
    # Parsing arguments
    parser = ArgumentParser()
    parser.add_argument(
        '-H', '--host',
        help='Addres of the RabitMQ server, defaults to %s' %
        common.DEFAULT_SERVER_INET_ADDR,
        default=common.DEFAULT_SERVER_INET_ADDR
    )
    parser.add_argument(
        '-p', '--port',
        help='Port of the RabitMQ server, defaults to %d' %
        common.DEFAULT_SERVER_PORT,
        default=common.DEFAULT_SERVER_PORT
    )
    args = parser.parse_args()

    # Connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=args.host, port=args.port))
    channel = connection.channel()
    channel.exchange_declare(exchange='direct_logs', type='direct')

    # Queues
    client_queue = channel.queue_declare(exclusive=True).method.queue
    server_advertisements = channel.queue_declare(exclusive=True).method.queue
    game_advertisements = channel.queue_declare(exclusive=True).method.queue
    events_queue = channel.queue_declare(exclusive=True).method.queue

    # Queue for window control
    events = Queue.Queue()

    # Application windows
    server_window = ServerWindow(channel, server_advertisements,
                                 client_queue, events)
    lobby_window = LobbyWindow(channel, game_advertisements,
                               client_queue, events, server_window)
    game_window = GameWindow(channel, client_queue, events_queue, events,
                             server_window)

    server_window.lobby_window = lobby_window
    lobby_window.game_window = game_window
    lobby_window.server_window = server_window
    game_window.lobby_window = lobby_window

    # Controling which windows are shown and which are hidden
    t_control = threading.Thread(target=window_control,
                                 args=(events, server_window,
                                       lobby_window, game_window),
                                 name='Window control')
    t_control.setDaemon(True)
    t_control.start()

    #thread_printing()

    try:
        server_window.root.mainloop()
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating client ...')
