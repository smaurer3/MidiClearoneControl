import mido
import argparse  
import json
from time import sleep
import thread
import sys
import RPi.GPIO as GPIO
import socket
from collections import namedtuple
import re

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
	def __init__(self, clearone, midi, commands, gpio):
		self.clearone = clearone
		self.midi = midi
		self.commands = commands
		self.gpio = gpio

	def create_midi(self, status, value, param1):  
		if param1 == '':
			param1 = value
		return mido.parse([int(status), int(param1), value]) 


def main():
	settings = load_settings("settings.json")
	clearone_settings = settings["clearone"]
	midi_settings = setting["midi_controller"]
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

def open_midi(in_port, out_port):
	midi_device = namedtuple("midi_dev","midi_in midi_out")
	try:
		midi_dev.midi_in = mido.open_input(in_port)
		midi_dev.midi_out = mido.open_output(out_port)
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


def _map(value, leftMin, leftMax, rightMin, rightMax): 
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin
    valueScaled = float(value - leftMin) / float(leftSpan)
    return rightMin + (valueScaled * rightSpan)





def process_clearone_rx(data): 
	commands = data.split('\r')
	
	def is_command(data):
		return ('#' in data)
	
	commands = filter(is_command, commands)

	for command in commands:

##### I'm up to here in new verion  #####
	try: 
		data = dataTemp[indices[0]]   #Get list item of command
	except:
		pass
	start = data.find("#")	#find the actual start of the command
	if start < 0:			#check if a command is contained in the string, otherwise return
		return False
	
	try:	
		dataSplit = data[start:].split(' ')   #split command string by spaces 
		rxModel = dataSplit[0][1:-1]		#Get model code from 1st list item
		rxDeviceID = dataSplit[0][2:]		#Get device id from 1st list item
	
		rxCommand = dataSplit[1]		# Get the command type from data string - Mute or Matrix Level at the moment
		if rxCommand == 'VER':
			return
		channel = dataSplit[2]				#get Clearone channel and group from data string
		group = dataSplit[3]
	except:
		print "Weird Data"
		return
	#iterate through commands in xml 
	for C in Commands:
		ClearoneCommand = Commands[C]['Clearone']
		MidiCommand = Commands[C]['Midi']
		
		if ClearoneCommand['DeviceType'] is None:  #if devicetype is blank skip assume the command is blank and skip
			continue
		#Check if current command received from clearone matches command in xml, if match process it.
		if ClearoneCommand['DeviceType'] == rxModel and ClearoneCommand['DeviceID'] == rxDeviceID and ClearoneCommand['Command'] == rxCommand and ClearoneCommand['Group'] == group and ClearoneCommand['Channel'] == channel:
			
			#find the index position of the Variable that needs to be changed (prefix *m, *v or *e)
			valueIndex = 3
			for i in ClearoneCommand['Values']:
				valueIndex += 1
				if ClearoneCommand['Values'][i][:2] == '*v' or ClearoneCommand['Values'][i][:2] == '*m'or ClearoneCommand['Values'][i][:2] == '*e':
					break
			value = dataSplit[valueIndex]
			
			if MomentaryBP:   #Check if a momentary button was presseed, cause then the value needs to be changed and sent back to the clearone
				print data, minmax, value
				if int(value) == int(minmax[0]):
					
					m = data[:-1] + minmax[1] + '\r'
				if int(value) == int(minmax[1]):
					
					m = data[:-1] + minmax[0] + '\r'
				MomentaryBP = False
				telnet(m)
				return
				
			if Encoder:			#Check if encoder was changed, again the value needs to be incremented or decremented then sent back to the clearone.
				Encoder = False
				m = "#" + rxModel + rxDeviceID + ' ' + rxCommand + ' ' + channel + ' ' + group

				value = str(float(value) + float(ec[0]))
				
				for i in ec[1]:
					
					if ec[1][i][:2] == '*f':
						
						m = m + ' ' + ec[1][i][2:]		
						continue	
					if ec[1][i][:2] == '*e':
						m = m + ' ' + value
					else:
						m = m + ' ' + ec[1][i]
				
				
				ec = []
				m = m + '\r'
				telnet(m)
				return
				
				
			minmax = ClearoneCommand['Values'][i][2:].split(',')
			value = int(translate(float(value), float(minmax[0]),float(minmax[1]),0,127))  #Map the min and max values to between 0-127 for the midi device.
			for C in Pins:
				if MidiCommand['Status'] == Pins[C]['MidiStatus'] and MidiCommand['Param1'] == Pins[C]['MidiParam1']:
					if value > 0:
						GPIO.output(int(Pins[C]['OutPin']), 1)
					else:
						GPIO.output(int(Pins[C]['OutPin']), 0)
			try:
				if MidiCommand['Param1'] is None:
					midiOut.send(createMidi(MidiCommand['Status'], value, ''))
				else:
					midiOut.send(createMidi(MidiCommand['Status'], value, MidiCommand['Param1']))
				return
			except: #An error will occur if it is a *e and the value goes out of range (0-127), the map function won't work properly because it doesn't know the min and max values
					#At the moment this is something that can be lived with because the encoders on the icon don't have any feedback and that is the only thing that can trigger this fault.
				print "MIDI Command Creation Error, proably using an incremental encoder and the value is negative: VALUE=" + str(value)
	

			