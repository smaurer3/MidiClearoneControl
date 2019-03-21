#!/usr/bin/env python

# This program is to control a Clearone Converge DSP using a Midi Control Surface
#
# Midi Controller motors can be disabled or enabled by mapping button in the XML
#
# All Configuration is done in midi.xml
# 
# Make sure you have a backup of the Clearone Configuration.
#
#  4 types of variables can be changed:
#		*v - the standard type used by most faders, toggle buttons and absolute encoders.  Format is *v , minimum value , maximum value, eg. *v-65,20 a toggle would be *v0,1
#			 This is all you need for the Behringer BCF2000 and TouchOSC, the next 2 a needed for the icon i-Control pro and possible other controllers we haven't tested.
#		*m - the type used for momentary button, eg buttons that send an on when pushed and off when released, these can alternate between 2 values	
#			 format is *m , off value , on value eg. *m0,1
#		*e - the type used for incremental encoders when you need to change and absolute value.  Format is *e, increment midi value, decrement midi value, increment step, decrement step
#			 eg. *e1,127,.5,-.5
#		*f - this is for values that presents before the value we want to change (the *v, *e, *m value) and not requried when querying the clearone for the value.
#			 This is so the program knows not to send it if request just for status.
#
#	Known Limitations:
#		- 	Can only send commands that need a channel and group argument.  Example, GMODE can't be sent as it doesn't have the group included in it, you can use XGMODE instead as this 
#			has the Channel and Group.

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
	print "\n---------------------------------------\nEnsure midi device is connected\n\nChange midi ports in  midi.xml\n\n\n\n\n"
	sys.exit(0)
# Send the Motor Disable message to the midi device
msg = mido.parse(MotorDISMidi)	
midiOut.send(msg)

motorEN = False  #Global variable for enabling motors
run = False
pMidi = True	
MomentaryBP = False
minmax = ''
Encoder = False
ec = []

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
	#Find / wait for the user prompt then enter the username
	while s.recv(512).find('user') < 0:
		pass
	s.send(clearoneUser + "\r")
	#find / wait for the pass prompt then enter password
	while s.recv(512).find('pass') < 0:
		pass
	s.send(clearonePass + "\r")
	
	#confirm login was successful, otherwise exit program
	while s.recv(512).find('Authenticated') < 0:
		if s.recv(512).find('Invalid') < 0:
			print "Invalid User/Pass." 
			sys.exit(0)
		pass
	print "Login Succesful"	
	return s

def telnet(data):   #Send data to clearone via telnet, attempts to re-connect if there is a problem.
	global s
	print "telnet: " + data
	try:
		s.send(data)
	except Exception as e: 
		print(e)
		s = socket.socket()
		connectClearone()
		s.send(data)

def createMidi(Status, value, Param1):  #Convert midi bytes to midi command for mido to send
	
	if Param1 == '':
		Param1 = value
	msg = mido.parse([int(Status), int(Param1), value])  #generate and send the midi message
	print msg
	return msg
			
def processRX(data):   #Process data received from clearone via telnet and translate and pass to midi controller
	global motorEN
	global MomentaryBP
	global minmax
	global Encoder
	global ec
	print "Received: " + data
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
		#Check if cureny command recieved from clearone matches command in xml, if match process it.
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

			try:
				if MidiCommand['Param1'] is None:
					midiOut.send(createMidi(MidiCommand['Status'], value, ''))
				else:
					midiOut.send(createMidi(MidiCommand['Status'], value, MidiCommand['Param1']))
				return
			except: #An error will occur if it is a *e and the value goes out of range (0-127), the map function won't work properly because it doesn't know the min and max values
					#At the moment this is something that can be lived with because the encoders on the icon don't have any feedback and that is the only thing that can trigger this fault.
				print "MIDI Command Creation Error, proably using an incremental encoder and the value is negative: VALUE=" + str(value)
	

				
				
def getStatus():  #Get the stus of the clearone and sets the Midi Control Surface to match, runs at start up
	global motorEN
	global run
	motorEN = True
	run = False
	for C in Commands:
		MidiCommand = Commands[C]['Clearone']
		
		if MidiCommand['DeviceType'] is None:
			continue
		if MidiCommand['Group'] is None:
			MidiCommand['Group'] = ''
 
		m = '#' + MidiCommand['DeviceType'] + MidiCommand['DeviceID'] + ' ' + MidiCommand['Command'] + ' ' + MidiCommand['Channel'] + ' ' + MidiCommand['Group']
		
		for i in MidiCommand['Values']:
			if MidiCommand['Values'][i][:2] == '*v' or MidiCommand['Values'][i][:2] == '*m' or MidiCommand['Values'][i][:2] == '*f' or MidiCommand['Values'][i][:2] == '*e':
				break
			m = m + ' ' + MidiCommand['Values'][i]

		m = m + '\r'
		telnet(m)
		sleep(.05)
		
		processRX(s.recv(512))
	#motorEN = False			# Disable the motors as default
	#sys.exit(0)
	
	
		
