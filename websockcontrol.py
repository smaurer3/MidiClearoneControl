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
import time

class Clearone(object):
    def __init__(self, hostname, username, password):
        self.telnet_port = 23
        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password
        #self.login()

    def login(self):
        try:
            self.device.close()
            self.device = None
        except:
            pass
        retry_delay = 10

        while not self.connect(self.hostname):
            print(
                "No response from Clearone, waiting %s to retry" % retry_delay
                )
            sleep(retry_delay)
            retry_delay += 1
            if retry_delay > 20:
                raise Exception("Could Not Connnect To Clearone")

        return self.authenticate(self.username, self.password)

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
        self.clearone_device = None


    def connect_clearone(self):
        verboseprint("Trying Connecting to Clearone")
        self.clearone_device = Clearone(
            self.clearone_settings["hostname"],
            self.clearone_settings["user"],
            self.clearone_settings["password"]
        )
        return self.clearone_device.login()

    def disconnect_clearone(self):
        verboseprint("Disconnecting") 
        self.clearone_device.close()
        self.clearone_device = None

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

    def send_keepalive(self):
        self.clearone_device.send_data("#** VER")

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

    def get_clearone_status(self):
        for command in self.commands:
            clearone_command = command["clearone"]
            self.clearone_device.send_command(
                                clearone_command["get_command"]
                                )

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
clearone_connected = False

class ws_Server(WebSocket):

    def handle(self):
        try:
            message = self.data
            command = json.loads(message)
            verboseprint(command)
            if command["command"] == "_reload_":
                ws_clearone.load_commands()

            elif command["command"] == "_refresh_":
                ws_clearone.get_clearone_status()
            else:
                matched_commands = ws_clearone.get_matched_ws(command['command'])
                verboseprint(matched_commands)
                ws_clearone.send_clearone(matched_commands, command['value'])
        except Exception as e:
                verboseprint("Something Went Wrong in handle: %s" % e)
                self.remove_me(self)

    def connected(self):
        global clearone_connected
        verboseprint(self.address, 'WS Client connected')
        try:

            if not clearone_connected:
                try:
                    ws_clearone.disconnect_clearone()
                except:
                    pass
                clearone_connected = ws_clearone.connect_clearone()
            clients.append(self)
        except Exception as e:
                verboseprint("Something Went Wrong in connected: %s" % e)
                self.remove_me(self)

    def handle_close(self):
        global clearone_connected
        verboseprint(self.address, 'WS Client Disconnected')
        try:
            clients.remove(self)
            if len(clients) == 0:
                ws_clearone.disconnect_clearone()
                clearone_connected = False
            print(self.address, 'closed')
        except Exception as e:
                verboseprint("Something Went Wrong in handle_close: %s" % e)
                self.remove_me(self)

    def remove_me(self):
        try:
            print("Trying to remove client")
            clients.remove(self)
        except Exception as e:
            verboseprint("Couldn't remove client: %s" % e)



def clearone_thread():
    global clearone_connected
    while True:
        sleep(.01)
        if clearone_connected:
            try:
                data_rx = ws_clearone.recv_clearone()
                clearone_commands = ws_clearone.get_clearone_commands(data_rx)
                commands = ws_clearone.generate_ws_command(clearone_commands)
                message = json.dumps(commands)


                for client in clients:
                        client.send_message(message)

            except Exception as e:
                verboseprint("Something Went Wrong: %s, Probably all clients disconnected." % e)
                clearone_connected = False

def clearone_keepalive_thread():
    global clearone_connected
    timer = time.time() + 60
    verboseprint("Keep Alive Started")
    while True:
        sleep(10)
        if clearone_connected:
            try:
                if time.time() > timer:
                    verboseprint("Keep alive - sending request")
                    ws_clearone.send_keepalive()
                    timer = time.time() + 60
            except Exception as e:
                verboseprint("Something Went Wrong: %s" % e)
                clearone_connected = False


def server_thread(port):
    server = WebSocketServer('', port, ws_Server)
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
               
    ws_clearone = WebsocketClearone(args.settings)
    port = args.port
    print(port)
    ws_thread = Thread(target=server_thread, args=(port,))
    ws_thread.start()

    clearone_run = Thread(target=clearone_thread)
    clearone_run.start()

    clearone_keepalive = Thread(target=clearone_keepalive_thread)
    clearone_keepalive.start()
  

    



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
    required_argument.add_argument(
        "-p", 
        "--port",
        help="Specify Websocket Port",
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
