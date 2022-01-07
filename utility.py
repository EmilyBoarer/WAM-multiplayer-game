import notrequests as requests
import socket

def autodetect_games(port = 80):
    """
    returns a list of all the (IP, name)-es of the available WAM servers
    """

    timeout = (0.03, 0.4) # time to establish, time to respond     #these times work reliably for ethernet, but not over wi-fi


    output = [] # stored ip, name pairs found

    myip = socket.gethostbyname(socket.gethostname()) # get current IP

    if myip != "127.0.0.1":# if connect to a network
        first, second, third, forth, = myip.split(".")
        first = int(first)
        second = int(second)
        third = int(third)
        forth = int(forth)

        ips = []
        #generate list of all IP addresses in subnet:
        mask = 24 # TODO get this mask automatically

        shift3 = (2**(32-mask)-1) & 65280
        shift4 = (2**(32-mask)-1) & 255

        for part4 in range(1, (2**(32-mask)-1) & 255 ):
            if shift3 > 0: # mask < 24
                for part3 in range(1, ((2**(32-mask)-1) & 65280) >> 8 ): # this assumes subnet of [16,32)
                    ips.append( str(first)+"."+str(second)+"."+str( part3&shift3 | third&(~shift3) )+"."+str( part4&shift4 | forth&(~shift4) ) ) 
            else: # mask >= 24 and so part 3 will never change so for loop would never be called once
                ips.append( str(first)+"."+str(second)+"."+str(third)+"."+str( part4&shift4 | forth&(~shift4) ) ) 

    else:
        ips = ["127.0.0.1"] # not connected to a network and so only probe localhost once (rather than 254 times)

    # test every IP in the given range and add successful requests to output list
    for ip in ips: 
        # print(f"probing {ip}")
        try:
            response = requests.get(f"{ip}:{port}","/probe", timeout = 0.05)
            name = "INVALID"
            text = response.content # extract text response
            if text.split("@")[0] == "WAMSERVERv02":
                name = text.split("@")[1]
                output.append((ip,name))
        except: # connection times out or other error
            pass # do nothing, this is expected

    return output


if __name__ == "__main__":
    print(autodetect_games())

