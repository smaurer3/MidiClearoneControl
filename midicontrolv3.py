#!/usr/bin/python
import mido
import argparse  
import json
from time import sleep
import thread
import sys
#import RPi.GPIO as GPIO
import socket
from collections import namedtuple
import re
from pprint import pprint

#Clearone:   Handles communications to Clearone DSPs
class Clearone(object):
    def __init__(self, hostname, username, password):
        self.telnet_timeout = 2
        self.telnet_port = 23
        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password
        

    def login(self):
        try:
            self.device.close()
            self.device = None
        except:
            pass
        status = self.connect(self.hostname)
        if not status:
            return ( False,"Could not Connect to Clearone")
        status = self.authenticate(self.username, self.password)
        if not status:
            return (False)
        return (True)

    def connect(self, clearone_ip): 
        try:
            self.device = socket.socket()
            self.device.connect((clearone_ip, self.telnet_port))
        except Exception as e: 
            return (False)
        return (True)

    def authenticate(self, clearone_user, clearone_pass, ):    
        while self.device.recv(512).find('user') < 0:
            pass
        login = self.send_login(clearone_user, clearone_pass)  
        return(login)

    def send_login(self, clearone_user, clearone_pass):
        self.device.send(clearone_user + "\r")
        while self.device.recv(512).find('pass') < 0:
            pass
        self.device.send(clearone_pass + "\r")
        while self.device.recv(512).find('Authenticated') < 0:
            if self.device.recv(512).find('Invalid') < 0:
                return(False)
            pass
        return(True)

    def send_data(self, data):
        data = data.strip()
        try:
            verboseprint("Sending to Clearone: '%s'\r" % data)
            self.device.send(data + '\r')
            return (True)
        except Exception as e:
            verboseprint("Failed to send data: %s - %s" % (data, e))
            return(False)
        
    def send_command(self,command):
        if self.send_data(command):
            return(True)
        self.login()
        if self.send_data(command):
            return(True)
        return(False)
        
    def rx_data(self):
        try:
            msg = self.device.recv(512)
        except:
            return(False)
        return(msg)
    
    def close(self):
        self.device.close()


