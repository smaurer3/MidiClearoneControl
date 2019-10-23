import mido
        
from time import sleep
import thread
import sys
import RPi.GPIO as GPIO
import clearone as clearone_lib
from settings import clearone
from settings import midi_controller
from settings import commands
from settings import gpio

ERRORS = {
    "OK" : 0,
    "WARNING" : 1,
    "CRITICAL" : 2,
    "UNKNOWN" : 3
}


CLEARONE = clearone_lib(
                    clearone['hostname'],
                    clearone['user'],
                    clearone['password']
                    )

def main():
    open_midi()
    gpio_setup()
    (status,output) = CLEARONE.login()
    if status:
        print("Clearone Login Success")
    else:
        print("Could not Connect to clearone: %s" % output)
        sys.exit(ERRORS['CRITICAL'])
    
    

def open_midi():
	try:
		midi_in = mido.open_input(midi_controller["in_port"])
		midi_out = mido.open_output(midi_controller["out_port"])
		return (midi_in, midi_out)
	except:
		list_midi_ports()
		sys.exit(ERRORS["CRITICAL"])

def list_midi_ports():
		print ("Invalid Midi Port\n" + "-"*40 + "\n\nAvailable Input Ports:\n")
		_in = mido.get_input_names()
		out = mido.get_output_names()
		for p in mido.get_input_names():
			print p
		print ("\n" + "-"*40 + "\nAvailable Output Ports:\n")
		for p in mido.get_output_names():
			print p
		print (
      			"\n" + "-"*40 + "\nEnsure midi device is connected\n"
        	   	"\nChange midi ports in  settings.py\n"
             )
def gpio_setup():
	for C in gpio:
		GPIO.setup(int(gpio[C]['in_pin']), GPIO.IN, pull_up_down=GPIO.PUD_DOWN)	
		GPIO.setup(int(gpio[C]['out_pin']), GPIO.OUT)	
		GPIO.output(int(gpio[C]['out_pin']), 1)


