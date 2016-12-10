# -*- coding: utf-8 -*-
"""
Created on Fri Dec  9 20:55:58 2016

@author: pavla
"""
# Imports----------------------------------------------------------------------
import common
from . import listen
import threading
import pika
import Tkinter
# Logging ---------------------------------------------------------------------
import logging
LOG = logging.getLogger(__name__)
# Classes ---------------------------------------------------------------------
class GameWindow(object):
    '''Window for displaying game.
    '''
    def __init__(self, channel, client_queue, events, parent):
        '''Set next window, gui elements, communication channel, and queues.
        Hides the game window.
        @param channel: pika connection channel
        @param client_queue: queue for messages to client
        @param events: Queue of events for window control
        '''
        # Next window
        self.server_window = None
        self.game_window = None
        
        # Arguments from server_window
        self.server_name = None 
        self.client_name = None
        self.game_name = None
        
        # Queue of events for window control
        self.events = events
        
        # GUI
        self.root = Tkinter.Toplevel(master=parent.root)
        self.root.title('Battleships')
        self.root.protocol("WM_DELETE_WINDOW", self.disconnect)
        
        self.frame = Tkinter.Frame(self.root)
        self.frame.pack()
        
        self.button_leave = Tkinter.Button(self.frame, text="Leave", 
                                           command=self.leave)
        self.button_leave.pack()
        
        self.frame_player = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_player.pack()
        
        self.frame_oponent = Tkinter.Frame(self.frame, borderwidth=15)
        self.frame_oponent.pack()
        
        # Communication
        self.channel = channel
        self.client_queue = client_queue
        
        self.root.withdraw()
    
    def show(self, arguments):
        '''Show the game window.
        @param arguments: arguments passed from previous window: 
                          [server_name, client username, game name]
        '''
        LOG.debug('Showing game window.')
        self.server_name = arguments[0]
        self.client_name = arguments[1]
        self.game_name = arguments[2]
        self.on_show()
        self.root.deiconify()

    def on_show(self):
        '''Bind queues, set consuming and listen.
        '''
        # Binding queues
        self.channel.queue_bind(exchange='direct_logs',
                                queue=self.client_queue,
                                routing_key=self.client_queue)
        # Set consuming
        self.channel.basic_consume(self.on_response, 
                                   queue=self.client_queue,
                                   no_ack=True)
        # Listening
        self.listening_thread = listen(self.channel, 'game')
        
        # TODO: Get field dimensions and players
        
        
        
        self.game_label = Tkinter.Label(self.frame_player, text="Game:")
        self.game_label.grid(columnspan=5)
        
        for i in range(5):
            for j in range(5):
                Tkinter.Button(self.frame_player).grid(row=i+1, column=j)
        
        
        players = ['']
        variable = Tkinter.StringVar(self.frame_oponent)
        variable.set('')
        
        self.opponent_menu = Tkinter.OptionMenu(self.frame_oponent, variable, *players)
        self.opponent_menu.grid(columnspan=5)
        
        for i in range(5):
            for j in range(5):
                Tkinter.Button(self.frame_oponent).grid(row=i+1, column=j)
        
        def refresh():
            # Reset var and delete all old options
            variable.set('')
            self.opponent_menu['menu'].delete(0, 'end')
        
            # Insert list of new options (tk._setit hooks them up to var)
            players.append('player1')
            for choice in players:
                self.opponent_menu['menu'].add_command(label=choice, command=Tkinter._setit(variable, choice))
        
        # I made this quick refresh bu20185tton to demonstrate
        Tkinter.Button(self.frame_oponent, text='Refresh', command=refresh).grid(columnspan=3)




    def hide(self):
        '''Hide the game window.
        '''
        LOG.debug('Hiding game window.')
        self.root.withdraw()
        self.on_hide()

    def on_hide(self):
        '''Unbind queues, stop consuming.
        '''
        # Unbinding queues
        self.channel.queue_unbind(exchange='direct_logs',
                                  queue=self.client_queue,
                                  routing_key=self.client_queue)
        # Stop consuming
        if threading.current_thread() == self.listening_thread:
            self.channel.stop_consuming()
        else:
            LOG.error('LobbyWindow.on_hide called from non-listening thread.')
    
    def disconnect(self):
        '''Disconnect from server.
        '''
        msg = common.REQ_DISCONNECT + common.SEP + self.client_name
        self.channel.basic_publish(exchange='direct_logs',
                                   routing_key=self.server_name,
                                   properties=pika.BasicProperties(reply_to =\
                                       self.client_queue),
                                   body=msg)
    
    def leave(self):
        pass
    
    def on_response(self, ch, method, properties, body):
        '''React on server response.
        @param ch: pika.BlockingChannel
        @param method: pika.spec.Basic.Deliver
        @param properties: pika.spec.BasicProperties
        @param body: str or unicode
        '''
        LOG.debug('Received message: %s', body)
        msg_parts = body.split(common.SEP)
        
        if msg_parts[0] == common.RSP_DISCONNECTED:
            self.hide()
            self.events.put(('server', None, None))
        