#!/usr/bin/python3

import argparse
import json
from threading import Thread
from simple_websocket_server import WebSocketServer, WebSocket
import socket
import re
from time import sleep
from pprint import pprint
import time
import traceback



clients = []
ws_clearone = None
verboseprint = lambda s: None
clearone_connected = False
tx_timer = 0
tx_timeout = False

class Clearone(object):
    def __init__(self, hostname, username, password):
        self.telnet_port = 23
        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password

    def login(self):
        global clearone_connected, tx_timeout
        try:
            self.device.close()
            self.device = None  
        except:
            verboseprint("Unable to close, probably wasn't connected")
        clearone_connected = False
        tx_timeout = False
        retry_delay = 10
        verboseprint("First Attempt to connect...")
        retries = 0
        while not self.connect(self.hostname):
            print(
                "No response from Clearone, waiting %s to retry" % retry_delay
                )
            sleep(retry_delay)
            retries += 1
            if retries > 5:
                verboseprint("Unable to Connect to clearone")
                return False
             
        return self.authenticate(self.username, self.password)

    def connect(self, clearone_ip):
        try:
            self.device = socket.socket()
            self.device.settimeout(5)
            self.device.connect((clearone_ip, self.telnet_port))
            verboseprint("Telnet Connection Opened")
            return True
        except:
            verboseprint("Unable to open telnet connection")
            return False

    def authenticate(self, clearone_user, clearone_pass, ):
        verboseprint("Waiting for 'user' prompt...")
        while self.device.recv(512).find('user'.encode()) < 0:
            pass
        login = self.send_login(clearone_user, clearone_pass)
        return(login)

    def send_login(self, clearone_user, clearone_pass):
        verboseprint("Sending username...")
        self.device.send((clearone_user + "\r").encode())
        verboseprint("Waiting for 'pass' prompt...")
        while self.device.recv(512).find('pass'.encode()) < 0:
            pass
        verboseprint("Sending password...")
        self.device.send((clearone_pass + "\r").encode())
        verboseprint("Wainting for confirmation 'Authenticated / Invalid'...")
        while self.device.recv(512).find('Authenticated'.encode()) < 0:
            if self.device.recv(512).find('Invalid'.encode()) < 0:
                verboseprint("Authentication invalid")
                return(False)
            pass
        verboseprint("Authentication Succuseful")
        return(True)

    def send_data(self, data):
        global clearone_connected, tx_timer, tx_timeout
        if not clearone_connected:
            verboseprint("Trying to send data but clearone not connected")
            return (False)
        data = data.strip()
        data = data.strip()
        try:
            verboseprint("Sending to Clearone: '%s'" % data)
            self.device.send((data + "\r").encode())
            tx_timer = time.time() + 5
            tx_timeout = True

        except Exception as e:
            verboseprint("Failed to send data: %s - %s" % (data, e))
            clearone_connected = False


    def send_command(self,command):
        return self.send_data((command + "\r"))

    def rx_data(self):
        try:
            msg = self.device.recv(512).decode('utf-8')
            verboseprint("RAW Data Received: %s" % msg)
        except Exception as e:
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
        global clearone_connected
        verboseprint("Disconnecting")
        self.clearone_device.close()
        self.clearone_device = None
        clearone_connected = False

    def load_commands(self):
        settings = self._load_settings(self.settings_file)
        self.commands = settings["commands"]
        verboseprint(self.commands)
        self.clearone_settings = settings["clearone"]

    def _load_settings(self, file):
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

    def get_matched_ws(self, data):
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

    def get_clearone_commands(self, data):
        rx_commands = re.split("\r|OK>", data)
        is_command = lambda d: '#' in d
        rx_commands = list(filter(is_command, rx_commands))
        return self._match_clearone_commands(rx_commands)

    def generate_ws_command(self, commands):
        ws_commands = []
        for command in commands:
            value = command['value']
            ws_command = command['command']['command']
            ws_commands.append({"command" : ws_command, "value" : value})
        return ws_commands

    def get_clearone_status(self):
        verboseprint("Getting statatus of Clearone")
        for command in self.commands:
            clearone_command = command["clearone"]
            self.clearone_device.send_command(
                                clearone_command["get_command"]
                                )
    
    def get_input_status(self, commands):
        for command in commands:
            clearone_command = command['clearone']['get_command']
            self.clearone_device.send_command(clearone_command)                              

    def _match_clearone_commands(self, rx_commands):
        ws_commands = []
        verboseprint(f'match this: {rx_commands}')
        for rx_command in rx_commands:
            verboseprint(f'First RX Command: {rx_command}')
            rx_to_match = rx_command.strip()
            for command in self.commands:
                regex = (command["clearone"]["set_command"] % ".*")
                #verboseprint(
                #    f'Trying REGEX Match Expression: {regex} String {rx_to_match}'
                #    )
                if re.match(regex, rx_to_match):
                    verboseprint("Match=True")
                    ws_commands.append(
                        {
                            "command": command,
                            "value": self._get_value(rx_to_match, command)
                        }
                    )
        verboseprint(f'Websocket Commands for Clients: {list(ws_commands)}')
        return ws_commands

    def _get_value(self, clearone_rx, command):
        set_command = command["clearone"]["set_command"].split()
        clearone_rx = clearone_rx.split()
        value_index = set_command.index("%s")
        return float(clearone_rx[value_index])





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
            elif command["command"] == "_input_status_":
                matched_commands = ws_clearone.get_matched_ws(command['value'])
                verboseprint(matched_commands)
                ws_clearone.get_input_status(matched_commands)
            else:
                matched_commands = ws_clearone.get_matched_ws(command['command'])
                verboseprint(matched_commands)
                ws_clearone.send_clearone(matched_commands, command['value'])
        except Exception as e:
            verboseprint("Something Went Wrong (ws_Server.handle): %s" % e)


    def connected(self):
        clients.append(self)
        verboseprint('WS Client connected')
            

    def handle_close(self):
        verboseprint('WS Client Disconnected')
        try:
            clients.remove(self)
            print(self.address, f'closed: clients remaining={len(clients)}')
        except Exception as e:
            verboseprint("Something Went Wrong (ws_server.handle_close: %s" % e)




