#Copyright (c) Emily Boarer 2020-2021
#some ideas (not all terrible) from Joe Avery (and POG edit (texture))


#this is the main file that is run when the game is launched, this launches everything else

import pygame
import menu
import verify
import time
import utility
import threading
import getpass
import multiprocessing
import notrequests
import socket
import os
from zipfile import ZipFile
import shutil

import server
import client


def runserver(name, public, port, pipe): # this has to be out of any class to work
    # the whole server is seperated into a seperate process
    # need to inform that can now go to username screen
    pipe.send("process loaded")
    pipe.close()
    s = server.Server(name, public, port)


keychars = { # a list of all the keys that can be pressed in an input box, in key ID and character pairs
    pygame.K_q: "q",
    pygame.K_w: "w",
    pygame.K_e: "e",
    pygame.K_r: "r",
    pygame.K_t: "t",
    pygame.K_y: "y",
    pygame.K_u: "u",
    pygame.K_i: "i",
    pygame.K_o: "o",
    pygame.K_p: "p",
    pygame.K_a: "a",
    pygame.K_s: "s",
    pygame.K_d: "d",
    pygame.K_f: "f",
    pygame.K_g: "g",
    pygame.K_h: "h",
    pygame.K_j: "j",
    pygame.K_k: "k",
    pygame.K_l: "l",
    pygame.K_z: "z",
    pygame.K_x: "x",
    pygame.K_c: "c",
    pygame.K_v: "v",
    pygame.K_b: "b",
    pygame.K_n: "n",
    pygame.K_m: "m",
    pygame.K_SPACE: " ",
    pygame.K_UNDERSCORE: "_",
    pygame.K_MINUS: "_", # TODO figure out why pygame does not detect underscore as a character that is being pressed??
    pygame.K_PERIOD: ".",
    pygame.K_0: "0",
    pygame.K_1: "1",
    pygame.K_2: "2",
    pygame.K_3: "3",
    pygame.K_4: "4",
    pygame.K_5: "5",
    pygame.K_6: "6",
    pygame.K_7: "7",
    pygame.K_8: "8",
    pygame.K_9: "9",
    pygame.K_KP0: "0", # num pad numbers (key pad)
    pygame.K_KP1: "1",
    pygame.K_KP2: "2",
    pygame.K_KP3: "3",
    pygame.K_KP4: "4",
    pygame.K_KP5: "5",
    pygame.K_KP6: "6",
    pygame.K_KP7: "7",
    pygame.K_KP8: "8",
    pygame.K_KP9: "9",
    pygame.K_KP_PERIOD: ".",
    # pygame.K_BACKSPACE: "BACKSPACE",
}

