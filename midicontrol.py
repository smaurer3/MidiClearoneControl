#!/usr/bin/python
import mido
import argparse  
import json
from time import sleep
import threading  # Updated from 'thread' to 'threading'
import sys
import socket
from collections import namedtuple
import re
from pprint import pprint
try:
    import RPi.GPIO as GPIO    
except ImportError:
    pass
class Clearone:
    def __init__(self, hostname, username, password):
        self.telnet_port = 23
        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password
        self.login()

    def login(self):
        try:
            if self.device:
                self.device.close()
            self.device = None
        except Exception:
            pass
        
        retry_delay = 10
        while not self.connect(self.hostname):
            print(f"No response from Clearone, waiting {retry_delay} seconds to retry")
            sleep(retry_delay)    
            retry_delay += 2
            if retry_delay > 16:
                retry_delay = 60

        status = self.authenticate(self.username, self.password)
        if not status:
            raise Exception("Could not authenticate Clearone")

    def connect(self, clearone_ip): 
        try:
            self.device = socket.socket()
            self.device.connect((clearone_ip, self.telnet_port))
            return True
        except Exception: 
            return False

    def authenticate(self, clearone_user, clearone_pass):    
        while self.device.recv(512).find(b'user') < 0:
            pass
        login = self.send_login(clearone_user, clearone_pass)  
        return login

    def send_login(self, clearone_user, clearone_pass):
        self.device.send((clearone_user + "\r").encode())
        while self.device.recv(512).find(b'pass') < 0:
            pass
        self.device.send((clearone_pass + "\r").encode())
        while True:
            response = self.device.recv(512)
            if b'Authenticated' in response:
                return True
            if b'Invalid' in response:
                return False

    def send_data(self, data):
        data = data.strip()
        try:
            if "verboseprint" in globals():
                verboseprint(f"Sending to Clearone: '{data}'")
            self.device.send((data + '\r').encode())
            return True
        except Exception as e:
            if "verboseprint" in globals():
                verboseprint(f"Failed to send data: {data} - {e}")
            return False
        
    def send_command(self, command):
        if self.send_data(command + "\r"):
            return True
        self.login()
        return self.send_data(command + "\r")

    def rx_data(self):
        try:
            msg = self.device.recv(512).decode(errors="ignore")
            if "verboseprint" in globals():
                verboseprint(f"RAW Data Received: {msg}")
            return msg
        except Exception:
            return False
    
    def close(self):
        if self.device:
            self.device.close()


class Midi(object):
    def __init__(self,in_port, out_port):
        try:
            self.midi_in = mido.open_input(in_port)
            self.midi_out = mido.open_output(out_port)
        except:
            print(self.list_midi_ports())
            sys.exit(2)            

    def list_midi_ports(self):
            port_msg = ("Invalid Midi Port\n" + "-"*40 + "\n\nAvailable Input Ports:\n")
            for p in mido.get_input_names():
                port_msg += p + "\n"
            port_msg += ("\n" + "-"*40 + "\nAvailable Output Ports:\n")
            for p in mido.get_output_names():
                port_msg += p + "\n"
            port_msg += (
                    "\n" + "-"*40 + "\nEnsure midi device is connected\n"
                    "\nChange midi ports in  settings.py\n\n"
                    "Alternatively, the:  -a, --auto_midi arguments can be used"
                    "\nto automatically use first Midi In and Out ports on system.\n"
                )
            return(port_msg)
            
