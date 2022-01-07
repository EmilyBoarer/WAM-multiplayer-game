from enum import Enum
import os

class MenuState(Enum):
    main = 0        #main menu
    connect = 1     #connect to autodiscovered game
    directconnect = 2   # direct connect to IP
    name = 3        # enter username screen
    leavegame = 4
    singleplayererror = 5
    help = 6
    
import pygame
from collections import defaultdict

import verify

class MenuComponent:
    def __init__(self, menu, text, relativesize, fontfp, bgcol = (0,0,0), txtcol = (255,255,255), activebgcol = (255,255,255), activetxtcol = (0,0,0), centred = True, shouldrender = True):
        self.shouldrender = shouldrender # tell the menu to not draw this (will leave space, used for padding to take advantage to polymorphism to make code neater later)

        self.menu = menu
        self.text = text

        self.fontname = fontfp
        
        self.relativesize = relativesize
        self.setsize()

        self.bgcol = bgcol
        self.txtcol = txtcol
        self.activebgcol = activebgcol
        self.activetxtcol = activetxtcol
        
        self.active = False # if it needs to be highlighted (only true if being pressed or hovered over)

        self.centred = centred # justification of the text (True -> Centre,, False -> Left)
        self.needtorender = True

    def render(self):
        if self.needtorender: # if contents has not changed, then no need to waste CPU time re-rendering - because yes [CPU]: pygame does not have hardware acceleration :'(  
            self.needtorender = False # now rendering and so don't need to re-render after this is finished
            if self.active:
                self.image = pygame.Surface((self.width, self.height))
                self.image.fill(self.activebgcol) # fill with background colour
                tempsurf = self.font.render(self.text, False, self.activetxtcol)  #No Antialiasing looks better with the chosen font
                # render font to a seperate surface (make it possible to then justify as width of text is known)
                if self.centred:
                    x = (self.width - tempsurf.get_size()[0])//2 # work out where it needs to be positioned to be centred on the screen
                else:
                    x=7 # constant gap from edge of the screen to left
                self.image.blit(tempsurf,(x,0))
            else:
                self.image = pygame.Surface((self.width, self.height))
                self.image.fill(self.bgcol) # same as above except without active colours
                tempsurf = self.font.render(self.text, False, self.txtcol)
                if self.centred:
                    x = (self.width - tempsurf.get_size()[0])//2
                else:
                    x=7
                self.image.blit(tempsurf,(x,0))

    def setsize(self):
        self.width = self.menu.width
        self.height = int((self.menu.height/180)*self.relativesize) # work out how tall to set the text to be
        if self.shouldrender:
            self.font = pygame.font.Font(self.fontname, self.height) # update font with new size
            self.needtorender = True
    
    def setactive(self):
        if not self.active: # this check means that needtorender is not erroneously made True
            self.menu.needtorender = True # set render flag if not already set to active
            self.needtorender = True
            self.active = True
    def setinactive(self):
        if self.active: # this check means that needtorender is not erroneously made True
            self.menu.needtorender = True # set render flag if not already inactive
            self.needtorender = True
            self.active = False
    def press(self):
        self.menu.controller.deselectinput() # if this is pressed, deselect a the selected text box
        

class TextComponent(MenuComponent):
    def __init__(self, menu, text, relativesize, font, centred = True, shouldrender = True):
        super().__init__(menu, text, relativesize, font, centred=centred, shouldrender=shouldrender)
    
    def setactive(self):
        pass # this is a passive menu component - does not need to be activated or deactivated
    def setinactive(self):
        pass 

class PaddingComponent(TextComponent): # inheriting TextComponent means don't have to re-overwrite setactive() and setinactive()
    def __init__(self, menu, relativesize):
        super().__init__(menu, "", relativesize, "", shouldrender = False)
        #setting render to false: tell the menu to draw nothing here, saves resources and causes gap in menu (intended, this component just padding)

class ButtonComponent(MenuComponent):
    def __init__(self, menu, text, relativesize, font, centred = True, function = None):
        self.function = function
        super().__init__(menu, text, relativesize, font, centred=centred)
    def press(self):
        self.menu.controller.deselectinput() # if this is pressed, deselect a the selected text box first
        if str(type(self.function)) == "<class 'method'>": # <<< validation to check if function was actually assigned, and to see if it can be called // method is a function of a class => used here, as all the functions assigned to it will be methods
            self.function(self.text) # call the function that was given a reference to when the button was declared

class CyclerComponent(MenuComponent):
    def __init__(self, menu, texts, relativesize, font, centred = True, functions = []):
        super().__init__(menu, texts[0], relativesize, font, centred=centred) # set to start on first option of cycler
        self.texts = texts
        self.counter = 0
        self.functions = functions
    def press(self):
        self.menu.controller.deselectinput() # if this is pressed, deselect a the selected text box first
        self.counter += 1
        if self.counter >= len(self.texts): self.counter = 0 # reset counter if reached last item in cycler
        self.text = self.texts[self.counter] # update the text
        if len(self.functions) >= self.counter: # if all functions are present << validation
            self.functions[self.counter](self.text) # call the required funciton, with the parameter of the text currently selected

        self.needtorender = True # need to update the screen to reflect the new state
        self.menu.needtorender = True

