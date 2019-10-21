clearone = {
    "device_id" : "1",
    "model" : "G",
    "user" : "clearone",
    "password" : "converge",
    "hostname" : "192.168.1.102"   
}
midi_controller = {
    "in_port" : 
        "iCON iControls_Pro(M) V1.04:iCON iControls_Pro(M) V1.04 MID 20:0",
    "out_port" : 
        "iCON iControls_Pro(M) V1.04:iCON iControls_Pro(M) V1.04 MID 20:0"
}
   
################## FADERS ##################
commands = {
    "_1" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "GAIN A P %s A",
            "max" : "10",
            "min" : "-35",
            "default" : "0"
        },
        "midi" : {
            "status" : 224
        } 
    },
    "_2" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "GAIN B P %s A",
            "max" : "10",
            "min" : "-35",
            "default" : "0"
        },
        "midi" : {
            "status" : 225
        } 
    },
    "_3" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "GAIN C P %s A",
            "max" : "10",
            "min" : "-35",
            "default" : "0"
        },
        "midi" : {
            "status" : 226
        } 
    },
    "_4" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "GAIN D P %s A",
            "max" : "10",
            "min" : "-35",
            "default" : "0"
        },
        "midi" : {
            "status" : 227
        } 
    },
    "_5" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "GAIN E P %s A",
            "max" : "10",
            "min" : "-35",
            "default" : "0"
        },
        "midi" : {
            "status" : 228
        } 
    },
    "_6" : {
        "clearone": {
            "device" : "G1",
            "set_command" : "GAIN 1 F %s A",
            "max" : "10",
            "min" : "-35",
            "default" : "0"
        },
        "midi" : {
            "status" : 229
        } 
    },
    "_9" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "GAIN H P %s A",
            "max" : "10",
            "min" : "-35",
            "default" : "0"
        },
        "midi" : {
            "status" : 232
        } 
    },
################## MUTES ##################        
    "_10" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "MUTE A P %s",
            "get_command" : "MUTE A P",
            "max" : "1",
            "min" : "0",
            "default" : "0"
        },
        "midi" : {
            "status" : 144,
            "param" : 16
        } 
    },
    "_11" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "MUTE B P %s",
            "get_command" : "MUTE B P",
            "max" : "1",
            "min" : "0",
            "default" : "0"
        },
        "midi" : {
            "status" : 144,
            "param" : 17
        } 
    },
    "_12" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "MUTE C P %s",
            "get_command" : "MUTE C P",
            "max" : "1",
            "min" : "0",
            "default" : "0"
        },
        "midi" : {
            "status" : 144,
            "param" : 18
        } 
    },
    "_13" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "MUTE D P %s",
            "get_command" : "MUTE D P",
            "max" : "1",
            "min" : "0",
            "default" : "0"
        },
        "midi" : {
            "status" : 144,
            "param" : 19
        } 
    },
    "_14" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "MUTE E P %s",
            "get_command" : "MUTE E P",
            "max" : "1",
            "min" : "0",
            "default" : "0"
        },
        "midi" : {
            "status" : 144,
            "param" : 20
        } 
    },
    "_15" : {
        "clearone": {
            "device" : "G1",
            "set_command" : "MUTE 1 F %s",
            "get_command" : "MUTE 1 F",
            "max" : "1",
            "min" : "0",
            "default" : "0"
        },
        "midi" : {
            "status" : 144,
            "param" : 21
        } 
    },
################## FILTERS ##################        
    "_16" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "FILTER H P 1 6 20 %s 3.7",
            "get_command" : "FILTER H P 1",
            "inc" : "1",
            "dec" : "127",
            "step" : ",5",
            "default" : "0"
        },
        "midi" : {
            "status" : 176,
            "param" : 22
        } 
    },
    "_17" : {
        "clearone": {
            "device" : "H2",
            "set_command" : "FILTER H P 2 6 20000 %s 3.7",
            "get_command" : "FILTER H P 1",
            "inc" : "1",
            "dec" : "127",
            "step" : ",5",
            "default" : "0"
        },
        "midi" : {
            "status" : 176,
            "param" : 23
        } 
    },  
}
##################  GPIO COMMANDS ##################    
gpio = {
    "_1" : {
        "in_pin" : 31,
        "out_pin" : 35,
        "status" : 144,
        "param"  : 16
    },
    "_2" : {
        "in_pin" : 33,
        "out_pin" : 37,
        "status" : 144,
        "param"  : 17
    },    
}
