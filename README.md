# Midi Clearone Control
Control Clearone Converge DSP from any Midi device.

Tested with:
  TouchOSC with TouchOSC Bridge
  Behringer BCF2000
  icon i-controls Pro

Fully configurable in midi.xml

XML Structure -
ClearOneMidiControl
  - Clearone            #Here all the clearone device settings are stored.  This is the device to establish the telnet connection.  If multiple     clearone devices are connected via the link port they can be addressed in the Commands section by setting the Device ID
    - Communication     # The communications settings for the device to connect to
  - MidiController      # The Midi Control device configuration
    - MotorENMidi       # Assign a button on the midi controller to disable motor feedback. (currently will only operate with toggle buttons)
    - MotorDIS Midi     # Assign a button on the midi controller to enable motor feedback.  (currently will only operate with toggle buttons)
    - MidiPorts         # Set the Midi In and Out ports
 - Commands             # Configure the clearone commands and map to midi device
    -_n                 