class InputComponent(MenuComponent):  #text box for gathering input
    def __init__(self, menu, relativesize, font, text="", emptycovertext = "", validationfunc = verify.isvalidusername, ongoingvalidationfunc = verify.isvalidusername_ongoing): # default validation function is for username 
        self.covertext = emptycovertext  #this is the text that will be displayed when the text box is not focused and contains not text
        self.validationfunc = validationfunc
        self.ongoingvalidationfunc = ongoingvalidationfunc # set functions to parameters (they are just references to the actual functions)
        super().__init__(menu, text, relativesize, font)
        self.focused = False
        self.input = text # the string that stores what is contained within the input box, initialised to empty if nothing specified
        self.valid = None# stores whether or not the input is valid
    
    def press(self): # set to focused
        self.focused = True
        self.menu.controller.setgatheringinput(self) # tell the controller that it needs to be gathering input from this particular input box
        self.needtorender = True # need to update the screen to reflect the new state
        self.menu.needtorender = True
    
    def keypress(self, char): # this is called by the controller when it is gathering input and a key is pressed
        if char == "BACKSPACE":
            self.input = self.input[:-1] # crop the last character off the end of the text
            self.needtorender = True
            self.menu.needtorender = True # these lines make sure that the screen updates when the contents of the text box is changed

        else: # adding a character:
            totest = self.input + char
            if self.ongoingvalidationfunc(totest): # check the validation for the new proposed input
                self.input = totest # if it is allowed then add the input
                self.needtorender = True
                self.menu.needtorender = True # these lines make sure that the screen updates when the contents of the text box is changed

    def getinput(self): # can be called by another object to get the value of the input box
        self.valid = self.validationfunc(self.input) # run validation function to make sure it is giving correct information about validity
        self.needtorender = True # need to update the screen to reflect any change in self.valid (if one has occured)
        self.menu.needtorender = True
        return self.input, self.valid

    def defocus(self):
        self.focused = False
        self.needtorender = True # need to update the screen to reflect the new state
        self.menu.needtorender = True
        #check to see if the input is valid
        self.valid = self.validationfunc(self.input) # run validation function

    def set_invalid(self): # only called on username input if server refuses name
        self.valid = False
        self.needtorender = True # need to update the screen to reflect the new state
        self.menu.needtorender = True

    def render(self): # render function needs to be re-defined for this for the two seperate cases of focused and unfocused rendering
        if self.focused:
            self.text = self.input
            self.centred = False
            self.setactive() # needs to be in active colour scheme to show the user that it is focused
        else:
            self.centred = True
            if len(self.input) > 0: # display 
                self.text = self.input
            else: # nothing present to display covertext
                self.text = self.covertext
        if self.valid == True: # if True, then show as green (because it has now been checked)
            self.bgcol = (0,102,0)
            self.txtcol = (255,255,255) # normal colours if there is no error with the text
        elif self.valid == False: # if False, then show as red (because it has now been checked)
            self.bgcol = (204,0,0) # red to show that the input is invalid
            self.txtcol = (255,255,255)
        #self.valid may be None if the validation function is yet to be run
        super().render() # now that the variables are set, use the parent's render function to draw again (saves repeating all the code)

