#!/usr/bin/env python

# This program is to control a Clearone Converge DSP using a Midi Control Surface
#
# Supported Clearone Commands:
#	MTRXLVL - Matrix level crosspoint gain adjustments - map to faders on midi controller to give channel fader control.
#	MUTE - Channel Mute - Map to buttons to toggle mute for channel
#   GMODE - Map to buttons on midi controller to toggle gate mode for channel between auto and manual on
#	MMAX - Adjust the maximum number of Micx in a gating group - Map to rotary encoders on midi controller
#	
# Midi Controller motors can be disabled or enabled by mapping button in the XML
#
# All Configuration is done in midicontrol.xml, don't change the order of anything in the xml file or the 
# program may fail.
# 
# Make sure you have a backup of the Clearone Configuration, or at least presets setup for the Matrix Corss points and Mutes you 
# are going to be changing before using this program.


import mido
import socket               # Import socket module
from time import sleep
import thread
import sys
import xmltodict

########### Load XML ######################
print "\n\n**********************************\n  Clearone Converge MIDI control\n**********************************\n\n......Loading XML.....\n"


with open('midi.xml') as fd:
	xml = xmltodict.parse(fd.read())
		

#     	
# #print Mutes
# #print GatingModes
# ##############   Clearone Settings    #############
clearoneIP = xml['ClearOneMidiControl']['Clearone']['Communication']['URL']

port = 23 
clearoneUser = xml['ClearOneMidiControl']['Clearone']['Communication']['User']
clearonePass= xml['ClearOneMidiControl']['Clearone']['Communication']['Password']
#See clearone serial guide for list of model codes.
Model = xml['ClearOneMidiControl']['Clearone']['Communication']['Model'] 
DeviceID = xml['ClearOneMidiControl']['Clearone']['Communication']['DeviceID']

#############       Midi Settings    ##############
#Midi In and Out ports to use
MidiInPortName = xml['ClearOneMidiControl']['MidiController']['MidiPorts']['In']
MidiOutPortName = xml['ClearOneMidiControl']['MidiController']['MidiPorts']['Out']

#MMAX =
#[int(MidiController[3][0]),int(MidiController[3][1]),MidiController[3
#][2]]
## 
#Motor Enable and Disable Command -list of Status, Param 1 and Param 2
MotorENMidi = [int(xml['ClearOneMidiControl']['MidiController']['MotorENMidi']['Status']),int(xml['ClearOneMidiControl']['MidiController']['MotorENMidi']['Param1']),int(xml['ClearOneMidiControl']['MidiController']['MotorENMidi']['Value'])] 
MotorDISMidi = [int(xml['ClearOneMidiControl']['MidiController']['MotorDISMidi']['Status']),int(xml['ClearOneMidiControl']['MidiController']['MotorDISMidi']['Param1']),int(xml['ClearOneMidiControl']['MidiController']['MotorDISMidi']['Value'])] 

Commands= xml['ClearOneMidiControl']['Commands']

print "......XML Loading Complete......\n"
s = socket.socket()         

# Open midi Ports	
try:
	midiIn = mido.open_input(MidiInPortName)
	midiOut = mido.open_output(MidiOutPortName)
except:
	print "Invalid Midi Port\n---------------------------------------\n\nAvailable Input Ports:\n"
	_in = mido.get_input_names()
	out = mido.get_output_names()
	for p in mido.get_input_names():
		print p
	print "\n---------------------------------------\nAvailable Output Ports:\n"
	for p in mido.get_output_names():
		print p
	print "\n---------------------------------------\nEnsure midi device is connected\n\nChange midi ports in  midicontrol.xml\n\n\n\n\n"
	sys.exit(0)
# Send the Motor Disable message to the midi device
msg = mido.parse(MotorDISMidi)	
midiOut.send(msg)

motorEN = False  #Global variable for enabling motors
run = False
pMidi = True
MomentaryBP = False

def translate(value, leftMin, leftMax, rightMin, rightMax):   #Same as map in java, arduino etc...
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin
    valueScaled = float(value - leftMin) / float(leftSpan)
    return rightMin + (valueScaled * rightSpan)

def clearBuffer():	#Reads the socket buffer to clear it
	sleep(.1)
	s.setblocking(0)
	s.recv(1024)
	s.setblocking(1)


	
