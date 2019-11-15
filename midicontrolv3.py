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
        if login:
            return (True)    
        return(False)

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
        try:
            self.device.send(data)
            return (True)
        except Exception as e: 
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


class MidiClearone(object):
    def __init__(self, commands, gpio):

        self.commands = commands
        self.gpio = gpio
        
    def create_midi(self, status, value, param1):  
        if param1 == '':
            param1 = value
        #return mido.parse([int(status), int(param1), value]) 

    def clearone_rx(self, data): 
        def match_command(command):
            rx_to_match = rx_command.strip()
            regex = (self.commands[command]["clearone"]["set_command"] % ".*")
            return re.match(regex,rx_to_match)
        
        
        def process_match(command):
            clamp = lambda n: max(min(127, n), 0)
            
            def match_gpio(index):
                if 'param' in self.gpio[index]:
                    return (
                            self.gpio[index]["param"] == midi_bytes.param and
                            self.gpio[index]["status"] == midi_bytes.status 
                        )
                else:
                    return (self.gpio[index]["status"] == midi_bytes.status )

            def set_gpio(gpio, value):
                pin = int(self.gpio[gpio]["out_pin"])
                if value > 0:
                    pprint((pin, "HIGH"))
                    #GPIO.output(int(Pins[C]['OutPin']), 1)
                else:
                    pprint((pin, "LOW"))
                    #GPIO.output(int(Pins[C]['OutPin']), 0)
            
            
            def create_midi(status, value, param):         
                msg = mido.parse([status, param, value]) 
                return msg
                
            def get_value(clearone_rx,command):
                set_command = command["clearone"]["set_command"].split()
                clearone_rx = clearone_rx.split()
                value_index = set_command.index("%s")
                return float(clearone_rx[value_index])     
            def midi_value(command):
                min = command["clearone"]["min"]
                max = command["clearone"]["max"]
                value = get_value(rx_command,command)
                value = clamp(_map(value, min,max,0,127))
                return (value)

            value = midi_value(command)
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
            for gpio in gpios:
                set_gpio(gpio, value)           
            #self.mido_out.send(midi)
            return(midi)     
  
        rx_commands = data.split('\r')
        is_command = lambda d: '#' in d
        rx_commands = filter(is_command, rx_commands)
        
        midi_to_return =[]
        for rx_command in rx_commands:
            matched_commands = filter(match_command,self.commands)
            for matched_command in matched_commands:
                midi_to_return.append(
                                process_match(self.commands[matched_command])
                                )

        return midi_to_return
            
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
            
            def clearone_value(command):
                min = command["clearone"]["min"]
                max = command["clearone"]["max"]
                value = _map(midi_bytes.value, 0,127,min,max)
                value = round(value, 2)
                value = ('%f' % value).rstrip('0').rstrip('.')
                return (value)
            
            def clearone_command(command,value):
                return (command["clearone"]["set_command"] % value)
            
            value = clearone_value(command)
            return clearone_command(command,value)

        matched_midis = filter(match_midi,self.commands)
        for matched_midi in matched_midis:
            return process_match(self.commands[matched_midi])
        




def main():
    settings = load_settings("settings.json")
    clearone_settings = settings["clearone"]
    midi_settings = settings["midi_controller"]
    commands = settings["commands"]	
    gpio = settings["gpio"]



    mc = MidiClearone(commands,gpio)
    pprint(mc.clearone_rx("#H2 MUTE D P 0 \r"
                    "#H2 FILTER H P 2 6 20000 0 3.7 \r"
                    " >#H2 VER 4.4.0.2 \r"
                    "#H2 GAIN C P 0.00 A\r"
                    "#H2 MUTE B P 0\r"
                    "#H2 MUTE A P 1"
                    ))
    print "MIDI RX TEST"
    print mc.midi_rx((176,23,64))
#mc.clearone_rx("#H2 GAIN C P 0 A")


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


main()

'''
def main():
    settings = load_settings("settings.json")
    clearone_settings = settings["clearone"]
    midi_settings = settings["midi_controller"]
    commands = settings["commands"]
    gpio = settings["gpio"]

    gpio_setup(gpio)

    midi_device = open_midi(
                            midi_settings["in_port"],
                            midi_settings["out_port"]
                            )

    clearone_device = Clearone(
                                clearone_settings["hostname"],
                                clearone_settings["user"],
                                clearone_settings["password"]
                            )
    if clearone_device.login():
        print("Clearone Login Success")
    else:
        print("Could not Connect to clearone" % output)
        sys.exit(3)

    midi_clearone = MidiClearone(clearone_device, midi_device, commands, gpio)
'''


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
'''
def gpio_setup(gpio):
    for C in gpio:
        GPIO.setup(int(gpio[C]['in_pin']), GPIO.IN, pull_up_down=GPIO.PUD_DOWN)	
        GPIO.setup(int(gpio[C]['out_pin']), GPIO.OUT)	
        GPIO.output(int(gpio[C]['out_pin']), 1)

'''
            