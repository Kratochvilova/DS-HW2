import logging
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

import threading

def listen(channel, owner=None):
    def tmp_listen():
        LOG.debug('LISTEN start, owner: %s', owner)
        channel.start_consuming()
        LOG.debug('LISTEN end, owner: %s', owner)

    t = threading.Thread(target=tmp_listen, name='Listening on channel')
    t.start()
    return t