def connectClearone():    #Connect to the clearone
	print "Attempting to login to Clearone"
	timeout = 10
	
	while 1:
		try:
			s.connect((clearoneIP, port))
			break
		except Exception as e: 
			print(e)
			print "Could not establish a telnet socket"
			sleep(timeout)
			timeout = timeout + 1   #Each time it fails to connect increase the retry time by 1 second.
			if timeout == 61:
				print "To many failed retry attempts...\nExiting Program."
				sys.exit(0)
			
	while s.recv(512).find('user') < 0:
		pass
	s.send(clearoneUser + "\r")
	while s.recv(512).find('pass') < 0:
		pass
	s.send(clearonePass + "\r")
	while s.recv(512).find('Authenticated') < 0:
		if s.recv(512).find('Invalid') < 0:
			print "Invalid User/Pass." 
			sys.exit(0)
		pass
	print "Login Succesful"	
	return s

def telnet(data):   #Send data to clearone via telnet, attempts to re-connect if there is a problem.
	global s
	#print data
	try:
		s.send(data)
	except Exception as e: 
		print(e)
		s = socket.socket()
		connectClearone()
		s.send(data)

def createMidi(Status, value, Param1):
	
	if Param1 == '':
		Param1 = value
	
	#print Param1
	msg = mido.parse([int(Status), int(Param1), value])  #generate and send the midi message
	#print msg
	return msg
			
def processRX(data):   #Process data received from clearone via telnet and translate and pass to midi controller
	global motorEN
	global MomentaryBP

	dataTemp = data.split('\r')  #Split the received data by lines
	indices = [i for i, s in enumerate(dataTemp) if '#' in s]  #find which list item contains the command string (#)
	#print dataTemp
	try: 
		data = dataTemp[indices[0]]   #Get list item of command
	except:
		pass
		#print data
	start = data.find("#")	#find the actual start of the command
	if start < 0:			#check if a command is contained in the string, otherwise return
		#print "Invalid Data"
		return
		
	dataSplit = data[start:].split(' ')   #split command string by spaces 
	rxModel = dataSplit[0][1:-1]		#Get model code from 1st list item
	rxDeviceID = dataSplit[0][2:]		#Get device id from 1st list item
	
	rxCommand = dataSplit[1]		# Get the command type from data string - Mute or Matrix Level at the moment
	if rxCommand == 'VER':
		return
	channel = dataSplit[2]				#get Clearone channel and group from data string
	group = dataSplit[3]
	
	for C in Commands:
		ClearoneCommand = Commands[C]['Clearone']
		MidiCommand = Commands[C]['Midi']
		
		if ClearoneCommand['DeviceType'] is None:
			continue
		if ClearoneCommand['DeviceType'] == rxModel and ClearoneCommand['DeviceID'] == rxDeviceID and ClearoneCommand['Command'] == rxCommand and ClearoneCommand['Group'] == group and ClearoneCommand['Channel'] == channel:
			valueIndex = 3
			for i in range(1,5):
				valueIndex += 1
				if ClearoneCommand['Values']['_' + str(i)][:2] == '*v' or ClearoneCommand['Values']['_' + str(i)][:2] == '*m':
					break
			value = dataSplit[valueIndex]
			
			if MomentaryBP:
				
				if int(value) == 1:
					m = data[:-1] + '0\r'
				if int(value) == 0:
					m = data[:-1] + '1\r'
				MomentaryBP = False
				telnet(m)
				return
			minmax = ClearoneCommand['Values']['_' + str(i)][2:].split(',')
			value = int(translate(float(value), float(minmax[0]),float(minmax[1]),0,127))

			if MidiCommand['Param1'] is None:
				midiOut.send(createMidi(MidiCommand['Status'], value, ''))
			else:
				midiOut.send(createMidi(MidiCommand['Status'], value, MidiCommand['Param1']))
			return
	# if rxModel != Model or rxDeviceID != DeviceID:   #Make sure we are communicating with the correct clearone converge
# 		print "Wrong Model / Device"
# 		return;
	
			# return from function as there is no point in continuing to search for matches
# 	
# 	if rxCommand == 'MTRXLVL' and motorEN == True:
# 		value = dataSplit[6]
# 		value = int(translate(float(value), -60,12,0,127))
# 		midiOut.send(createMidi(Faders, channel, value, group))
# 		return				# return from function as there is no point in continuing to search for matches

				
				
