import socket

class clearone:
    def __init__(self, device):
        self.telnet_timeout = 2
        self.telnet_port = 23
        self.device = None
        self.hostname = device[0]
        self.username = device[1]
        self.password = device[2]
        self.login()
        

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
            return ( False, "Could not Authenticate to Clearone")
        return (True, "Connected and Login Succesful")

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