class MidiClearone(object):
    def __init__(self, settings, enable_gpio, auto_port):
        self.commands = settings["commands"]
        self.gpio = settings["gpio"]
        self.clearone_settings = settings["clearone"]
        self.midi_settings = settings["midi_controller"]
        self.momentary_button_pushed = None
        self.encoder_changed = namedtuple("encoder_changed", "changed amount")
        self.encoder_changed.changed = False
        self.encoder_changed.amount = 0
        self.run_thread = False
        self.gpio_enabled = enable_gpio
        if auto_port:
            (in_port, out_port) = self.get_midi_ports()
            self.midi_settings["in_port"] = in_port
            self.midi_settings["out_port"] = out_port
        print("Midi In Port: %s\nMidi Out Port: %s\n" % (
            self.midi_settings["in_port"],
            self.midi_settings["out_port"]
            )
        )
        if enable_gpio:
            self.gpio_setup(self.gpio)
        self.midi = Midi(
                            self.midi_settings["in_port"], 
                            self.midi_settings["out_port"]
                        )

        self.clearone_device = Clearone(
                                    self.clearone_settings["hostname"],
                                    self.clearone_settings["user"],
                                    self.clearone_settings["password"]
                                )
        
    def get_midi_ports(self):
        print("Auto selecting Midi Ports...\n")
        in_ports = mido.get_input_names()
        out_ports = mido.get_input_names()
        try:
            return(in_ports[0], out_ports[0])
        except Exception as e:
            raise Exception("Could not get Midi Ports, %s" % e)
              
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

    def run_startup_commands(self):
        startup_commands = self.clearone_settings["startup_commands"]
        for command in startup_commands:
             self.clearone_device.send_command(command)

    def clearone_to_midi_gpio(self, data): 
        def match_command(command):       
            rx_to_match = rx_command.strip()
            regex = (command["clearone"]["set_command"] % ".*")
            return re.match(regex,rx_to_match)
              
        def process_match(command):
            clamp = lambda n: max(min(127, n), 0)
            def match_gpio(index):
                if 'data' in self.gpio[index]:
                    return (
                            self.gpio[index]["data"] == midi_bytes.data and
                            self.gpio[index]["status"] == midi_bytes.status 
                        )
                else:
                    return (self.gpio[index]["status"] == midi_bytes.status )

            def set_gpio(gpio):
                pin = int(self.gpio[gpio]["out_pin"])
                if value > 0:
                    return (pin, 1)
                else:
                    return (pin, 0)
                      
            def create_midi(status, value, data):         
                msg = mido.parse([status, data, value]) 
                return msg
                
            def get_value(clearone_rx):
                set_command = command["clearone"]["set_command"].split()
                clearone_rx = clearone_rx.split()
                value_index = set_command.index("%s")
                return float(clearone_rx[value_index])     
            
            def midi_value():
                min = command["clearone"]["min"]
                max = command["clearone"]["max"]
                value = get_value(rx_command)
                value = clamp(_map(value, min,max,0,127))
                return (value)

            def momentary_press():
                self.momentary_button_pushed = False
                value = get_value(rx_command)
                if value == command["clearone"]["max"]:
                    value = command["clearone"]["min"]
                elif value == command["clearone"]["min"]:
                    value = command["clearone"]["max"]
                return (command["clearone"]["set_command"] % value)

            def encoder_change():
                self.encoder_changed.changed = False
                value = (
                            get_value(rx_command) +
                            self.encoder_changed.amount
                        )
                return (command["clearone"]["set_command"] % value)
            
            if self.momentary_button_pushed:
                self.clearone_device.send_data(momentary_press())
            if self.encoder_changed.changed:
                self.clearone_device.send_data(encoder_change())

            
            value = midi_value()
            if 'midi' in command:
                if 'data' not in command['midi']:
                    data = value    
                else:
                    data = command["midi"]['data']
            
                midi_bytes = namedtuple("midi_bytes", "status value data")
                midi_bytes.status = int(command["midi"]['status'])
                midi_bytes.value = int(value + .5)
                midi_bytes.data = int(data + .5)
                midi = create_midi(
                                    midi_bytes.status, 
                                    midi_bytes.value, 
                                    midi_bytes.data
                                )
            else:
                midi = {}
   
            gpios = filter(match_gpio, self.gpio)
            gpio = map(set_gpio, gpios)         

            obj = {
                    "midi" : midi,
                    "gpio" : gpio
                    }
            return(obj)     
  
        rx_commands = re.split("\r|OK>", data)   
        is_command = lambda d: '#' in d
        rx_commands = filter(is_command, rx_commands)
        
        midi_to_return = []
        gpio_to_return = []
        for rx_command in rx_commands:
            matched_commands = filter(match_command,self.commands)
            midi_gpio = map(
                                                    process_match, 
                                                    matched_commands
                                                )
            for each_midi_gpio in midi_gpio:
                midi_to_return.append(each_midi_gpio["midi"])
                gpio_to_return.append(each_midi_gpio["gpio"])
        
        return (midi_to_return, gpio_to_return)
            
    def midi_to_clearone(self,data):
        midi_bytes = namedtuple("midi_bytes", "status value data")
        midi_bytes.status = data[0]
        midi_bytes.value = data[2]
        midi_bytes.data = data[1]
        
        def match_midi(command):
            midi_command = command["midi"]
            if "data" in midi_command:
                data = midi_bytes.data == midi_command["data"]
            else:
                data = True
            return (midi_command["status"] == midi_bytes.status and data)
        
        def process_match(command):
            def clearone_value():
                min = command["clearone"]["min"]
                max = command["clearone"]["max"]
                value = _map(midi_bytes.value, 0,127,min,max)
                value = round(value, 2)
                value = ('%f' % value).rstrip('0').rstrip('.')
                return (value)
            
            def momentary_press():
                if midi_bytes.value == 127:
                    self.momentary_button_pushed = True
                    return (command["clearone"]["get_command"])

            def encoder_change():    
                self.encoder_changed.changed = True
                amount = command["clearone"]["step"]
                inc = command["clearone"]["inc"]
                dec = command["clearone"]["dec"]
                step = 0
                if midi_bytes.value == inc:
                    step = amount
                if midi_bytes.value == dec:
                    step = amount * -1
                self.encoder_changed.amount = step
                return (command["clearone"]["get_command"])

            _type = command["midi"]["type"]
            if _type == "momentary":
                return(momentary_press())

            if _type == "incremental":
                return(encoder_change())

            value = clearone_value()
            return (command["clearone"]["set_command"] % value)

        matched_midis = filter(match_midi,self.commands)
        return map(process_match,matched_midis)
    
    def midi_thread(self):  
            while self.run_thread:   
                msg = self.midi.midi_in.receive()
                self.midi_data_received(msg.bytes())
                
    def clearone_thread(self):  
        while self.run_thread: 
            try:
                msg = self.clearone_device.rx_data()
                self.clearone_data_received(msg)
            except Exception as e: 
                print("Clearone Thread Error: %s" % e)
                self.clearone_device.login()
    
    def gpio_rx_thread(self): 
            midi_msg_sent = False
            pin_triggered = ''
            while self.run_thread:  
                sleep(.05)
                for pin in self.gpio:
                    if GPIO.input(int(self.gpio[pin]['in_pin'])):
                        pin_triggered = pin
                        
                        status = self.gpio[pin]['status']
                        if "data" in self.gpio[pin]:
                            data = self.gpio[pin]['data']
                        else:
                            data = 127
                        msg = [int(status), int(data), 127]
                        if not midi_msg_sent:
                            self.midi_data_received(msg)
                        midi_msg_sent = True
                    else:
                        if pin_triggered == pin:
                            midi_msg_sent = False	


    def start_threads(self):
        try:
            self.run_thread = True
            self.stop_event = threading.Event()  # Add event for stopping threads

            threads = [
                threading.Thread(target=self.midi_thread, daemon=True),
                threading.Thread(target=self.clearone_thread, daemon=True)
            ]

            if self.gpio_enabled:
                threads.append(threading.Thread(target=self.gpio_rx_thread, daemon=True))

            for t in threads:
                t.start()

        except Exception as e:
            raise Exception(f"Unable to start Threads: {e}")

        print("\nReady and Running...")
        while self.run_thread:
            sleep(300)
            self.clearone_device.send_data("#** VER")
           
                                                
    def midi_data_received(self,data):
        verboseprint("Data Received from Midi Device: %s" % data)
        clearone_commands_to_send = self.midi_to_clearone(data)
        for clearone_command in clearone_commands_to_send:
            if clearone_command:
                verboseprint("Sending Command to Clearone: %s" 
                             % clearone_command)
                self.clearone_device.send_data(clearone_command)

    def clearone_data_received(self,data):
        (midi_commands, gpio_pins) = self.clearone_to_midi_gpio(data)
        for midi_command in midi_commands:
            if midi_command:
                verboseprint("Sending MIDI: %s" % midi_command)
                self.midi.midi_out.send(midi_command)
        if self.gpio_enabled:
            self.gpio_received(gpio_pins)

    def gpio_received(self,gpio_pins):
        for gpio_pin in gpio_pins:
            if gpio_pin:
                for indivdual_commands in gpio_pin:
                    self.set_gpio(indivdual_commands[0], indivdual_commands[1])
    
    def set_gpio(self,pin, state):
        verboseprint("SET PIN %s: %s" % (pin,state))
        GPIO.output(pin, state)

    def send_defaults_to_clearone(self):
        for command in self.commands:
            clearone_command = command["clearone"]
            self.clearone_device.send_command(
                                clearone_command["set_command"]
                                % clearone_command["default"]
                                )
            msg = self.clearone_device.rx_data()
            self.clearone_data_received(msg)
    
    def gpio_setup(self,gpio):
        print ("Setting up GPIO")
        GPIO.setmode(GPIO.BOARD)
        for command in gpio:
            GPIO.setup(int(gpio[command]['in_pin']), GPIO.IN, pull_up_down=GPIO.PUD_DOWN)	
            GPIO.setup(int(gpio[command]['out_pin']), GPIO.OUT)	
            GPIO.output(int(gpio[command]['out_pin']), 1)

    def get_clearone_status(self):
        for command in self.commands:
            clearone_command = command["clearone"]
            self.clearone_device.send_command(
                                clearone_command["get_command"]
                                )
            msg = self.clearone_device.rx_data()
            self.clearone_data_received(msg)
            