class Menu:
    def __init__(self, controller, width, height, state):
        self.controller = controller
        self.width = width
        self.height = height
        self.state = state
        self.components = defaultdict(list)
        self.selectable_components = defaultdict(list)
        self.image = pygame.Surface((width, height))
        self.background = pygame.Surface((self.width, self.height))
        self.backgroundfp = f"defaults{os.sep}background.png"
        self.setbackground(self.backgroundfp)
        self.needtorender = True
        self.selectionID = 1


    def render(self):
        # draw the background image
        if self.needtorender:
            self.needtorender = False
            self.image.blit(self.background, (0,0)) 
            
            #draw each component in the current menu state / screen
            y = 0
            for component in self.components[self.state]:
                if component.shouldrender:
                    component.render()
                    self.image.blit(component.image, (0,y))
                y += component.height # increment y so each menu item is drawn one after each other from the top of the screen down
        
        
    def resize(self, newwidth, newheight):
        self.width = newwidth
        self.height = newheight
        self.image = pygame.Surface((newwidth, newheight))
        for state, components in self.components.items():
            for component in components: # each component needs to be told that it needs to resize, and to what size
                component.setsize() # it will automatically get the width and height via reference
        if self.backgroundfp == None:
            self.background = pygame.Surface((self.width, self.height))
            self.background.fill((0,255,0))
        else:
            self.setbackground(self.backgroundfp) # keep same filepath, reaload it at new size
        #set render flag as content has been updated
        self.needtorender = True
        
    
    def setbackground(self, imagefilepath):
        #this function sets the background image as the largest it can be no matter the aspect ratio or dimensions of the screen/window it is being rendered to
        self.backgroundfp = imagefilepath
        im = pygame.image.load(imagefilepath)
        w = self.width
        h = int((w/im.get_size()[0]) * im.get_size()[1]) # calculate hight from ratio of background image dimensions
        if h < self.height: # the image is to square to fit a vertical skinny ranctangle, so scale the other way (loosing wdith, rather than height of the background image)
            h = self.height
            w = int((h/im.get_size()[1]) * im.get_size()[0])
        self.background = pygame.transform.smoothscale(im, (int(w), int(h))) # scale the image and set as background
    

    def addtextcomponent(self, state, text, relativesize, centred = True, fontfp = f"defaults{os.sep}menufont.ttf"):
        self.components[state].append(TextComponent(self, text, relativesize, fontfp, centred = centred))
    
    def addpaddingcomponent(self, state, relativesize):
        self.components[state].append(PaddingComponent(self, relativesize)) # add component to specified state

    def addbuttoncomponent(self, state, text, relativesize, centred = True, fontfp = f"defaults{os.sep}menufont.ttf", function=None): 
        self.components[state].append(ButtonComponent(self, text, relativesize, fontfp, centred = centred, function=function)) # add to normal list
        self.selectable_components[state].append(self.components[state][-1]) # add the same item to the selectable components list (for keyboard/controller navigation)
    
    def addcyclercomponent(self, state, texts, relativesize, centred = True, fontfp = f"defaults{os.sep}menufont.ttf", functions=[]): 
        self.components[state].append(CyclerComponent(self, texts, relativesize, fontfp, centred = centred, functions=functions))
        self.selectable_components[state].append(self.components[state][-1]) # add the same item to the selectable components list (for keyboard/controller navigation)
    
    def addinputcomponent(self, state, relativesize, fontfp = f"defaults{os.sep}menufont.ttf", text="", emptycovertext = "", validationfunc = verify.isvalidusername, ongoingvalidationfunc = verify.isvalidusername_ongoing): 
        self.components[state].append(InputComponent(self, relativesize, fontfp, text, emptycovertext, validationfunc, ongoingvalidationfunc))
        self.selectable_components[state].append(self.components[state][-1]) # add the same item to the selectable components list (for keyboard/controller navigation)
    

    def removeselectionhighlights(self):
        for component in self.components[self.state]:
            component.setinactive()
    

    def activatecomponent(self, mousecoords, press = False):
        self.removeselectionhighlights() # set everything as de-selected
        mousex, mousey = mousecoords

        y = 0
        for component in self.components[self.state]:
            maxy = y + component.height
            if mousey >= y and mousey < maxy:
                component.setactive() # select only button that is being hovered over
                if self.controller.button_time_elapsed(): # see if can press any button yet
                    if press:
                        component.press()
                        self.controller.reset_button_timer() # reset the timer to prevent multiple presses to frequently
                        self.needtorender = True # need to re-render the screen
            y = maxy

    def crop_state(self, state, targetlength):
        while len( self.components[state] ) > targetlength:
            removed = self.components[state].pop() # remove  and return last element
            #remove from any other possible list
            if removed in self.selectable_components[state]: # <<< check // validation
                self.selectable_components[state].remove(removed)

    #these are the equivalent for the function activatecomponent, except with keyboard or controller rather than mouse
    def move_selection_up(self): # move the selection up 1 (or underflow)
        self.selectionID -= 1
        if self.selectionID < 0: # overflow => reset
            self.selectionID = len(self.selectable_components[self.state]) - 1 
        self.update_screen_with_new_selection() # update the screen to reflect internal state

    def move_selection_down(self): # move the selection down 1 (or overflow)
        self.selectionID += 1
        if self.selectionID >= len(self.selectable_components[self.state]): # overflow => reset
            self.selectionID = 0
        self.update_screen_with_new_selection() # update the screen to reflect internal state

    def press_selection(self): # press the currently selected item 
        component = self.selectable_components[self.state][self.selectionID]
        if type(component) is InputComponent:
            if component.focused:
                self.selectable_components[self.state][self.selectionID + 1].press() # THIS IS A BODGE // this assumes the selectable immediately after the input box is the submit button
                return # skip the line below
        component.press() # press the component is the default

    def update_screen_with_new_selection(self): # tell the new selection to draw itself to the screen
        self.removeselectionhighlights()
        self.selectable_components[self.state][self.selectionID].setactive() # highlight only the selected (hoverd over // not pressed) selectable


    def goto_menuscreen(self, ID, selectionID = 1): # ID is MenuState.something enum
        self.state = ID
        self.selectionID = selectionID # this is always the one below back button
        self.update_screen_with_new_selection()
