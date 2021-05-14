#!/usr/bin/python3

import argparse

import json
from threading import Thread
from simple_websocket_server import WebSocketServer, WebSocket
import socket
import sys
import re
from time import sleep
from pprint import pprint

class Clearone(object):
    def __init__(self, hostname, username, password):
        self.telnet_port = 23
        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password
        self.login()

    def login(self):
        try:
            self.device.close()
            self.device = None
        except:
            pass
        retry_delay = 10
        
        while not self.connect(self.hostname):
            print("No response from Clearone, waiting %s to retry" % retry_delay)
            sleep(retry_delay)    
            retry_delay += 1
            if retry_delay > 20:
                raise Exception("Could Not Connnect To Clearone")

        status = self.authenticate(self.username, self.password)
        if not status:
            raise Exception("Could not authenticate Clearone")

    def connect(self, clearone_ip): 
        while True:
            try:
                self.device = socket.socket()
                self.device.connect((clearone_ip, self.telnet_port))
                return True
            except: 
                return False

    def authenticate(self, clearone_user, clearone_pass, ):    
        while self.device.recv(512).find('user'.encode()) < 0:
            pass
        login = self.send_login(clearone_user, clearone_pass)  
        return(login)

    def send_login(self, clearone_user, clearone_pass):
        self.device.send((clearone_user + "\r").encode())
        while self.device.recv(512).find(('pass'.encode())) < 0:
            pass
        self.device.send((clearone_pass + "\r").encode())
        while self.device.recv(512).find('Authenticated'.encode()) < 0:
            if self.device.recv(512).find('Invalid'.encode()) < 0:
                return(False)
            pass
        return(True)

    def send_data(self, data):
        data = data.strip()
        try:
            verboseprint("Sending to Clearone: '%s'" % data)
            self.device.send((data + "\r").encode())
            return (True)
        except Exception as e:
            verboseprint("Failed to send data: %s - %s" % (data, e))
            return(False)
        
    def send_command(self,command):
        if self.send_data((command + "\r")):
            return(True)
        self.login()
        if self.send_data((command + "\r")):
            return(True)
        return(False)
        
    def rx_data(self):
        try:
            msg = self.device.recv(512).decode('utf-8')
            verboseprint("RAW Data Received: %s" % msg)
        except:
            return(False)
        return(msg)
    
    def close(self):
        self.device.close()

            
class WebsocketClearone(object):
    def __init__(self, settings):
        self.settings_file = settings
        self.commands = None
        self.clearone_settings = None
        self.load_commands()
        self.run_thread = False
        self.clearone_device = Clearone(
                                    self.clearone_settings["hostname"],
                                    self.clearone_settings["user"],
                                    self.clearone_settings["password"]
                                )
              
    def load_commands(self):
        settings = self._load_settings(self.settings_file)
        self.commands = settings["websocket"]
        verboseprint(self.commands)
        self.clearone_settings = settings["clearone"]

    def _load_settings(self,file):  
        try:
            with open(file) as fh:
                settings = json.loads(fh.read())
        except Exception as e:
            raise Exception(
                    'An error occured trying to open settings file: %s, %s'
                    % (file, e)
                    )
        return settings

    def wait_for_all_devices(self):
        device_list = self.clearone_settings["devices"]
        device_list_count = len(device_list)
        while device_list_count > 0:
            device_list_count = len(device_list)
            sleep(1)
            self.clearone_device.send_command("#** DID")
            response = self.clearone_device.rx_data()
            responses = response.split()
            devices = filter(lambda r: "#" in r, responses)
            for device in device_list:
                if any(device in s for s in devices):
                    device_list_count -= 1 

    def get_matched_ws(self,data):
        matched_commands = []
        
        for command in self.commands:
            
            if command['command'] == data:
                matched_commands.append(command)
        return matched_commands
    
    def send_clearone(self, commands, value):
        for command in commands:
            clearone_command = command['clearone']['set_command'] % (value)
            self.clearone_device.send_command(clearone_command)

    def recv_clearone(self):
        return self.clearone_device.rx_data()

    def get_clearone_commands(self,data):
        rx_commands = re.split("\r|OK>", data)   
        is_command = lambda d: '#' in d
        rx_commands = filter(is_command, rx_commands)
        return self._match_clearone_commands(rx_commands)

    def generate_ws_command(self, commands):
        ws_commands = []
        for command in commands:
            value = command['value']
            ws_command = command['command']['command']
            ws_commands.append({"command" : ws_command, "value" : value})
        return ws_commands           

    def _match_clearone_commands(self, rx_commands):       
            ws_commands = []
            for rx_command in rx_commands:
                rx_to_match = rx_command.strip()
                for command in self.commands:
                    regex = (command["clearone"]["set_command"] % ".*")
                    if re.match(regex,rx_to_match):
                        ws_commands.append(
                            {
                                "command" : command, 
                                "value" : self._get_value(rx_to_match, command)
                            }
                        )
            return ws_commands

    def _get_value(self, clearone_rx, command):
                set_command = command["clearone"]["set_command"].split()
                clearone_rx = clearone_rx.split()
                value_index = set_command.index("%s")
                return float(clearone_rx[value_index])

clients = []
class ws_Server(WebSocket):

    def handle(self):
        message = self.data
        command = json.loads(message)
        verboseprint(command)
        if command["command"] == "_reload_":
            ws_clearone.load_commands()
        else:
            matched_commands = ws_clearone.get_matched_ws(command['command'])
            verboseprint(matched_commands)
            ws_clearone.send_clearone(matched_commands, command['value'])
        
    def connected(self):
        print(self.address, 'connected')
        for client in clients:
            client.send_message(self.address[0] + u' - connected')
        clients.append(self)

    def handle_close(self):
        clients.remove(self)
        print(self.address, 'closed')
        for client in clients:
            client.send_message(self.address[0] + u' - disconnected')

        
def clearone_thread():
    while True:
        data_rx = ws_clearone.recv_clearone()
        clearone_commands = ws_clearone.get_clearone_commands(data_rx)
        commands = ws_clearone.generate_ws_command(clearone_commands)
        message = json.dumps(commands)
        
        for client in clients:
                client.send_message(message)
        sleep(.01)      


def server_thread():
    server = WebSocketServer('', 8766, ws_Server)
    print ("Starting Web socket server")
    server.serve_forever()  

ws_clearone = None 
verboseprint = lambda s: None

def main():
    global verboseprint
    global ws_clearone
    print ("-"*80 + "\Clearone Websocket Controller\n" + "-"*80)
    args = get_args()
    if args.verbose:
        verboseprint = lambda s: pprint(s)
               
    print (" "*40 + "\nConnecting to Clearone and Midi Controller Devices...\n")
    ws_clearone = WebsocketClearone(args.settings)

    ws_thread = Thread(target=server_thread)
    ws_thread.start()
    clearone_run = Thread(target=clearone_thread)
    clearone_run.start()
    
      
  
    
  


    while True:
        print ("Keep Alive")
        sleep(300)

    



def _map(value, leftMin, leftMax, rightMin, rightMax): 
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin
    valueScaled = float(value - leftMin) / float(leftSpan)
    return rightMin + (valueScaled * rightSpan)


def get_args():
    parser = argparse.ArgumentParser(
        description="Clearone Midi Control",
        formatter_class=argparse.RawTextHelpFormatter
    )
    required_argument = parser.add_argument_group("required arguments")
    required_argument.add_argument(
        "-s", 
        "--settings",
        help="Setiings JSON file",
        required=True
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action='store_true',
        help="Enable extended output"
    )
    
    return(parser.parse_args())

main()