verboseprint = lambda s: None

def main():
    global verboseprint

    print ("-"*80 + "\nMidi Clearone Controller\n" + "-"*80)
    args = get_args()
    if args.verbose:
        verboseprint = lambda s: pprint(s)
        
    print (" "*40 + "\nLoading Settings...\n")
    settings = load_settings(args.settings)
    
    print (" "*40 + "\nConnecting to Clearone and Midi Controller Devices...\n")
    midi_clearone = MidiClearone(settings, args.gpio, args.auto)
    
    if args.wait:
        print ("Waiting for all Devices to connect")
        midi_clearone.wait_for_all_devices()
        print("All Devices Present")
    if args.startup:
        print("Running Startup Commands")
        midi_clearone.run_startup_commands()    
    
    if args.defaults:
        print (" "*40 + "\nSending Default Values to Clearone...\n")
        midi_clearone.send_defaults_to_clearone()
    else:
        print (" "*40 + "\nGetting Clearone Status...\n")
        midi_clearone.get_clearone_status()
    
    print (" "*40 + "\nStarting Midi, Clearone and Keep Alive Threads...\n")  
    midi_clearone.start_threads()
    midi_clearone.clearone_device.close()

def load_settings(file):  
    try:
        with open(file) as fh:
            settings = json.loads(fh.read())
    except Exception as e:
        raise Exception(
                'An error occured trying to open settings file: %s, %s'
                % (file, e)
                )
    return settings