def getStatus():  #Get the stus of the clearone and sets the Midi Control Surface to match, runs at start up
	global motorEN
	global run
	motorEN = True
	run = False
	for C in Commands:
		MidiCommand = Commands[C]['Clearone']
		
		if MidiCommand['DeviceType'] is None:
			continue
		m = '#' + MidiCommand['DeviceType'] + MidiCommand['DeviceID'] + ' ' + MidiCommand['Command'] + ' ' + MidiCommand['Channel'] + ' ' + MidiCommand['Group']
		
		for i in range(1,5):
			if MidiCommand['Values']['_' + str(i)][:2] == '*v' or MidiCommand['Values']['_' + str(i)][:2] == '*m':
				break
			m = m + ' ' + MidiCommand['Values']['_' + str(i)]

		m = m + '\r'
		#print m
		telnet(m)
		sleep(.05)
		
		#processRX(s.recv(512))
	motorEN = False			# Disable the motors as default
	#sys.exit(0)
	startThreads()	
	
		
def processMidiRX(data): #Process received midi messages from control surface
	global motorEN
	global pMidi
	global MomentaryBP
	
	#print data
	
	if pMidi == False:
		return
		
	if data == MotorENMidi:
		getStatus()
		motorEN = True	
		return
	if data == MotorDISMidi:
		motorEN = False	
		return 
	try:
		command = data[0]
		input = data[1]
		value = data[2]
	except:
		return
		
	m = ''
	for C in Commands:
		MidiCommand = Commands[C]['Midi']
		if MidiCommand['Status'] is None:
			continue
	
		if (MidiCommand['Status'] == str(command)) and (MidiCommand['Param1'] is None or MidiCommand['Param1'] == str(input)):
			
			ClearoneCommand = Commands[C]['Clearone']
			m = '#' + ClearoneCommand['DeviceType'] + ClearoneCommand['DeviceID'] + ' ' + ClearoneCommand['Command'] + ' ' + ClearoneCommand['Channel'] + ' ' + ClearoneCommand['Group']
			
			for i in range(1,5):
				if ClearoneCommand['Values']['_' + str(i)] is None:
					break
				
				###  Value Change ###
				if ClearoneCommand['Values']['_' + str(i)][:2] == '*m':
					if value == 127:
						MomentaryBP = True
						
					break
				
				if ClearoneCommand['Values']['_' + str(i)][:2] == '*v':
					minmax = ClearoneCommand['Values']['_' + str(i)][2:].split(',')
					gain = round(translate(float(value),0,127,float(minmax[0]),float(minmax[1])),1)
					gainInt =  str(gain).split('.')[0]
					gainDec = str(gain).split('.')[1]
					if gainDec == '0':
						gain = gainInt
					else:
						gain = gainInt + '.' + gainDec
					m = m + ' ' + gain
				else:	
					m = m + ' ' + ClearoneCommand['Values']['_' + str(i)]
				### Momentary Button Press ###
				
					
		
	m = m + '\r'
	#print m
		
	telnet(m)
		
				
				
		
	
#Threading is used so there is no need to worry about using non-blocking receive commands and dealing with them.
#One thread for listening for Midi and another for listening for Telnet messages

def midiRX(threadname, dat):   #thread to listen for midi messages
		print "Midi Thread Started"
		while run:   #loop while run is true
			
			msg = midiIn.receive()
			processMidiRX(msg.bytes())
			 
def socketRX(threadname, dat):   #thread to listen to telnet socket messages
		global s
		global pMidi
		print "Telnet Thread Started"
		while run:   #loop while run is true
			try:
				msg = s.recv(512)
				pMidi = False
				processRX(msg)
				pMidi = True
				pass
			except Exception as e: 
				print(e)
				#print "Call Connect"
				s = socket.socket()
				connectClearone()
				processRX(msg)
				
def startThreads():   #Stop the clearone disconnecting the telnet session by making a request every 5 minutes.
	global run
	run = True			#Keeps threads runnning
	try:					#start Threads
		thread.start_new_thread( midiRX, ("mt",True))			
		thread.start_new_thread( socketRX, ("tt", True))
	except:
	   print "Error: unable to start threads"

		
#################################################### Main Pogram Starts Here #############################################################################
connectClearone()  #Connect the clearone
clearBuffer()		#clear the telnet socket buffer
getStatus()			#Get status of clearone and set control surface faders to match

	

#socketRX("t",True)
while True:
	m = '#' + Model + DeviceID + ' VER\r'
	telnet(m)
	sleep(300)

run = False			#this will cause the threads to get to the end
	
s.close()