class GameController:
    # functions for menu buttons specfically:
    def quit(self, value = None): # exit the game
        self.running = False # cause main game loop to be exited
    
    # these functions will be properly filled out in a later iteration
    def joinmultiplayergame(self, value = None): # called on main menu screen
        self.menu.goto_menuscreen(menu.MenuState.connect)
        # set autoscanning for games running
        thread = threading.Thread(target=self.updateautodiscoveredgames)
        thread.start()

        #if the current things in the screen are games, then they need to be discarded and replaces with a message to inform the player that it is scanning
        self.menu.crop_state(menu.MenuState.connect, 8) # get rid of last things to make 8 long
        
        self.menu.addtextcomponent(menu.MenuState.connect, "Scanning for games...", 10)
        self.menu.addtextcomponent(menu.MenuState.connect, "[please wait]", 7)
        self.menu.addpaddingcomponent(menu.MenuState.connect, 100)

    def updateautodiscoveredgames(self): # this is the threaded function
        pairs = utility.autodetect_games() # run the scanner
        self.autogames = {} # stores name: ip pairs for lookup later when button pressed
        self.menu.crop_state(menu.MenuState.connect, 8) # get rid of last things to make 8 long
        if len(pairs) > 0: #games were found
            self.menu.addtextcomponent(menu.MenuState.connect, "Autodiscovered games:", 10)
            for ip, name in pairs:
                self.autogames[name] = ip # add entry to dictionary
                self.menu.addbuttoncomponent(
                    menu.MenuState.connect, 
                    name, # name of the game is the button text
                    10, 
                    function=self.connecttoautodiscoveredgame
                    )
        else: # no games found
            self.menu.addtextcomponent(menu.MenuState.connect, "No games were found :(", 10)
        self.menu.addpaddingcomponent(menu.MenuState.connect, 100)
        #update screen
        self.menu.needtorender = True
        
    def connecttoautodiscoveredgame(self, value = None): # called form connect screen
        print(value)
        print(self.autogames[value]) # should be found IP address to save for later
        #create clients and connect to address
        self.spawn_clients(serverip = self.autogames[value])

        self.getusername() # go to username screen
            
        #TODO check server exists before connecting??
       

    def hostmultiplayergame(self, value = None): # called on main menu screen
        try:
            response = notrequests.get(f"{socket.gethostbyname(socket.gethostname())}:{self.gameport}","/probe", timeout = 0.1)
            self.menu.goto_menuscreen(menu.MenuState.singleplayererror, selectionID = 0)
        except: # timeout
            #launch server and then connect client to it
            self.remove_all_clients() # remove anything that is still running in the background before starting again
            username = getpass.getuser() # this gets the local account username
            self.start_server(name = username+"'s Game", public = True, port = self.gameport)
            
            self.spawn_clients(serverip = socket.gethostbyname(socket.gethostname())) #inputmethod stores number of controller inputs
            
            self.getusername()
            

    def singleplayergame(self, value = None): # called on main menu screen
        #first, check that there is not already a game hosted locally, because if it is not tied to this instance of the game then it should NOT be shut down
        try:
            response = notrequests.get(f"{socket.gethostbyname(socket.gethostname())}:{self.gameport}","/probe", timeout = 0.1)
            # print(str(response.content))
            # if str(response.content)[:13] == "WAMSERVERv02@":
            #     # do not shut down, one already exists
            #     print("Game already hosted on current device and so singleplayer is unavailable") # TODO send proper error
            self.menu.goto_menuscreen(menu.MenuState.singleplayererror, selectionID = 0)
                # return # cause the rest of the function to be ignored and so not run
        except: # timeout
            #pass # server non-existent

            #launch private server then connect
            self.remove_all_clients() # remove anything that is still running in the background before starting again
            self.start_server(name = "Local Private Game (This device only)", public = False, port = self.gameport)
            
            self.spawn_clients(serverip = socket.gethostbyname(socket.gethostname())) #inputmethod stores number of controller inputs
                
            self.getusername()

    def setfullscreen(self, value=None): # value is the text of theh button pressed
        self.screen = pygame.display.set_mode((self.displayx, self.displayy), pygame.FULLSCREEN) # re-initialise screen to fullscreen
        if self.ingame: # update clients
            for c in self.clients:
                c.resize(self.displayx//self.scale//len(self.clients), self.displayy//self.scale)
        else: # update menu system
            self.menu.resize(self.displayx//self.scale, self.displayy//self.scale)
        self.Fullscreen = True

    def setwindowed(self, value=None):
        self.screen = pygame.display.set_mode((self.windowedx, self.windowedy),pygame.RESIZABLE) # re-initialise screen to windowed resizable
        if self.ingame: # update clients
            for c in self.clients:
                c.resize(self.windowedx//self.scale//len(self.clients), self.windowedy//self.scale)
        else: # update menu system
            self.menu.resize(self.windowedx//self.scale, self.windowedy//self.scale)
        self.Fullscreen = False

    def cycleinput(self, value):# value is the text of theh button pressed
        self.inputmethod = ["Input: Keyboard & Mouse","Input: Keyboard & Mouse, Controller (splitscreen)","Input: Controller", "Input: 2x Controller (spltiscreen)"].index(value) - 1 # subtract 1 means that -1 = keyboard, 0 = k/c splitscreen, 1onwards = controller count

    def changescaling(self, value):
        # value is the text of theh button pressed
        #will be in the form "scaling: 1x"
        #get the 1x, then remove 1/ and convert to int
        factor = int(value.split(" ")[1].split("/")[1])
        self.scale = factor
        if self.Fullscreen:
            self.setfullscreen() # cause display to update with new scale
        else:
            self.setwindowed()

        #input scaling means that the game thinks it is running at 1/factor 
        # the resolution of the actual screen area filled by the game, and 
        # then after everything is rendered it is scaled to fit the screen 
        # area. this saves resources and gives a higher frame rate but with 
        # the same area of the screen still occupied - resolution can be 
        # decreased without forfeiting physical size!

    def changetexturepack(self, value): # value = f"Texturepack: {name}"
        name = value[13:]
        self.load_texturepack(name)

        #TODO load all texturepacks when starting the game to be the options in the cyclet
        #TODO load_texturepack with default when first launching the games

    def get_list_of_texturepacks(self):
        names = ["Default"] # this has to be first, because it is the default
        with os.scandir("Texturepacks") as dirs:
            for entry in dirs:
                if entry.name[-8:] == ".txtpack" and entry.name != "Default.txtpack":
                    names.append(entry.name[:-8])
        return names
        
    def load_texturepack(self, name):
        if os.path.isfile(f"Texturepacks{os.sep}{name}.txtpack"):
            print(f"loading texturepack Texturepacks{os.sep}{name}.txtpack")
            #only load if exists / validation
            #remove existing textures folder
            if os.path.isdir(f"Texturepacks{os.sep}loadedtextures"):
                shutil.rmtree(f"Texturepacks{os.sep}loadedtextures")
            #extract to textures folder  
            with ZipFile(f"Texturepacks{os.sep}{name}.txtpack", "r") as zipObj:
                zipObj.extractall(f"Texturepacks{os.sep}loadedtextures")

    def backtomainmenu(self, value = None): # called on connect screen (autodiscover) 
        self.remove_all_clients()
        self.menu.goto_menuscreen(menu.MenuState.main)

    def backtomainmenufromerror(self, value = None):
        self.menu.goto_menuscreen(menu.MenuState.main)

    def directconnect(self, value = None): # called on connect screen (autodiscover) 
        self.menu.goto_menuscreen(menu.MenuState.directconnect)

    def backfromdirect(self, value = None): # called on direct connect screen
        self.remove_all_clients()
        self.menu.goto_menuscreen(menu.MenuState.connect)
        #TODO reset text box in directconnect screen
    
    def connecttogame(self, value = None): # called from direct connect screen join button
        #the input box is index 7
        IP, valid = self.menu.components[menu.MenuState.directconnect][7].getinput() # get the contents and validity of the IP text box
        if IP == "127.0.0.1": IP = socket.gethostbyname(socket.gethostname()) # change to this IP (needed for the WSGIserver)
        if valid: # only if the input is valid, proceed
            #TODO store IP address for later (once server written)
            self.getusername() # go to username screen
            #start clients
            self.spawn_clients(serverip = IP) #inputmethod stores number of controller inputs
                

    def backfromname(self, value = None): # called on enter username screen
        self.menu.goto_menuscreen(menu.MenuState.main)
        self.remove_all_clients()
        #remove only this game's servers
        self.terminate_processes()

    def getusername(self): # special function because multiple others link to username prompt, and since dynamic box, it should have a function so the code is all in one place
        #create menu screen with appropriate counter so the players know what name they are entering
        if len(self.clients) > 1:#multiplayer => update the screen
            count = 1
            for c in self.clients:
                if not c.ingame: # need to get details // construct for this user
                    #reconstruct the menu
                    self.menu.crop_state(menu.MenuState.name, 6) # get rid of last things to make 6 long

                    self.menu.addtextcomponent(menu.MenuState.name, "Username for player "+str(count)+":", 10)
                    self.menu.addinputcomponent(menu.MenuState.name, 15, emptycovertext="Enter Username here") # this will use default validation functions of the username
                    self.menu.addpaddingcomponent(menu.MenuState.name, 5)
                    self.menu.addbuttoncomponent(menu.MenuState.name, "Submit & Join Game", 10, function=self.usernamesubmit)
                    self.menu.addpaddingcomponent(menu.MenuState.name, 100)
                    
                    break
                count += 1
        else: # this needs to be reset (mostly here if played splitscreen game and then wants to do singleplayer, so it willl revert back to defualt text)
            self.menu.crop_state(menu.MenuState.name, 6) # get rid of last things to make 6 long
            
            self.menu.addtextcomponent(menu.MenuState.name, "Username:", 10)
            self.menu.addinputcomponent(menu.MenuState.name, 15, emptycovertext="Enter Username here") # this will use default validation functions of the username
            self.menu.addpaddingcomponent(menu.MenuState.name, 5)
            self.menu.addbuttoncomponent(menu.MenuState.name, "Submit & Join Game", 10, function=self.usernamesubmit)
            self.menu.addpaddingcomponent(menu.MenuState.name, 100)
        #now go to newly generated screen
        self.menu.goto_menuscreen(menu.MenuState.name)


    def usernamesubmit(self, value = None):# called on enter username screen
        #the input box is index 7
        name, valid = self.menu.components[menu.MenuState.name][7].getinput() # get the contents and validity of the username text box
        if valid: # only if the input is valid, proceed
            #because of how the text box is generated, this will be the first client in self.clients's username
            for c in self.clients:
                if not c.ingame:
                    success = c.join(name) # attempt to join
                    if success:
                        #go to client screen if all users in game
                        finished = True
                        for innerc in self.clients:
                            if innerc.ingame == False:
                                finished = False
                        if finished:
                            self.set_ingame()
                        #else get other users info
                        else:   
                            self.getusername() # get next user
                    else:
                        #set invalid so give the user feedback that it has failed to let them in
                        self.menu.components[menu.MenuState.name][7].set_invalid()
                    break # do not check any other users

    #these are called from the are you sure you want to leave menu:
    def leavegame_leave(self, value = None):    
        self.remove_all_clients()
        self.menu.goto_menuscreen(menu.MenuState.main)
        #remove only local server if there
        self.terminate_processes()
    
    def leavegame_stay(self, value = None):
        self.set_ingame() # go back to the game

    def enterhelpscreen(self, value):
        self.menu.goto_menuscreen(menu.MenuState.help, selectionID = 0)

    # rest of methods:

    def spawn_clients(self, serverip):
        
        if self.inputmethod == -1: # keyboard 
            count = 1
        elif self.inputmethod == 0: # keyboard & controller splitscreen
            count = 2
        else: # controllers
            count = self.inputmethod

        if len(self.clients) == 0: # validating that no clients already exist before creating new ones
            self.clients = [] # make empty list

        if count == 0 or count >= 2:
            width, height = self.windowedx//2, self.windowedy # TODO make the resolution adjust properly
            for _ in range(2):
                self.clients.append(client.Client(serverip, self.gameport, self, width, height))
        else:
            width, height = self.windowedx, self.windowedy # TODO make the resolution adjust properly
            self.clients.append(client.Client(serverip, self.gameport, self, width, height))
                
    def start_server(self, name, public, port):
        # make sure there is no server still running
        self.remove_all_servers()

        #start server
        self.server = True
        this_conn, that_conn = multiprocessing.Pipe()
        #save process so it can be terminaed later
        self.serverproc = multiprocessing.Process(target = runserver, args=(name, public, port, that_conn))
        #name the process
        if public:
            self.serverproc.name = "War Against Memes Public Server"
        else:
            self.serverproc.name = "War Against Memes Private Local Server"
        #start the process
        self.serverproc.start()
        #check the server process has started, this will make the program freeze until the secondary process has loaded
        this_conn.recv()


    def remove_all_servers_and_clients(self):
        self.remove_all_clients()
        self.remove_all_servers()
    
    def remove_all_clients(self):
        #end all clients
        for c in self.clients:
            if type(c) is client.Client:
                c.stop()
        self.clients = []
        
    def remove_all_servers(self):
        if self.server == True:
            try: # attempt to make it close smoothly if possible
                response = notrequests.put(f"{socket.gethostbyname(socket.gethostname())}:{self.gameport}","/shutdown", timeout=1)

            except:
                pass
            self.terminate_processes()

    def terminate_processes(self):
        print("terminating server")
        if type(self.serverproc) is multiprocessing.Process:
            self.serverproc.terminate()
            self.serverproc.join()
            self.server = None

        #need to get clients to leave before server shutsdown

    def set_ingame(self):
        self.ingame = True
        # causes appropriate screen components to resize if needed
        if self.Fullscreen:
            self.setfullscreen() # trigger update
        else:
            self.setwindowed() 
        pygame.mouse.set_visible(False)
    def set_inmenu(self):
        self.ingame = False
        # causes appropriate screen components to resize if needed
        if self.Fullscreen:
            self.setfullscreen() # trigger update
        else:
            self.setwindowed()
        pygame.mouse.set_visible(True)

    def clients_kicked_goto_main_menu(self):
        #this is called when the server cannot be reached and so the client must have been kicked (either intentionally or unintentionally by the server)
        #reset the game back 
        self.RESET = True
        self.quit()


    def __init__(self):
        self.RESET = False
        self.gameport = 80
        self.server = None
        self.clients = []
        self.serverproc = None

        self.ingame = False # True if in game (render clients and channel input there), if False, then render and give input to menu system

        pygame.init()
        pygame.joystick.init() # for controllers
        pygame.font.init()
        self.buttontime = 0
        self.buttonwaittime = 0.3 # seconds

        self.keytime = 0            #will hold the time the the key was last pressed
        self.keywaittime = 0.1      #how many seconds need to elapse before pressing the same key again

        self.windowedx = 1000
        self.windowedy = 500

        #resolution of the monitor
        self.displayx = pygame.display.Info().current_w # set the display to be the size of the monitor as reported by pygame
        self.displayy = pygame.display.Info().current_h
        
        self.scale = 1

        self.Fullscreen = False 

        self.inputbox = None
                
        # set up the window
        if self.Fullscreen:
            self.screen = pygame.display.set_mode((self.displayx, self.displayy), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((self.windowedx, self.windowedy))

    def run(self): 

        #load default texturepack
        self.load_texturepack("Default")

        clock = pygame.time.Clock()

        # set icon
        pygame.display.set_icon(pygame.image.load(f"defaults{os.sep}WAM_icon_dev.png"))

        self.menu = menu.Menu(self, self.displayx, self.displayy, menu.MenuState.main)

        #determine what input options are available to the game
        inputtypes = ["Input: Keyboard & Mouse"] # no controller, only keyboard
        if pygame.joystick.get_count() > 0: # at least 1 controller
            inputtypes.append("Input: Keyboard & Mouse, Controller (splitscreen)")
            inputtypes.append("Input: Controller")
        if pygame.joystick.get_count() > 1: # at least 2 controllers
            inputtypes.append("Input: 2x Controller (spltiscreen)")

        self.inputmethod = -1 # -1=keyboard, 0=keyboard and controller splitscreen, anything else is no.controllers

        # init all controllers:
        self.controllers = []
        for ID in range(pygame.joystick.get_count()):
            self.controllers.append(pygame.joystick.Joystick(ID))
            self.controllers[-1].init()
        
        axis, a, b = 0, 0, 0  # this is here in case no controller is present it won't crash menu navigating

        #define the menu structure
        version = "65 - Open Source Release"
        subtitle = f"Alpha: Iteration {version} - Copyright Emily Boarer 2021"

        #main menu
        self.menu.addpaddingcomponent(menu.MenuState.main, 18)
        self.menu.addtextcomponent(menu.MenuState.main, "War Against Memes", 20)
        self.menu.addtextcomponent(menu.MenuState.main, subtitle, 5)
        self.menu.addpaddingcomponent(menu.MenuState.main, 5)
        self.menu.addbuttoncomponent(menu.MenuState.main, "Exit Game", 7, centred = False, function=self.quit) 
        self.menu.addpaddingcomponent(menu.MenuState.main, 18)
        self.menu.addbuttoncomponent(menu.MenuState.main, "Join Multiplayer Game", 12, function=self.joinmultiplayergame)
        self.menu.addpaddingcomponent(menu.MenuState.main, 5)
        self.menu.addbuttoncomponent(menu.MenuState.main, "Host Multiplayer Game", 12, function=self.hostmultiplayergame)
        self.menu.addpaddingcomponent(menu.MenuState.main, 5)
        self.menu.addbuttoncomponent(menu.MenuState.main, "Singleplayer Game", 12, function=self.singleplayergame)
        self.menu.addpaddingcomponent(menu.MenuState.main, 13)
        self.menu.addtextcomponent(menu.MenuState.main, "Settings: [Click to toggle]", 5, centred=False)
        self.menu.addcyclercomponent(menu.MenuState.main, inputtypes, 10, centred = False, functions = [self.cycleinput for _ in range(len(inputtypes))]) # generate this to match what is in the input types list
        self.menu.addcyclercomponent(menu.MenuState.main,["Toggle Video: Windowed","Toggle Video: Fullscreen"], 10, centred = False, functions = [self.setwindowed, self.setfullscreen])
        self.menu.addcyclercomponent(menu.MenuState.main,["Scaling: 1/1","Scaling: 1/2","Scaling: 1/3","Scaling: 1/4","Scaling: 1/5"], 10, centred = False, functions = [self.changescaling, self.changescaling, self.changescaling, self.changescaling, self.changescaling])
        packs = self.get_list_of_texturepacks()
        self.menu.addcyclercomponent(menu.MenuState.main,[f"Texturepack: {name}" for name in packs], 10, centred = False, functions = [self.changetexturepack for _ in range(len(packs))])
        self.menu.addpaddingcomponent(menu.MenuState.main, 20)
        
        #Connect (autodetect screen)
        self.menu.addpaddingcomponent(menu.MenuState.connect, 18)
        self.menu.addtextcomponent(menu.MenuState.connect, "War Against Memes", 20)
        self.menu.addtextcomponent(menu.MenuState.connect, subtitle, 5)
        self.menu.addpaddingcomponent(menu.MenuState.connect, 5)
        self.menu.addbuttoncomponent(menu.MenuState.connect, "Back", 7, centred = False, function=self.backtomainmenu) 
        self.menu.addpaddingcomponent(menu.MenuState.connect, 18)
        self.menu.addbuttoncomponent(menu.MenuState.connect, "Direct Connect to an IP", 10, function=self.directconnect)
        self.menu.addpaddingcomponent(menu.MenuState.connect, 10)

        #Direct Connect
        self.menu.addpaddingcomponent(menu.MenuState.directconnect, 18)
        self.menu.addtextcomponent(menu.MenuState.directconnect, "War Against Memes", 20)
        self.menu.addtextcomponent(menu.MenuState.directconnect, subtitle, 5)
        self.menu.addpaddingcomponent(menu.MenuState.directconnect, 5)
        self.menu.addbuttoncomponent(menu.MenuState.directconnect, "Back", 7, centred = False, function=self.backfromdirect) 
        self.menu.addpaddingcomponent(menu.MenuState.directconnect, 18)
        self.menu.addtextcomponent(menu.MenuState.directconnect, "Address:", 10)
        self.menu.addinputcomponent(menu.MenuState.directconnect, 15, emptycovertext="Enter IP address here", validationfunc=verify.isvalidipaddress, ongoingvalidationfunc=verify.isvalidipaddress_ongoing)
        self.menu.addpaddingcomponent(menu.MenuState.directconnect, 5)
        self.menu.addbuttoncomponent(menu.MenuState.directconnect, "Submit", 10, function=self.connecttogame)
        self.menu.addpaddingcomponent(menu.MenuState.directconnect, 100)

        #Enter username
        self.menu.addpaddingcomponent(menu.MenuState.name, 18)
        self.menu.addtextcomponent(menu.MenuState.name, "War Against Memes", 20)
        self.menu.addtextcomponent(menu.MenuState.name, subtitle, 5)
        self.menu.addpaddingcomponent(menu.MenuState.name, 5)
        self.menu.addbuttoncomponent(menu.MenuState.name, "Back", 7, centred = False, function=self.backfromname) 
        self.menu.addpaddingcomponent(menu.MenuState.name, 18)
        #the rest of this menu is declared in self.getusername()

        #Are you sure you want to quit
        self.menu.addpaddingcomponent(menu.MenuState.leavegame, 18)
        self.menu.addtextcomponent(menu.MenuState.leavegame, "War Against Memes", 20)
        self.menu.addtextcomponent(menu.MenuState.leavegame, subtitle, 5)
        self.menu.addpaddingcomponent(menu.MenuState.leavegame, 10)
        self.menu.addtextcomponent(menu.MenuState.leavegame, "Are you sure you want to", 11)
        self.menu.addtextcomponent(menu.MenuState.leavegame, "leave the game?", 11)
        self.menu.addpaddingcomponent(menu.MenuState.leavegame, 18)
        self.menu.addbuttoncomponent(menu.MenuState.leavegame, "Yes, quit to main menu", 10, function=self.leavegame_leave) 
        self.menu.addtextcomponent(menu.MenuState.leavegame, "[this will kick all players if you are hosting]", 6)
        self.menu.addpaddingcomponent(menu.MenuState.leavegame, 18)
        self.menu.addbuttoncomponent(menu.MenuState.leavegame, "No, return to game", 10, function=self.leavegame_stay) 
        self.menu.addpaddingcomponent(menu.MenuState.leavegame, 18)
        self.menu.addbuttoncomponent(menu.MenuState.leavegame, "Reference & Help", 10, function=self.enterhelpscreen) 
        self.menu.addpaddingcomponent(menu.MenuState.leavegame, 100)

        #instructions for how to use the game
        self.menu.addpaddingcomponent(menu.MenuState.help, 18)
        self.menu.addtextcomponent(menu.MenuState.help, "War Against Memes", 20)
        self.menu.addtextcomponent(menu.MenuState.help, subtitle, 5)
        self.menu.addpaddingcomponent(menu.MenuState.help, 5)
        self.menu.addbuttoncomponent(menu.MenuState.help, "Resume Game [ESC]", 7, centred = False, function=self.leavegame_stay) 
        self.menu.addpaddingcomponent(menu.MenuState.help, 10)
        self.menu.addtextcomponent(menu.MenuState.help, "Button Mapping Reference:                         ", 7)
        self.menu.addtextcomponent(menu.MenuState.help, "           keyboard/mouse -or- controller (xbox)  ", 7)
        self.menu.addpaddingcomponent(menu.MenuState.help, 3)
        self.menu.addtextcomponent(menu.MenuState.help, "To Move:   W, A, S, D     -or- Left Joystick      ", 7)
        self.menu.addpaddingcomponent(menu.MenuState.help, 3)
        self.menu.addtextcomponent(menu.MenuState.help, "To Crouch: L shift        -or- Press Left Joystick", 7)
        self.menu.addpaddingcomponent(menu.MenuState.help, 3)
        self.menu.addtextcomponent(menu.MenuState.help, "To Attack: Left Click     -or- RB, LB, RT, LT     ", 7)
        self.menu.addpaddingcomponent(menu.MenuState.help, 3)
        self.menu.addtextcomponent(menu.MenuState.help, "To Pick/Drop/Swap items:                          ", 7)
        self.menu.addtextcomponent(menu.MenuState.help, "           Right Click    -or- B button           ", 7)
        self.menu.addpaddingcomponent(menu.MenuState.help, 3)
        self.menu.addtextcomponent(menu.MenuState.help, "To Collect Ammo:                                  ", 7)
        self.menu.addtextcomponent(menu.MenuState.help, "           E              -or- A button           ", 7)
        self.menu.addpaddingcomponent(menu.MenuState.help, 3)
        self.menu.addtextcomponent(menu.MenuState.help, "To Drop Ammo:                                     ", 7)
        self.menu.addtextcomponent(menu.MenuState.help, "           Q              -or- X button           ", 7)
        self.menu.addpaddingcomponent(menu.MenuState.help, 3)
        self.menu.addtextcomponent(menu.MenuState.help, "To Aim:    Mouse Position -or- Right Joystick     ", 7)
        self.menu.addpaddingcomponent(menu.MenuState.help, 3)
        self.menu.addtextcomponent(menu.MenuState.help, "Show info: TAB            -or- Y                  ", 7)


        #server not allowed to start error screen
        self.menu.addpaddingcomponent(menu.MenuState.singleplayererror, 18)
        self.menu.addtextcomponent(menu.MenuState.singleplayererror, "War Against Memes", 20)
        self.menu.addtextcomponent(menu.MenuState.singleplayererror, subtitle, 5)
        self.menu.addpaddingcomponent(menu.MenuState.singleplayererror, 5)
        self.menu.addtextcomponent(menu.MenuState.singleplayererror, "There is a program using the required resources on your", 10)
        self.menu.addtextcomponent(menu.MenuState.singleplayererror, "computer; you cannot launch a singleplayer game", 10)
        self.menu.addpaddingcomponent(menu.MenuState.singleplayererror, 10)
        self.menu.addbuttoncomponent(menu.MenuState.singleplayererror, "Back to main menu", 7, function=self.backtomainmenufromerror) 
        self.menu.addpaddingcomponent(menu.MenuState.singleplayererror, 100)

        # end defining menu structure

        #create a dividing bar between multiplayer clients if needed
        divider = pygame.Surface((8, self.displayy))
        divider.fill((255,255,255))
           
        mousex, mousey = pygame.mouse.get_pos() # get current mouse coords
        self.running = True # having this linked to the class means that the quit button can stop this loop remotely from another section in the code
        while self.running:
            ticks = clock.tick() # ticks are the number of milliseconds since this line was last executed
            if ticks > 0: # cannot div by zero if it refreshes fast enough
                pygame.display.set_caption(f"W.A.M. [Feedback Development Version {version}] - {1000//ticks} FPS") 

            keys = pygame.key.get_pressed()

            for event in pygame.event.get():
                if event.type == pygame.QUIT: # red X
                    if self.ingame:
                        self.menu.goto_menuscreen(menu.MenuState.leavegame)
                        self.set_inmenu() # exit to menu
                    else:
                        self.quit()
                if event.type == pygame.VIDEORESIZE and not self.Fullscreen: # screen size adjusted
                    self.windowedx = event.w
                    self.windowedy = event.h
                    self.setwindowed(None) # update size of contents of window
                #get input box keypresses
                if self.inputbox != None: 
                    if event.type == pygame.KEYDOWN:
                        #send input to text box
                        if event.key in keychars:
                            if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or keys[pygame.K_CAPSLOCK]:
                                self.inputbox.keypress(keychars[event.key].upper())
                            else:
                                self.inputbox.keypress(keychars[event.key])



            if self.ingame: # send inputs to clients
                #DO INPUT THINGS
                
                if self.inputmethod < 1: # keyboard, or keyboard and controller (keyboard is client[0] either way!)
                    #movement, aim, crouch, pick/swap/drop item, drop ammo, hud screen 2 (extra info)
                    #get movement vector
                    mx, my = 0, 0
                    if keys[pygame.K_a]:
                        mx -= 1
                    if keys[pygame.K_d]:
                        mx += 1
                    if keys[pygame.K_s]:
                        my -= 1
                    if keys[pygame.K_w]:
                        my += 1
                    if mx != 0 and my != 0: # crop to magnitude of 1 (and avoiding div by 0)
                        rec = 1/( (mx**2 + my**2)**0.5 ) # reciprocal
                        mx *= rec
                        my *= rec
                    #get aim vector
                    if self.Fullscreen: # obtain centre of clients screen
                        centre = ((self.displayx // len(self.clients))//2, self.displayy//2)
                    else:
                        centre = ((self.windowedx // len(self.clients))//2, self.windowedy//2)
                    mousex, mousey = pygame.mouse.get_pos()
                    ax = mousex - centre[0]
                    ay = mousey - centre[1]
                    if abs(ax) < 10: ax = 0
                    if abs(ay) < 10: ay = 0
                    #get other buttons
                    crouch = int(keys[pygame.K_LSHIFT])
                    attack = int(pygame.mouse.get_pressed()[0]) # left click
                    pick = int(pygame.mouse.get_pressed()[2]) # right click
                    dropammo = int(keys[pygame.K_q])
                    collectammo = int(keys[pygame.K_e])
                    info = int(keys[pygame.K_TAB])
                    #relay to client
                    self.clients[0].getinput((mx, my, ax, ay, crouch, attack, pick, dropammo, collectammo, info))
                
                if self.inputmethod == 0: # keyboard and controller splitscreen (controller is client[1])
                    #movement 
                    mx = self.controllers[0].get_axis(0)
                    my = -self.controllers[0].get_axis(1)
                    #stop small non-centering from making move
                    if abs(mx) < 0.1: mx = 0
                    if abs(my) < 0.1: my = 0
                    if mx != 0 and my != 0: # crop to magnitude of 1 (and avoiding div by 0)
                        rec = 1/( (mx**2 + my**2)**0.5 ) # reciprocal
                        mx *= rec
                        my *= rec
                    #aim 
                    ax = self.controllers[0].get_axis(4)
                    ay = self.controllers[0].get_axis(3)
                    #stop small non-centering from making move
                    if abs(ax) < 0.1: ax = 0
                    if abs(ay) < 0.1: ay = 0
                    #get other buttons
                    crouch = int(self.controllers[0].get_button(8))
                    attack = int(self.controllers[0].get_button(6)) or int(abs(self.controllers[0].get_axis(2)) > 0.5) or int(self.controllers[0].get_button(4)) or int(self.controllers[0].get_button(5)) 
                    pick = int(self.controllers[0].get_button(1)) 
                    dropammo = int(self.controllers[0].get_button(2))
                    collectammo = int(self.controllers[0].get_button(0))
                    info = int(self.controllers[0].get_button(3))
                    #relay to client
                    self.clients[1].getinput((mx, my, ax, ay, crouch, attack, pick, dropammo, collectammo, info))

                if self.inputmethod > 0: # controller or controller splitscreen all clients are controllers
                    ID = 0
                    for c in self.clients:
                        #movement 
                        mx = self.controllers[ID].get_axis(0)
                        my = -self.controllers[ID].get_axis(1)
                        #stop small non-centering from making move
                        if abs(mx) < 0.1: mx = 0
                        if abs(my) < 0.1: my = 0
                        if mx != 0 and my != 0: # crop to magnitude of 1 (and avoiding div by 0)
                            rec = 1/( (mx**2 + my**2)**0.5 ) # reciprocal
                            mx *= rec
                            my *= rec
                        #aim 
                        ax = self.controllers[ID].get_axis(4)
                        ay = self.controllers[ID].get_axis(3)
                        #stop small non-centering from making move
                        if abs(ax) < 0.1: ax = 0
                        if abs(ay) < 0.1: ay = 0
                        #get other buttons
                        crouch = int(self.controllers[ID].get_button(8))
                        attack = int(self.controllers[ID].get_button(6)) or int(abs(self.controllers[ID].get_axis(2)) > 0.5) or int(self.controllers[ID].get_button(4)) or int(self.controllers[ID].get_button(5)) 
                        pick = int(self.controllers[ID].get_button(1)) 
                        dropammo = int(self.controllers[ID].get_button(2))
                        collectammo = int(self.controllers[ID].get_button(0))
                        info = int(self.controllers[ID].get_button(3))
                        #relay to client
                        c.getinput((mx, my, ax, ay, crouch, attack, pick, dropammo, collectammo, info))
                        
                        ID += 1 # for next controller



                #RENDER CLIENT(s) # TODO render in parrallel then wait for both threads to finish before rendering to save time??
                # 1 client no matter what
                c = self.clients[0]
                c.render()
                
                x, y = c.image.get_size()
                x *= self.scale
                y *= self.scale
                self.screen.blit(pygame.transform.scale(c.image,(int(x), int(y))), (0,0))
                if len(self.clients) > 1: # multiple (must be 2)
                    c = self.clients[1]
                    c.render()
                    #find where to render the image
                    if self.Fullscreen:
                        w = self.displayx//2
                    else:
                        w = self.windowedx//2
                    #render the image                
                    x, y = c.image.get_size()
                    x *= self.scale
                    y *= self.scale
                    self.screen.blit(pygame.transform.scale(c.image,(int(x), int(y))), (w,0))

                    #render a dividing bar between clients
                    self.screen.blit(divider, (w-4,0))

                #this has to go at the end of client things, so that if it leaves it will not try to access no longer existent clients
                if keys[pygame.K_ESCAPE]:
                    # go to are you sure you want to leave screen:
                    self.menu.goto_menuscreen(menu.MenuState.leavegame)                
                    self.set_inmenu() # exit to menu
                    self.reset_button_timer() # needs resetting otherwise it will come straight back here


                #end client only things
            else: # send inputs to menu system            
                if self.button_time_elapsed(): # keyboard navigation of menu
                    
                    if pygame.joystick.get_count() < 1: # if controller disconnected, then default to 0
                        axis, a, b = 0, 0, 0  # default to 0
                    else:
                        try:
                            axis = self.controllers[0].get_axis(1) # y axis of Left joystick
                            a = self.controllers[0].get_button(0) # A button
                            b = self.controllers[0].get_button(1) # B button
                        except:
                            print("plugged in at invalid time") # it turns out the pygame deals with adding and removing joysticks after it is initialised remarkable well, so non of my code really works to deal with it


                    if keys[pygame.K_ESCAPE] or b:
                        if self.inputbox != None: # exit the input box rather than the menu or the game
                            self.inputbox.defocus()
                            self.inputbox = None
                            self.reset_button_timer()
                        elif self.menu.state == menu.MenuState.leavegame or self.menu.state == menu.MenuState.help:
                            # go back to the game
                            self.set_ingame()
                            self.reset_button_timer()
                        elif self.menu.state == menu.MenuState.main: # this case should be removed when the game is finished with for testing
                            self.running = False
                            self.reset_button_timer()
                        elif self.menu.state == menu.MenuState.directconnect:
                            self.menu.goto_menuscreen(menu.MenuState.connect)
                            self.reset_button_timer()
                        elif self.menu.state == menu.MenuState.name:
                            self.backfromname() # make sure server and things are closed properly
                        else: # TODO later when more than just menu, make this not exit straight to main menu!!
                            self.menu.goto_menuscreen(menu.MenuState.main)
                            self.reset_button_timer()


                    elif keys[pygame.K_UP] or axis < -0.5: # cycle menu selection up (or underflow)
                        self.menu.move_selection_up()
                        self.reset_button_timer()

                    elif keys[pygame.K_DOWN] or axis > 0.5: # cycler menu selection down (or overflow)
                        self.menu.move_selection_down()
                        self.reset_button_timer()

                    elif keys[pygame.K_RETURN] or a: # enter => press selection
                        self.menu.press_selection()
                        self.reset_button_timer()
            
                if self.inputbox != None:  # TODO remove this if events work
                    if keys[pygame.K_BACKSPACE]:
                        if self.backspace_allowed_to_be_pressed():
                            self.inputbox.keypress("BACKSPACE")

                if (mousex, mousey) != pygame.mouse.get_pos() or pygame.mouse.get_pressed()[0]: # if mouse changed position or clicked
                    mousex, mousey = pygame.mouse.get_pos() # should only update with a mouse position if it has changed
                    self.menu.activatecomponent((mousex //self.scale,mousey //self.scale), pygame.mouse.get_pressed()[0]) # pass on to the menu to get that to do the calculations

                self.menu.render()
                x, y = self.menu.image.get_size()
                x *= self.scale
                y *= self.scale
                self.screen.blit(pygame.transform.scale(self.menu.image,(int(x), int(y))), (0,0))
                #end menu things

            pygame.display.flip()

        #once self.quit() has been run, this is where the code will go to. Therefore:
        self.remove_all_clients()# stop server and client if still running
        self.terminate_processes()
        pygame.quit() # exit pygame
        # the game will now have closed
        return self.RESET
        
    # input text box functions
    def deselectinput(self): self.setgatheringinput() # calling this with no parameter means it will assume None and so no input will be selected anymore (this is called by anything else when pressed)
    def setgatheringinput(self, inputcomponent = None): 
        if self.inputbox == inputcomponent:
            return # do nothing, exit the function here, if nothing needs to be changed
        if self.inputbox != None:
            self.inputbox.defocus() # need to be selecting the now pressed on input box
        self.inputbox = inputcomponent # set the new component to be the selected one (if None then later it will be ignored)

    # functions to deal with button press timings (non-gameplay)
    def button_time_elapsed(self):
        if time.time() - self.buttontime > self.buttonwaittime: # if it's been longer than the threshold since last button press
            return True
        else:
            return False

    def reset_button_timer(self):
        self.buttontime = time.time()

    def backspace_allowed_to_be_pressed(self):
        if time.time() - self.keytime > self.keywaittime: # if the time has elapsed, then any button press is allowed
            self.keytime = time.time()
            return True
        else: 
            return False 

# this is what is actually run when the game starts:
if __name__ == "__main__": # (makes the following only run when this file is run directly, and not if imported by another script)
    os.chdir(os.path.dirname(os.path.abspath(__file__))) # set python to run from the directory of this file, rather than whereever it decides to run from e.g. python.exe's path

    again = True
    while again:
        game = GameController()
        again = game.run()
        #relaunch the game until it is exited smoothly

# that one line means that all of the programming is completely in OOP, 
# which makes it a lot easier becuause my game is split into multiple 
# files to make things easier to work on, and so if I want to modify 
# any variable in the GameController, I can via reference rather than 
# trying to do everything in one file and using global variables