# Midi and Websocket Clearone Control
Control Clearone Converge DSP from any Midi Control Device and Websocket Client.

midicontrol.py - Midi Controller
websockcontrol.py - Websocket Control Server

Run with -h argument to get help output.

"midi" key is optional in config if midi control is not required for a command (websocket use only)

Tested with:
  TouchOSC with TouchOSC Bridge
  Behringer BCF2000
  icon i-controls Pro

Features:
      Ability to auto select midi ports
      Wait for all devices to be present at startup
      Send a list of commands at startup
      Rasberry PI GPIO support if running on a Pi
      Send default Settings
      Configured via a json file
      
Midi Supports:
      Absolute Encoders
      Incremental Encoders
      On/Off push buttons
      Momentary Push Buttons

Websocekt Server
      Json key "command" specifies the command value for clients to send and recevie data about clearone command.  Json value will send in %s position of send command.
      Websocket server responds in same format when an update occurs.
      
Example websocket json payloads:
      
        {  "command" : "program_fader"  , "value" : -3.5  }
        {  "command" : "lectern_mute"  , "value" : 1 }

JSON File Configuration (Descriptors start with #):

        {
            "clearone" : {                    #Clearone specific settings
                "devices" : ["H2", "G1"],     #Device IDs to check for on startup
                "user" : "clearone",          #Clearone Username
                "password" : "converge",      #Clearone Password
                "hostname" : "192.168.1.102", #Clearone Hostname / IP Address
                "startup_commands" : ["#H2 FEDR J 2","#H2 FEDR J 4"]  #Commands to send at startup
            }, 
            "midi_controller" : {         #Midi Specific Settings
                "in_port" :               #Midi In port name, leave this blank and run program to get a list of available ports
                    "iCON iControls_Pro(M) V1.04:iCON iControls_Pro(M) V1.04 MID 20:0",
                "out_port" :               #Midi Out port name, leave this blank and run program to get a list of available ports
                    "iCON iControls_Pro(M) V1.04:iCON iControls_Pro(M) V1.04 MID 20:0"
            },
            "commands" : [            #Clearone command definitions and associated midi commands
                 {              
                    "clearone": {     #Clearone Command Settings
                        "set_command" : "#H2 GAIN A P %s A",      #Command to send when setting a value, substitue the value to change with %s
                        "get_command" : "#H2 GAIN A P",       #Command to send to when querying a setting 
                        "max" : 10,         #Maximum value to send to clearone
                        "min" : -35,        #Minimum value to send to clearone
                        "default" : 0       #Default value to send to clearone on startup
                    },
                    "midi" : {
                        "type" : "absolute",    
                        "status" : 224
                    },
                    "command" : "lectern_fader"  #Websocket command,
                },  
                 {
                    "clearone": {
                        "set_command" : "#H2 MUTE A P %s",
                        "get_command" : "#H2 MUTE A P",
                        "max" : 1,
                        "min" : 0,
                        "default" : 0
                    },
                    "midi" : {
                        "type" : "momentary",
                        "status" : 144,
                        "data" : 16
                    },
                    "command" : "lectern_mute" 
                },
                 {
                    "clearone": {
                        "set_command" : "#H2 MUTE B P %s",
                        "get_command" : "#H2 MUTE B P",
                        "max" : 1,
                        "min" : 0,
                        "default" : 0
                    },
                    "midi" : {
                        "type" : "momentary",
                        "status" : 144,
                        "data" : 17
                    },
                    "command" : "roving_fader"
                },
                 {
                    "clearone": {
                        "set_command" : "#H2 FILTER H P 1 6 20.00 %s 3.70",
                        "get_command" : "#H2 FILTER H P 1",
                        "inc" : 1,
                        "dec" : 127,
                        "step" : 0.5,
                        "max" : 20,
                        "min" :-20,
                        "default" : 0
                    },
                    "midi" : {
                        "type" : "incremental",
                        "status" : 176,
                        "data" : 22
                    } 
            ], 
            "gpio" : [
                 {
                    "in_pin" : 31,
                    "out_pin" : 35,
                    "status" : 144,
                    "data"  : 16
                }
            ]  
        }



