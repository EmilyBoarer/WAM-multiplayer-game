import notrequests
import pygame
from collections import defaultdict
import time
import threading
import os
import getpass

# TODO remove this is for debugging the shotgun
import math

class Tile:
    def __init__(self, x, y, texture):
        self.x = int(x)
        self.y = int(y)
        self.texture = texture

class Entity:
    def __init__(self, x, y, vx, vy, texture, tag, itemtex):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.texture = texture
        self.item_texture = itemtex
        self.lastupdate = time.time() # the time of the last update
        #compile tag, with respect to escape codes
        self.entiretag = tag # used to identify which entity to follow the camera on
        self.alltxttag = ""
        self.tag = [[(255,255,255),""]] # list of tuples: (col, txt) // default start is WHITE
        pos = 0
        while pos < len(tag): # can't fit in just the last few chars
            if tag[pos] == "#":
                # convert to integers
                hxR = int(tag[pos+1:pos+3], 16)
                hxG = int(tag[pos+3:pos+5], 16)
                hxB = int(tag[pos+5:pos+7], 16)
                self.tag.append([(hxR,hxG,hxB),""]) # start new colour
                pos += 7
            else:
                self.tag[-1][1] += tag[pos] # add character to most recent colour block
                self.alltxttag += tag[pos]
                pos += 1

    def update_simulation(self):
        #get the time since last update as t in seconds (needed for the physics)
        t = time.time() - self.lastupdate
        self.lastupdate = time.time()
        #update coords based on velocity
        self.x += self.vx * t
        self.y += self.vy * t

class ClientServerCommunicator:
    def __init__(self, client, serveraddress, serverport):
        self.client = client
        self.serveraddress = serveraddress
        self.serverport = serverport
        self.tiles = [] # empty list
        self.entities = []
        
        self.inputs = 0,0,0,0,0,0,0,0,0

        self.framecount = 0
        self.serverplayercount = 1

    def been_kicked(self):
        self.client.controller.clients_kicked_goto_main_menu() # tell the GC to reset

    def join(self):
        #ask to join the server
        try:
            response = notrequests.post(f"{self.serveraddress}:{self.serverport}",f"/adduser/{self.client.name}/{getpass.getuser()}")
            return response.content == "Success"
        except: # not able to join, return error
            return False

    def leave_server(self):
        #ask to leave the server
        if self.client.ingame:
            self.client.ingame = False # stop the other threads
            # try:            
            response = notrequests.post(f"{self.serveraddress}:{self.serverport}",f"/quituser/{self.client.name}")
            #return if successfully left (True = left, False = failed)
            return response.content == "Success"
            # except: # must have been kicked
            #     self.been_kicked()
            #     return False
        else:
            return True # nothing to leave, this can just be deleted

    def get_tile_data(self):
        # try:
        # get tile data as raw from server, then split by '|', then by ','
        response = notrequests.get(f"{self.serveraddress}:{self.serverport}","/gettiles")
        tiles = response.content.split("|") # get rid of containing b' and ' then split by |
        self.tiles = [] # reset the list
        for tile in tiles:
            x, y, tex = tile.split(",")
            self.tiles.append(Tile(x, y, tex))
        # except: # must have been kicked
        #     self.been_kicked()

    def simulationthread(self): # update simulation in seperate thread
        while self.client.ingame:
            if self.serverplayercount > 4: # because of server polling algorithm, if only 1 player it will poll every frame and to this algorithm is unnecessary
                self.updatesimulation()
            time.sleep(0.015)

    def updatesimulation(self):
        #update all entities
        for entity in self.entities:
            entity.update_simulation()
            if entity.entiretag == self.client.name: # TODO will need to change for the death mechanic
                self.client.centrex = float(entity.x)+0.5
                self.client.centrey = float(entity.y)+0.5

    def giveinput(self, inputs):
        self.inputs = inputs # save for the secondary thread to pick up
        #TEMP for debugging processing
        self.sendinput()
        self.framecount += 1
        if self.framecount >= self.serverplayercount//4 + 1:
            self.framecount = 0
            self.resetsimulationandgetalldata()

    def sendinput(self): # called by secondary thread
        # try:
        t = time.time()
        # mx, my, ax, ay, crouch, attack, pick, dropammo, info = inputs # movement, aim, crouch, pick/swap/drop item, drop ammo, hud screen 2 (extra info)
        tosend = "|".join([str(i) for i in self.inputs])
        # send info to the server
        response = notrequests.post(f"{self.serveraddress}:{self.serverport}", f"/updateuser/{self.client.name}/{tosend}")
        t = time.time() - t
        #update HUD data and log data
        try:
            # print(response.content)
            hud, logs = response.content.split("|")
            self.client.huddata = hud.split("\\n")            
            self.client.logdata = logs.split("\\n")
            self.client.check_for_world_change()
        except:
            pass
        return t # return time it took to poll server
        # except: # must have been kicked
        #     self.been_kicked()
        #     return 100

    def resetsimulationandgetalldata(self):
        # try:
        t = time.time()
        response = notrequests.post(f"{self.serveraddress}:{self.serverport}",f"/getentityandserverdata/{self.client.name}")
        t = time.time() - t
        r = response.content
        if r[:7] == "Success":
            name, playercount, entities = r[8:].split(":")
            self.serverplayercount = int(playercount) # saved for timing algorithm
            #reset entity simulation
            self.entities = []
            for e in entities.split("|"): # TODO except if broken?
                x, y, vx, vy, tex, tag, itemtex = e.split(",")
                if tag == name:
                    self.client.centrex = float(x)+0.5
                    self.client.centrey = float(y)+0.5
                if name == "": # spectator -> need to set manually otherwise it will track to any object
                    self.client.centrex = 30
                    self.client.centrey = 30
                self.entities.append(Entity(x, y, vx, vy, tex, tag, itemtex)) # create new entity
        return t # return time it took to poll server
        # except: # must have been kicked
        #     self.been_kicked()
        #     return 100



