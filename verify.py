def isvalidusername(username):
    if not type(username) is str: # check supplied name is a string
        return False
    allowedchars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_" # all the allowed characters in the username
    if len(username) > 10 or len(username) < 1: # check length of name
        return False
    for char in username:
        if not char in allowedchars: # check to see if each character in username is in the allowed character list
            return False
    return True # it has not been rejected, so must be valid

def isvalidipaddress(ip):
    if not type(ip) is str: # check supplied with string
        return False
    if len(ip.split(".")) != 4: # it must comprise 4 parts when split by "." character as it will be an IPv4 address
        return False
    for part in ip.split("."): # check to see if each part is within range of 0-255 (defined by it being an IPv4 address)
        try:
            if int(part) > 255 or int(part) < 0:
                return False
        except: # cannot parse part to int => it is not a valid address (it consists of something other than numbers and cannot be a valid address)
            return False
    return True # must be valid

def isvalidusername_ongoing(username): # this function will be run as each character of the username is typed in so cannot check minimum length
    if not type(username) is str: # check supplied with string
        return False
    allowedchars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_" # all the allowed characters in the username
    if len(username) > 10: # check length of name is less than 10
        return False
    for char in username: # check it consists of allowed characters only
        if not char in allowedchars:
            return False
    return True

def isvalidipaddress_ongoing(ip): # this function will be run as each character of the address is typed in and so cannot test for entire address, rather just allowed characters
    if not type(ip) is str: # check supplied with string
        return False
    allowedchars = "0123456789."
    for char in ip: # check it consists of allowed characters only
        if not char in allowedchars:
            return False
    return True