def clearone_thread():
    global clearone_connected, tx_timer, tx_timeout
    while True:
        if clearone_connected:
            if (time.time() > tx_timer) and tx_timeout:
                verboseprint("Sent data and did not receive a response within 5 seconds")
                clearone_connected = False
                ws_clearone.disconnect_clearone()
                continue
            try:
                data_rx = ws_clearone.recv_clearone()
                if data_rx:
                    tx_timeout = False
                    clearone_commands = ws_clearone.get_clearone_commands(data_rx)
                    verboseprint(clearone_commands)
                    commands = ws_clearone.generate_ws_command(clearone_commands)
                    message = json.dumps(commands)
                    if len(message) > 2:
                        for client in clients:
                            verboseprint([f'Sending to client: {client}',f'Message: {message}'])
                            client.send_message(message)
            except (socket.timeout, socket.error):
                verboseprint("Socket Timeout")
                clearone_connected = False
                ws_clearone.disconnect_clearone()
            
            except Exception as e:
                verboseprint("Something Went Wrong (clearone_thread): %s" % e)
                verboseprint(traceback.format_exc())

        else:
                try:
                    clearone_connected = ws_clearone.connect_clearone()
                except Exception as e:
                    verboseprint("Something Went Wrong (clearone_keep_alive): %s" % e)
                    verboseprint(traceback.format_exc())
                    clearone_connected = False
              
            


def clearone_keepalive_thread():
    global clearone_connected
    verboseprint("Keep Alive Started")
    while True:
        sleep(60)
        if clearone_connected:
            try:                
                verboseprint("Keep alive - sending request")
                ws_clearone.send_keepalive()
            except Exception as e:
                verboseprint("Something Went Wrong (clearone_keep_alive): %s" % e)
                clearone_connected = False


def server_thread(port):
    server = WebSocketServer('0.0.0.0', port, ws_Server)
    print("Starting Web socket server")
    server.serve_forever()



def main():
    global verboseprint
    global ws_clearone
    print("\n" + "-"*80 + "\nClearone Websocket Controller\n" + "-"*80 + "\n")
    args = get_args()
    if args.verbose:
        verboseprint = lambda s: pprint(s)

    ws_clearone = WebsocketClearone(args.settings)
    port = args.port
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
        help="Settings JSON file",
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


if __name__ == "__main__":
    main()