def processMidiRX(data): #Process received midi messages from control surface
	global motorEN
	global pMidi
	global MomentaryBP
	global Encoder
	global minmax
	global ec
	print data
	
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
	for C in Commands:  #iterate through the commands in the xml and try to match the midi bytes to what was sent.
		MidiCommand = Commands[C]['Midi']
		if MidiCommand['Status'] is None:
			continue
	
		if (MidiCommand['Status'] == str(command)) and (MidiCommand['Param1'] is None or MidiCommand['Param1'] == str(input)): #matching the midi bytes to what is in the xml
			
			ClearoneCommand = Commands[C]['Clearone']
			#m is the variable used to build the command to send to the clearone
			m = '#' + ClearoneCommand['DeviceType'] + ClearoneCommand['DeviceID'] + ' ' + ClearoneCommand['Command'] + ' ' + ClearoneCommand['Channel'] + ' ' + ClearoneCommand['Group']
			#e is the temp variable to stop building the command if a *f is encountered, it is used if an incremental encoder is used to adjust a value.
			e = m
			#f indicates if a *f value has been encountered.
			f = False
			for i in ClearoneCommand['Values']:  #iterate through the values key with the xml
				if ClearoneCommand['Values'][i] is None: #if it encounters a blank key stop iterating
					break
				
				if not f:  # while *f hasn't been encountered e should continue to be the same as m
						e = m
				###  Value Change ###
				minmax = ClearoneCommand['Values'][i][2:].split(',')
				
				if ClearoneCommand['Values'][i][:2] == '*m':  # Midi button controlling this is a momentary button
					if value == 127:
						MomentaryBP = True	
					break
					
				if ClearoneCommand['Values'][i][:2] == '*e': # Midi control for this is an encoder
					 #not truly minmax, this becomes the *e..... list 
					Encoder = True
					if value == int(minmax[0]):
						ec.append(minmax[2])   #ec is a list for the encoder commands, first is the incremental value, followed by a dictionary of the values for the current command.
						#ec is so that when the command is processed from the clearone the values for sending the update command are known.
					if value == int(minmax[1]):
						ec.append(minmax[3])
					ec.append(ClearoneCommand['Values'])  #append the valus dictionay to the ec list.
					m = e
					break
				
				if ClearoneCommand['Values'][i][:2] == '*f':	# A value that does not need to be sent when requesting current values.
					f = True
					m = m + ' ' + ClearoneCommand['Values'][i][2:]  #if a *f is encountered add everything after the *f to the m string.  Now that f is true, e will stop updating to m.
					continue
					
				if ClearoneCommand['Values'][i][:2] == '*v':	# the Variable that needs to be changed in the string
					minmax = ClearoneCommand['Values'][i][2:].split(',') #get the min and max values for the clearone command
					gain = round(translate(float(value),0,127,float(minmax[0]),float(minmax[1])),1)   #map the min and max to 0 - 127 for midi usage
					# As we are dealing with a rounded float, it will always have a decimal even if it's a whole number (1.0).  The following removes the decimal if
					# the value is a whole number, this is so the same funcation can be used for toggles such as mutes and gate and these commands don't have decimals and 
					# the clearone would throw an error if we sent it a decimal.
					gainInt =  str(gain).split('.')[0]		
					gainDec = str(gain).split('.')[1]    
					if gainDec == '0':
						gain = gainInt
					else:
						gain = gainInt + '.' + gainDec
					m = m + ' ' + gain
				else:	
					m = m + ' ' + ClearoneCommand['Values'][i]
				### Momentary Button Press ###
				
					
		
	m = m + '\r'

		
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
				#pMidi = False
				processRX(msg)
				#pMidi = True
				pass
			except Exception as e: 
				print(e)
				
				s = socket.socket()
				connectClearone()
				processRX(msg)
				
def startThreads(): 
	global run
	run = True			#Keeps threads runnning
	try:					#start Threads
		thread.start_new_thread( midiRX, ("mt",True))			
		thread.start_new_thread( socketRX, ("tt", True))
	except:
	   print "Error: unable to start threads"

		
#################################################### Main Pogram Starts Here #############################################################################

connectClearone()  #Connect the clearone
#clearBuffer()		#clear the telnet socket buffer, not sure if this is nesscesary
getStatus()			#Get status of clearone and set control surface faders to match
startThreads()	
	

#socketRX("t",True)
while True:    #Stop the clearone disconnecting the telnet session by making a request every 5 minutes.
	m = '#' + Model + DeviceID + ' VER\r'
	telnet(m)
	sleep(300)

run = False			#this will cause the threads to get to the end
	
s.close()