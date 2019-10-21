import telnetlib 

telnet_timeout = 2

def clearone_login(hostname, username, password):
    device = None
    (output, status) = connect_clearone(hostname, username, password)
    if status == "OK":
        device = output
        (output, status) = authenticate_clearone(username, password, device)
    if device is not None:
            device.close()     
    return (output, status)

def connect_clearone(clearone_ip): 
    device = None
    try:
        device = telnetlib.Telnet(clearone_ip, port=23, timeout=telnet_timeout)
    except Exception as e: 
        return ("Unable to Connect", "CRITICAL")
    return (device, "OK")

def authenticate_clearone(clearone_user, clearone_pass, device):    
    device.read_until("user: ",telnet_timeout)
    login = send_login(device, clearone_user, clearone_pass)
    if not login:
        retry = send_login(device, "clearone", "converge")
        if retry:
            return ("Login Successful, Default Credentials Used","WARNING")
    else:
        return ("Login Successful","OK")    
    return("Could not Authenticate", "UNKNOWN")

def send_login(device, clearone_user, clearone_pass):
    device.write(clearone_user + "\r")
    device.read_until("pass: ",telnet_timeout)
    device.write(clearone_pass + "\r")
    login_response = device.expect(["Invalid", "Authenticated"],telnet_timeout)
    found_index = login_response[0]
    return found_index

def reset_clearone(device):
    device.write("\r#** RESET\r")
    login_response = None
    login_response = device.expect(["RESET"],telnet_timeout)
    if login_response:
        return ("Unit Resetting", "OK")
    return ("Reset command not succesful", "UNKNOWN")