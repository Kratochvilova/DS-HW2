#!/usr/bin/python
"""
Created on Thu Dec  1 15:41:34 2016

@author: pavla kratochvilova
"""
# Setup Python logging --------------------------------------------------------
import logging
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
LOG = logging.getLogger()
# Imports----------------------------------------------------------------------
import common
from windows import stop_consuming
from windows.server import ServerWindow
from windows.lobby import LobbyWindow
from argparse import ArgumentParser
import threading
import pika
import Queue
import Tkinter
from time import sleep
# Constants -------------------------------------------------------------------
___NAME = 'Battleship Game Client'
___VER = '0.1.0.0'
___DESC = 'Battleship Game Client'
___BUILT = '2016-11-10'
# Functions -------------------------------------------------------------------
def __info():
    return '%s version %s (%s)' % (___NAME, ___VER, ___BUILT)

def window_control(events, server_window, lobby_window, game_window):
    '''Get events from queue and show windows accordingly.
    @param events: Queue of events
    @param server_window: ServerWindow
    @param lobby_window: LobbyWindow
    @param game_window: GameWindow
    '''
    while True:
        try:
            event, old_thread = events.get(timeout=5)
            if old_thread is not None:
                old_thread.join()
            if event == 'server':
                server_window.show()
            elif event == 'lobby':
                lobby_window.show()
            elif event == 'game':
                game_window.show()
            elif event == 'close':
                # To stop consuming
                channel.basic_publish(exchange='direct_logs',
                                      routing_key='quit',
                                      body='')
                server_window.root.quit()
                lobby_window.root.quit()
                #game_window.root.quit()
                break
            else:
                LOG.debug('Unknown event for window control: %s' % event)
        except Queue.Empty:
            pass

def print_threads():
    '''Print names of all active threads except for the current.
    '''
    while True:
        print
        print('Active threads:')
        for t in threading.enumerate():
            if t != threading.current_thread():
                print t
        sleep(3)

# Main method -----------------------------------------------------------------
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
    args = parser.parse_args()

    # Connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=args.host, port=args.port))
    channel = connection.channel()
    channel.exchange_declare(exchange='direct_logs', type='direct')
    
    # Queues
    server_advertisements = channel.queue_declare(exclusive=True).method.queue
    client_queue = channel.queue_declare(exclusive=True).method.queue
    
    # To stop consuming, since it doesn't work properly for threads
    control_queue = channel.queue_declare(exclusive=True).method.queue
    channel.queue_bind(exchange='direct_logs',
                       queue=control_queue,
                       routing_key='quit')
    channel.basic_consume(stop_consuming,
                          queue=control_queue,
                          no_ack=True)
    
    # Queue for window control
    events = Queue.Queue()
    
    # Application windows
    server_window = ServerWindow(channel, server_advertisements, client_queue, events)
    lobby_window = LobbyWindow(channel, server_advertisements, client_queue, events)
    game_window = object()
    
    server_window.lobby_window = lobby_window
    lobby_window.game_window = game_window
    lobby_window.server_window = server_window
    #game_window.lobby_window = lobby_window
    
    # Controling which windows are shown and which are hidden
    t_control = threading.Thread(target=window_control, 
                                 args=(events, server_window, 
                                       lobby_window, game_window),
                                 name='Window control')
    t_control.setDaemon(True)
    t_control.start()
    
    # Printing threads for debug
    t_debug = threading.Thread(target=print_threads, name='Debug printing')
    t_debug.setDaemon(True)
    t_debug.start()
    
    try:
        Tkinter.mainloop()
    except KeyboardInterrupt as e:
        LOG.debug('Crtrl+C issued ...')
        LOG.info('Terminating client ...')
        # Send stop event to the control queue 
        channel.basic_publish(exchange='direct_logs',
                              routing_key='quit',
                              body='')