def _map(value, leftMin, leftMax, rightMin, rightMax): 
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin
    valueScaled = float(value - leftMin) / float(leftSpan)
    return rightMin + (valueScaled * rightSpan)

def gpio_setup(gpio):
    for command in gpio:
        GPIO.setup(int(gpio[command]['in_pin']), GPIO.IN, pull_up_down=GPIO.PUD_DOWN)	
        GPIO.setup(int(gpio[command]['out_pin']), GPIO.OUT)	
        GPIO.output(int(gpio[command]['out_pin']), 1)

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
    
    parser.add_argument(
        "-d",
        "--defaults",
        action='store_true',
        help="Send default values to clearone on startup"
    )
    
    parser.add_argument(
        "-w",
        "--wait",
        action='store_true',
        help="Wait for devices specified in settings to be present on startup"
    )
    
    parser.add_argument(
        "-g",
        "--gpio",
        action='store_true',
        help="Enable Raspberry Pi GPIO, RPi.GPIO library mus be installed."
    )
    
    parser.add_argument(
        "-a",
        "--auto",
        action='store_true',
        help="Automatically use first Midi In and Out ports on system."
    )

    parser.add_argument(
        "-S",
        "--startup",
        action='store_true',
        help="Run startup commands after connection to Clearone"
    )
    return(parser.parse_args())

main()