#MidiClearone: Converts - Midi <-> Clearone, GPIO -> Midi and Clearone -> GPIO.
#              Returns appropiate midi or clearone + gpio pins which will then
#              need to be handled accordingly.   
class MidiClearone(object):
    def __init__(self, commands, gpio):

        self.commands = commands
        self.gpio = gpio
        self.momentary_button_pushed = None
        self.encoder_changed = namedtuple("encoder_changed", "changed amount")
        self.encoder_changed.changed = False
        self.encoder_changed.amount = 0
        
    def clearone_rx(self, data): 
        def match_command(command):
            rx_to_match = rx_command.strip()
            regex = (self.commands[command]["clearone"]["set_command"] % ".*")
            return re.match(regex,rx_to_match)
        
        
        def process_match(command):
            command = self.commands[command]
            clamp = lambda n: max(min(127, n), 0)
            def match_gpio(index):
                if 'param' in self.gpio[index]:
                    return (
                            self.gpio[index]["param"] == midi_bytes.param and
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
            
            
            def create_midi(status, value, param):         
                msg = mido.parse([status, param, value]) 
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
                clearone_device.send_data(momentary_press())
                return
            if self.encoder_changed.changed:
                clearone_device.send_data(encoder_change())
                return
            
            value = midi_value()
            if 'param' not in command['midi']:
                param = value    
            else:
                param = command["midi"]['param']
            
            midi_bytes = namedtuple("midi_bytes", "status value param")
            midi_bytes.status = int(command["midi"]['status'])
            midi_bytes.value = int(value + .5)
            midi_bytes.param = int(param + .5)
            midi = create_midi(
                                midi_bytes.status, 
                                midi_bytes.value, 
                                midi_bytes.param
                            )
   
            gpios = filter(match_gpio, self.gpio)
            gpio = map(set_gpio, gpios)         

            obj = {
                    "midi" : midi,
                    "gpio" : gpio
                    }
            return(obj)     
  
        rx_commands = data.split('\r')
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
            
    def midi_rx(self,data):
        midi_bytes = namedtuple("midi_bytes", "status value param")
        midi_bytes.status = data[0]
        midi_bytes.value = data[2]
        midi_bytes.param = data[1]
        
        def match_midi(command):
            midi_command = self.commands[command]["midi"]
            if "param" in midi_command:
                param = midi_bytes.param == midi_command["param"]
            else:
                param = True
            return (midi_command["status"] == midi_bytes.status and param)
        
        def process_match(command):
            command = self.commands[command]
            def clearone_value():
                min = command["clearone"]["min"]
                max = command["clearone"]["max"]
                value = _map(midi_bytes.value, 0,127,min,max)
                value = round(value, 2)
                value = ('%f' % value).rstrip('0').rstrip('.')
                return (value)
            
            def momentary_press():
                self.momentary_button_pushed = (midi_bytes.value == 127)
                return (command["clearone"]["get_command"])

            def encoder_change():    
                self.encoder_changed.changed = True
                amount = command["midi"]["step"]
                inc = command["midi"]["inc"]
                dec = command["midi"]["dec"]
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
    
    def gpio_status_check(self):
            def match_gpio(gpio_pin):
                pin = int(gpio_pin["in_pin"])
                return (GPIO.input(pin))

            def process_match(matched_pin):
                pin_triggered = matched_pin["in_pin"]
                verboseprint("GPIO Input High on PIN: %s" % pin_triggered)
                midi_status = matched_pin["status"]
                if "param" in matched_pin:
                    midi_param = matched_pin["param"]
                else:
                    midi_param = 127
                midi_msg = (stats, param, 127)
                return (midi_msg)
                
            
            matched_pins = filter(match_gpio, self.gpio)
            return map(process_match, matched_pins)

verboseprint = lambda s: None

clearone_device = None
midi = None
midi_clearone = None

def main():
    global verboseprint, clearone_device, midi_clearone, midi

    print ("-"*80 + "\nMidi Clearone Controller\n" + "-"*80)
    args = get_args()
    if args.verbose:
        verboseprint = lambda s: pprint(s)
    settings = load_settings(args.settings)
    clearone_settings = settings["clearone"]
    midi_settings = settings["midi_controller"]
    commands = settings["commands"]	
    gpio = settings["gpio"]
    print ("\tOpening MIDI Ports...\n")
    midi = open_midi(midi_settings["in_port"], midi_settings["out_port"])

    clearone_device = Clearone(
                                clearone_settings["hostname"],
                                clearone_settings["user"],
                                clearone_settings["password"]
                            )
    verboseprint("Cleaone Login=%s" % clearone_device.login())
    midi_clearone = MidiClearone(commands,gpio)
      
    start_threads()
    while True:    
        clearone_device.send_data("#** VER")
        sleep(300)

def midi_thread():  
        print ("Midi Thread Started")
        while 1:   
            msg = midi.midi_in.receive()
            midi_data_received(msg.bytes())
             
def clearone_thread():  
    print ("Telnet Thread Started")
    while 1: 
        try:
            msg = clearone_device.rx_data()
            clearone_data_received(msg)
        except Exception as e: 
            print(e)
            clearone_device.login()
            
                
def start_threads(): 
    try:					
        thread.start_new_thread( midi_thread, ())			
        thread.start_new_thread( clearone_thread, ())
    except:
       print "Error: unable to start threads"


def gpio_rx_thread(): 
        pin_status = False
        pin_triggered = ''
        print "GPIO Thread Started"
        while 1:  
            sleep(.05)
            for C in Pins:
                if GPIO.input(int(Pins[C]['InPin'])):
                    pin_triggered = C
                    
                    print "Pin Triggered: " + C
                    Status = Pins[C]['MidiStatus']
                    Param1 = Pins[C]['MidiParam1']
                    msg = [int(Status), int(Param1), 127]
                    if not pin_status:
                        processMidiRX(msg)
                    pin_status = True
                else:
                    if pin_triggered == C:
                        pin_status = False						
def midi_data_received(data):
    verboseprint(data)
    clearone_commands_to_send = midi_clearone.midi_rx(data)
    for clearone_command in clearone_commands_to_send:
        verboseprint(clearone_command)
        clearone_device.send_data(clearone_command)

def clearone_data_received(data):
    (midi_commands, gpio_pins) = midi_clearone.clearone_rx(data)
    for midi_command in midi_commands:
        send_midi(midi_command)
    for gpio_pin in gpio_pins:
        for indivdual_commands in gpio_pin:
            set_gpio(indivdual_commands[0], indivdual_commands[1])



def send_midi(command):
    verboseprint( "SEND MIDI: %s" % command)
    midi.midi_out.send(command)

def set_gpio(pin, state):
    verboseprint("SET PIN %s: %s" % (pin,state))

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

def open_midi(in_port, out_port):
    midi_device = namedtuple("midi_device","midi_in midi_out")
    try:
        midi_device.midi_in = mido.open_input(in_port)
        midi_device.midi_out = mido.open_output(out_port)
        return (midi_device)
    except:
        list_midi_ports()
        sys.exit(3)

def list_midi_ports():
        print ("Invalid Midi Port\n" + "-"*40 + "\n\nAvailable Input Ports:\n")
        for p in mido.get_input_names():
            print p
        print ("\n" + "-"*40 + "\nAvailable Output Ports:\n")
        for p in mido.get_output_names():
            print p
        print (
                  "\n" + "-"*40 + "\nEnsure midi device is connected\n"
                   "\nChange midi ports in  settings.py\n"
             )

def gpio_setup(gpio):
    for C in gpio:
        GPIO.setup(int(gpio[C]['in_pin']), GPIO.IN, pull_up_down=GPIO.PUD_DOWN)	
        GPIO.setup(int(gpio[C]['out_pin']), GPIO.OUT)	
        GPIO.output(int(gpio[C]['out_pin']), 1)

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