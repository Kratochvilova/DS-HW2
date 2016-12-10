import logging
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

import threading
from time import sleep

counter = 0

def listen(channel, owner=None):
    global counter
    def tmp_listen():
        LOG.debug('LISTEN start, owner: %s', owner)
        channel.start_consuming()
        LOG.debug('LISTEN end, owner: %s', owner)

    t = threading.Thread(target=tmp_listen, name='Listen-%d'%counter)
    counter +=1
    t.setDaemon(True)
    t.start()
    return t

def print_threads():
    '''Print names of all active threads except for the current.
    '''
    while True:
        print
        print('Active threads:')
        for t in threading.enumerate():
            if t != threading.current_thread():
                print t
        sleep(5)

def thread_printing():
    '''Created thread that prints all active threads except for current thread
    for debugging.
    '''
    t_debug = threading.Thread(target=print_threads, name='Debug printing')
    t_debug.setDaemon(True)
    t_debug.start()