class Client:
    def __init__(self, serveraddress, serverport, gamecontroller, width, height): # width and height are in pixels, the GC should handle all scaling
        # the client should be instantiated when the server details are known: 
        # this should be run as the "enter username" screen is loaded, so no username is required yet
        self.controller = gamecontroller

        self.csc = ClientServerCommunicator(self, serveraddress, serverport)

        self.pixels = 16 # width and height of texture # TODO load with texturepack??
                
        self.centrex = 0
        self.centrey = 0
        
        self.backwidth = 0
        self.backheight = 0

        self.textures = {}
        self.texturefp = f"Texturepacks{os.sep}loadedtextures"
        self.texturefe = ".png"
        self.texturescale = 0

        self.tileimage = pygame.Surface((width, height))

        self.fontfp = f"defaults{os.sep}menufont.ttf"

        self.name = "" # this is set later, prevents crashes when on enter username screen
        self.resize(width, height) # use this algorithm to set the size and all appropriate variables

        self.ingame = False # this stores if the client is currently connected to a server

        self.mouseaim = False
        self.aimX, self.aimY = 0,0

        self.huddata = []
        self.logdata = []

        self.lastworldname = ""


    def check_for_world_change(self):
        """this function checks to see if the world name has changed and so it would need to reload the tiles"""
        if self.lastworldname != self.huddata[0]: # reload tiles
            self.update_tiles() # get new tiles
            self.lastworldname = self.huddata[0]
            #force update to screen
            self.resize(self.width, self.height)

    def get_texture(self, name, scale=1):
        if self.texturescale != self.scale:
            self.textures = {} # reset as need to load with new res
            self.texturescale = self.scale
        if not name in self.textures:
            #need to add it
            #check if special case or if needs external loading
            if name == "BulletParticle":
                self.textures[name] = (pygame.Surface((self.scale//8, self.scale//8)), 0)
                self.textures[name][0].fill((255,185,0))
            elif name == "DamageParticle":
                self.textures[name] = (pygame.Surface((self.scale//8, self.scale//8)), 0)
                self.textures[name][0].fill((255,0,0))
            elif name == "BLANK":
                self.textures[name] = (pygame.Surface((1,1)).convert_alpha(), 0) # minimal size reduces amount of work rendering -> improves performance
                self.textures[name][0].fill((0,0,0,0))
            else:
                if os.path.isfile(self.texturefp+os.sep+name+self.texturefe): # normal base texture
                    self.textures[name] = (pygame.transform.scale(
                        pygame.image.load(self.texturefp+os.sep+name+self.texturefe).convert_alpha(),
                        (self.scale*scale, self.scale*scale)
                        ), 
                        0 # height compensation
                    )
                    if os.path.isfile(self.texturefp+os.sep+name+"_HAT"+self.texturefe): # check for hat
                        tx = pygame.Surface((16, 32)).convert_alpha()
                        tx.fill((0,0,0,0))
                        tx.blit(
                            pygame.image.load(self.texturefp+os.sep+name+self.texturefe).convert_alpha(), 
                            (0, 16)
                        ) # render already loaded texture
                        tx.blit(
                            pygame.image.load(self.texturefp+os.sep+name+"_HAT"+self.texturefe).convert_alpha(),
                            (0,0)
                        ) # render HAT

                        #replace texture
                        self.textures[name] = (
                            pygame.transform.scale(tx.convert_alpha(), (self.scale*scale, self.scale*scale*2)), 
                            1 # height compensation
                        )
                else: # texture not found to load blank
                    self.textures[name] = (pygame.transform.scale(
                        pygame.image.load(f"defaults{os.sep}X{self.texturefe}").convert_alpha(),
                        (self.scale*scale, self.scale*scale)
                        ), 
                        0 # height compensation
                    )

        return self.textures[name]


    def stop(self):
        return self.csc.leave_server() # leave game smoothly


    def update_tiles(self):
        texfp=self.texturefp+os.sep # texture file path
        texfe=self.texturefe
        # get the data to the csc
        self.csc.get_tile_data()  
        #construct it to self.tileimage:
        # figure out the dimensions of the area, and what textures need to be loaded:
        minx = 0
        maxx = 0
        miny = 0
        maxy = 0
        texs = []
        for tile in self.csc.tiles:
            if tile.x > maxx:
                maxx = tile.x
            if tile.x < minx:
                minx = tile.x
            if tile.y > maxy:
                maxy = tile.y
            if tile.y < miny:
                miny = tile.y
            if not tile.texture in texs:
                texs.append(tile.texture)

        self.backwidth  = (maxx-minx + 1)*self.pixels
        self.bgheight = maxy-miny + 1 # this is how many tiles high it is
        self.backheight = (self.bgheight)*self.pixels #this is how many pixels high it is 
        #create new copy of image with transparency as background
        self.tileimage = pygame.Surface((self.backwidth, self.backheight)).convert_alpha()
        self.tileimage.fill((0,0,0,0))
        
        textures = {}
        #load all textures to dict:
        for t in texs:
            if os.path.isfile(texfp+t+texfe): # normal base texture
                textures[t] = pygame.image.load( texfp+t+texfe )
            else:
                textures[t] = pygame.image.load( f"defaults{os.sep}X.png" )
        #render all tiles to tileimage
        for tile in self.csc.tiles:
            self.tileimage.blit(
                textures[tile.texture], 
                (tile.x*self.pixels, (maxy-tile.y)*self.pixels)
                )

    def join(self, name): # this should be called when the user has entered there name
        self.name = name # proposed username
        successful = self.csc.join() # attemp to join
        self.ingame = successful # update to reflect server's response
        if successful:
            self.update_tiles() # need to load the world data generally one-off occurance, but will be able to be triggered when the server knows it needs to update the client's model
            #start the entity updating algorithm
            clientsidepredictionthread = threading.Thread(target = self.csc.simulationthread)
            clientsidepredictionthread.start()
        return successful

    def resize(self, newwidth, newheight):
        self.width = newwidth
        self.height = newheight
        self.image = pygame.Surface((self.width, self.height))

        #calculate scale based on pixel width and height
        maxview = 10 # the max amount of tiles visible
        xscale = self.width//maxview # pixels for each tile
        yscale = self.height//maxview
        #set the larger to be the scale
        if xscale > yscale:
            self.scale = xscale
        else:
            self.scale = yscale
        #scale is the number of pixels (width and height) that each tile should appear
        self.uiscale = self.scale

        if self.name == "spectator":
            maxview = 60
            xscale = self.width//maxview # pixels for each tile
            yscale = self.height//maxview
            #set the smaller to be the scale -> see whole world
            if xscale < yscale:
                self.scale = xscale
            else:
                self.scale = yscale
            #scale is the number of pixels (width and height) that each tile should appear
            self.uiscale = self.scale * 6
        
        #calculate size to scale background to
        wid = self.scale*self.backwidth  // self.pixels
        hei = self.scale*self.backheight // self.pixels
        #render backimage
        self.backimage = pygame.transform.scale(
                self.tileimage, 
                (wid,hei) # new resolution
                )
        # self.minimapimage = pygame.transform.scale(
        #         self.tileimage, 
        #         (int(self.width/1.5), int(self.height/1.5)) # new resolution
        #         )

        self.tagfont = pygame.font.Font(self.fontfp, self.scale//3)
        self.UIfont = pygame.font.Font(self.fontfp, self.uiscale//4)
        
            

    def render(self):
        #reset screen
        self.image.fill((0,0,0))
        #render background (tiles layer)

        self.image.blit(
            self.backimage, 
            (self.translate_map_coords_to_screen_coords(0,0, self.bgheight)) # beginning of background is at (0,0)
            )

        #render all entities
        for e in self.csc.entities:
            #render background item
            if e.item_texture[0] == "B" and e.item_texture != "BLANK":
                self.image.blit(
                    self.get_texture(e.item_texture[1:], scale=2)[0],
                    (self.translate_map_coords_to_screen_coords(e.x-0.5, e.y+0.5, 1))
                )
            #render texture of entity
            self.image.blit(
                self.get_texture(e.texture)[0],
                (self.translate_map_coords_to_screen_coords(e.x, e.y + self.get_texture(e.texture)[1], 1))
            )
            #render foreground item
            if e.item_texture[0] == "F" and e.item_texture != "BLANK":
                self.image.blit(
                    self.get_texture(e.item_texture[1:], scale=2)[0],
                    (self.translate_map_coords_to_screen_coords(e.x-0.5, e.y+0.5, 1))
                )
            #render tag (allowing for multiple colours)
            offset = self.tagfont.size(e.alltxttag)[0]/2 #(width/2)
            x,y = self.translate_map_coords_to_screen_coords(e.x+0.5, e.y+0.35, 1)
            x -= offset
            for col, txt in e.tag:
                self.image.blit(
                    self.tagfont.render(txt, False, col),                
                    (x,y)
                )
                x += self.tagfont.size(txt)[0] # increment the space so that the following text renders in the correct position

        #aim indicator
        if self.name != "spectator":
            self.image.blit( 
                self.get_texture("AIM")[0],
                (self.aimX, self.aimY)
            )

        # #TEMP for debugging shotgun
        # tempsurf = pygame.Surface((5,5))

        # cx = self.origaimX
        # cy = self.origaimY

        # vecs = [
        #     (cx, cy, (255,0,0))
        #     ]
        # if self.huddata[1] == "Holding: Shotgun":
        #     vecs.append((cx*math.cos(0.19)-cy*math.sin(0.19) , cx*math.sin(0.19)+cy*math.cos(0.19), (0,255,0)))
        #     vecs.append((cx*math.cos(-0.19)-cy*math.sin(-0.19) , cx*math.sin(-0.19)+cy*math.cos(-0.19), (0,0,255)))

        # for aX, aY, col in vecs:
        #     tempsurf.fill(col)
            
        #     for n in range(100): #  render line from centre to aim
                
        #         self.image.blit( 
        #             tempsurf,
        #             (
        #                 self.width//2 + aX * n/100,
        #                 self.height//2 + aY * n/100
        #             )
        #         )

        #render hud
        if len(self.huddata) > 0:
            if self.HUD2 or self.name=="spectator": # secondary hud
                y = 0
                for txt in [self.huddata[0]]+self.huddata[5:]: 
                    self.image.blit(
                        self.UIfont.render(txt, False, (255,255,255)),                
                        (5,y)
                    )
                    y += (self.uiscale // 4) + 5

            else: # normal hud
                y = 0
                for txt in self.huddata[1:5]:
                    self.image.blit(
                        self.UIfont.render(txt, False, (255,255,255)),                
                        (5,y)
                    )
                    y += (self.uiscale // 4) + 5

        # render logs
        y = self.height - self.uiscale//4 - 5
        for txt in self.logdata:
            self.image.blit(
                self.UIfont.render(txt, False, (255,255,255)),                
                (5,y)
            )
            y -= (self.uiscale // 4) + 5

        #render coordinates for debugging:
        txt = "X:" + str("{0:.2f}".format(self.centrex-0.5)) + " Y:" + str("{0:.2f}".format(self.centrey-0.5))
        self.image.blit(
            self.UIfont.render(txt, False, (255,255,255)),                
            (self.width - 5 - self.UIfont.size(txt)[0],self.height - self.UIfont.size(txt)[1])
        )

        # #render minimap for debugging
        # self.image.blit(
        #     self.minimapimage, 
        #     (int(self.width/5), int(self.height/5))
        #     )

        # #render watermark // temp whilst developing
        # self.image.blit(
        #     self.UIfont.render("Copyright Emily Boarer 2021 - DO NOT DISTRIBUTE", False, (255,255,255)),                
        #     (5,self.height - self.scale//4)
        # )
                

    def translate_map_coords_to_screen_coords(self, mapx, mapy, tileheight):
        x = self.width//2  + self.scale*( mapx - self.centrex)        
        y = self.height//2 - self.scale*( mapy - self.centrey + tileheight) # todo need to alter so mapy is bottom left not top left or something // add no.tiles high in bracket

        return x, y

    def getinput(self, inputs):
        _1, _2, x, y, _3, _4, _5, _6, _7, self.HUD2 = inputs
        self.csc.giveinput(inputs) # pass inputs through to client server comminicator

        self.origaimX = x
        self.origaimY = y

        #position aim indicator
        if abs(x) + abs(y) > 10 or self.mouseaim: # must be mouse aiming: go to coords
            self.mouseaim = True
            x /= self.controller.scale
            y /= self.controller.scale
            x += (self.width - self.scale)//2
            y += (self.height - self.scale)//2
            self.aimX, self.aimY = x, y
        else: # must be controller input
            mag = (x**2 + y**2) ** 0.5
            if mag > 0.2: # only if aiming somewhere new, update
                if self.width > self.height:
                    x *= (self.height/4)/mag
                    y *= (self.height/4)/mag
                else:
                    x *= (self.width/4)/mag
                    y *= (self.width/4)/mag
                x += (self.width - self.scale)//2
                y += (self.height - self.scale)//2
                self.aimX, self.aimY = x, y

                







