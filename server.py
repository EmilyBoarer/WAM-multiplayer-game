
# from flask import Flask, request
import wsgiserver
import socket
import verify
import threading
import random
import time
import cmath # for complex numbers for vector rotation
import math

#disable Flask messages all the time, unless an error or starting the server
# import logging
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

class Tile:
    def __init__(self, x, y, solid, textures):
        self.x = x
        self.y = y
        self.solid = solid
        self.texture = random.choice(textures)
    def __str__(self): # return sending data encoded info about this tile
        return str(self.x) + "," + str(self.y) + "," + self.texture

class GroundTile(Tile):
    def __init__(self, x, y):
        super().__init__(x, y, False, [ # random texture (more times repeated higher probability of being picked) // layed out as so for better readability
            "T100" for _ in range(100)] + [
            "T101","T101","T101","T101","T101",
            "T102","T102","T102","T102","T102",
            "T103","T103","T103","T103","T103",
            "T104","T104","T104","T104","T104",
            "T105","T105",
            "T106","T106",
            "T107",
            "T108",
            "T109",
            "T110",
        ])

class WallTile(Tile):
    def __init__(self, x, y):
        super().__init__(x, y, True, [ # random texture (more times repeated higher probability of being picked) // layed out as so for better readability
            "T000","T000","T000","T000","T000","T000","T000","T000","T000","T000","T000",
            "T001",
        ])

class Vector2D:
    def __init__(self, x = 0, y = 0):
        self.x = x
        self.y = y
    def __rmul__(self, value): # this is value * self
        if type(value) == int or type(value) == float: 
            return Vector2D(self.x * value, self.y * value)
        elif type(value) == Vector2D:
            return value.x * self.x + value.y + self.y
        else:
            raise ValueError("Can only multiply two 2D vectors or vector and integer")
    def __mul__(self, value):
        if type(value) == int or type(value) == float:
            return self.__rmul__(value)
        elif type(value) == Vector2D:
            return value.__rmul__(self)
        else:
            raise ValueError("Can only multiply two 2D vectors or vector and integer")
            
    def __add__(self, value):
        if type(value) == Vector2D:
            return Vector2D(self.x + value.x, self.y + value.y)
        else:
            raise ValueError("Can only add two vectors")

    def cap_to_magnitude(self, magnitude):
        if (self.x ** 2 + self.y ** 2)**0.5 > magnitude:
            rec = magnitude / ( (self.x ** 2 + self.y ** 2)**0.5 )
            self.x *= rec
            self.y *= rec

    def set_to_magnitude(self, magnitude):
        mod = (self.x ** 2 + self.y ** 2)**0.5
        if mod != 0:
            rec = magnitude / mod
            self.x *= rec
            self.y *= rec

    def totuple(self):
        return self.x, self.y

    def __abs__(self):
        return (self.x**2 + self.y**2)**0.5 

    def copy(self):
        return Vector2D(self.x, self.y)

    def get_copy_rotated_radians(self, r):
        """return a copy of the vector rotated r radians, by pretending the vector is a complex number on an argand diagram"""
        c = complex(self.x, self.y) * cmath.exp(r * 1j) # rotate by r radians ACW
        return Vector2D(c.real, c.imag)

class Entity:
    def __init__(self, x, y,terminalvel, health, tag, texture ):
        self.time = 1 # to stop error where loads particle slower than calling it's function
        #movement variables:
        self.position = Vector2D(x, y)
        self.velocity = Vector2D()
        self.acceleration = Vector2D()
        self.terminalVelocity = 3 # terminal velocity in tiles per second
        self.thrustPotential = 75 # TODO remove hardcoding?
        self.thrust = Vector2D()
        self.Fmax = 50

        self.health = health
        #only utilised by player at the moment, but nicer to have set in entity:
        self.maxhealth = health
        self.maxammo = 255
        self.ammo = 0
        self.holding = None
        self.XP = 0

        self.tag = tag 
        self.texture = texture
        self.rotational_textureID = 0 # mostly never used, but is is here for the odd case in which it is
        
        self.accepts_damage = True

    def __str__(self): # returned for encoding
        x, y = self.position.totuple()
        vx, vy = self.velocity.totuple()

        if self.holding == None: # nothing to render
            h = "BLANK"
        else: # must specify rotational texture too
            h = self.holding.renderlayer + self.holding.rotational_textures[self.rotational_textureID]

        return f"{x},{y},{vx},{vy},{self.texture},{self.tag},{h}"

    def die(self, killer):
        self.accepts_damage = False
        #this will be overwritten by most types of entities but is basic for enemy behavour
        #remove self from world
        pass # TODO imeplment

    def take_damage(self, dealer, quantity):
        if self.health > 0: # don't call die if already dead by this line 
            self.health -= quantity
            if self.health <= 0:
                self.health = 0
                self.die(dealer)

    def dropammo_getquantity(self):
        """this only returns the value that has been deducted, this does not spawn any ammoholders"""
        maxdrop = 10
        if self.ammo > maxdrop:
            self.ammo -= maxdrop
            deducted = maxdrop
        else:
            deducted = self.ammo
            self.ammo = 0
        return deducted
    
    def use_ammo(self, size = 1):
        """this just uses one ammo, returns True is permitted to use, and False if not permitted"""
        if self.ammo >= size:
            self.ammo -= size
            return True
        else:
            return False
    
    def add_ammo(self, quantity):
        """this returns the amount unable to be fit into the ammo holding inventory"""
        while quantity > 0 and self.ammo < self.maxammo:
            quantity -= 1
            self.ammo += 1
        return quantity


class Enemy(Entity):
    def __init__(self, x, y, health, tag, texture, server):
        super().__init__(x, y, 0, health, tag, texture)
        self.tag = f"#00ff00[{self.health}]"

        self.server = server
        self.server.entities.append(self) # add to entities list
        self.server.enemies.append(self) # add to enemies list

        self.stun = False
        self.stuntime = 0

        self.lastmovetime = 0

        #movement AI stats
        self.mAIspeed = 1 # tile/second
        self.mAIrange = 10 # tiles

        self.target_finding_method = 0
        #0 = position
        #1 = position + 1 tile in direction of velocity
        #2 = projected collision point

        #combat AI stats 
        self.cAIrange = 1.5 # tiles
        self.cAIcount = 1

        self.damage = 1 # how many points the enemy deals
        self.cooldown = 0.2 # seconds between damages

        self.lastattacktime = 0 # stores the lats time it attacked


    def update(self): # called to update AI
        #check stun to see if can move
        if self.stun:
            if time.time() - self.stuntime - self.cooldown > 0:
                self.stun = False
            else: return # prevent anyting from running if stunned by damage
        self.update_movement_ai()
        if self.can_deal_damage():
            self.update_combat_ai()

    def calc_path_target(self):
        """calcualate target to track: nearest player"""
        potential_targets = []
        for _, player in self.server.players.items():
            dist = abs( player.position + -1*self.position )
            if dist <= self.mAIrange and dist >= self.cAIrange*0.6 and player.accepts_damage and player.name != "": # only potential if close enough, but not too close    name "" means spectator!
                potential_targets.append((player, dist))
        if len(potential_targets) > 0:
            #target = player : 
            player = sorted(potential_targets, key=lambda tup: tup[1])[0][0] # sort by distance, return player
            #calculate position to return
            pos = player.position # method 0

            if self.target_finding_method == 1: # method 1
                addition = player.velocity.copy()
                addition.set_to_magnitude(1) # 1 in direction of movement
                pos = player.position + addition

            if self.target_finding_method == 2: # method 2
                #maths is basically solving |e.pos - p.pos - t*p.vel| = t * e.speed   for t>0, to then sub to get target = p.pos + t*p.vel

                rx, ry = ( self.position + -1*player.position ).totuple()
                vx, vy = player.velocity.totuple()
                s = self.mAIspeed

                #coeffs of t^2, t^1, t^0 for quadratic equation:
                a = vx**2 + vy**2 - s**2
                b = 2 * ( vx*rx + vy*ry ) # this should be -2, but because of how b is used, i have removed double negation!! => formula should be +b not -b as it normally would be
                c = rx**2 + ry**2
                
                discrim = b**2 - 4*a*c

                if discrim >= 0: # real solutions => possible to catch the player with current velocity
                    t = ( b + discrim**0.5 ) / ( 2*a ) # ignore the other solution, because that would break t>0
                    pos = player.position + t * player.velocity
                
                else: # the player is faster and ahead => not possible to catch, default to method 1
                    addition = player.velocity.copy()
                    addition.set_to_magnitude(1) # 1 in direction of movement
                    pos = player.position + addition

            return pos
        return None

    def update_movement_ai(self):
        target = self.calc_path_target()
        #time since last update
        t = time.time() - self.lastmovetime
        self.lastmovetime = time.time()
        if t > 0.2: t = 0.2 # cap to prevent anything if server lagging a lot
        # move towards that position if a target was found
        if target != None:
            ox, oy = self.position.totuple() # old position // needed for collision detection later

            self.velocity = -1*self.position + target # get direction of movement
            self.velocity.set_to_magnitude(self.mAIspeed) # set speed
            self.position = self.position + t*self.velocity
            
            #collision detection
            def teleport_to_spawn(): # called if out of bounds error
                self.die(self)

            px, py = self.position.totuple()

            #offset derived from 1-90% / 2 => 0.05
            offset = 0.05
            #when checking, the non-focus axis should use the previous coordinate becacuse otherwise it causes a very jittrey mess when moving through 1 wide gaps or against walls in general

            if self.velocity.x > 0: #is the x coord increasing according to velocity// so need to check right side and decrese position if colliding
                #must be moving to the right
                #calc corners to check
                corners = (
                    (px + 1 - offset, oy+offset), # bottom right
                    (px + 1 - offset, oy+1-offset), # top right
                )
                #check each corner to see if need to back up to border line
                reverse = False
                for x, y in corners:
                    #check if the corner is in a wall tile
                    try:
                        if type(self.server.world["tiles"][int(y)][int(x)]) is WallTile: # int is effectively floor function // truncate
                            #check to see that player is not on y boundary
                            if y % 1 == 0: # if y is whole number exactly => exepmtion because traveling against wall, and probably in 1 block high gap
                                pass
                            else: # not on boundary
                                reverse = True
                    except KeyError: # caused by out of bounds and no tile information
                        teleport_to_spawn()
                        
                if reverse: # must back out to exactly edge of tile
                    self.position.x -= px % 1 - offset #subtract the distance into the tile it is
                    self.velocity.x = 0 # reset velocity to 0

            if self.velocity.x < 0: #is the x coord decreasing according to velocity// so need to check leftt side and increase position if colliding
                #must be moving to the right
                #calc corners to check
                corners = (
                    (px + offset, oy+offset), # bottom left
                    (px + offset, oy+1-offset), # top left
                )
                #check each corner to see if need to back up to border line
                reverse = False
                for x, y in corners:
                    #check if the corner is in a wall tile
                    try:
                        if type(self.server.world["tiles"][int(y)][int(x)]) is WallTile: # int is effectively floor function // truncate
                            #check to see that player is not on y boundary
                            if y % 1 == 0: # if y is whole number exactly => exepmtion because traveling against wall, and probably in 1 block high gap
                                pass
                            else: # not on boundary
                                reverse = True
                    except KeyError: # caused by out of bounds and no tile information
                        teleport_to_spawn()
                        
                if reverse: # must back out to exactly edge of tile
                    self.position.x += 1 - (px % 1) - offset #add the distance into the tile it is
                    self.velocity.x = 0 # reset velocity to 0
            
            if self.velocity.y > 0: #is the y coord increasing according to velocity// so need to check top side and decrese position if colliding
                #must be moving to the right
                #calc corners to check
                corners = (
                    (ox + offset, py+1-offset), # top left
                    (ox + 1-offset, py+1-offset), # top right
                )
                #check each corner to see if need to back up to border line
                reverse = False
                for x, y in corners:
                    #check if the corner is in a wall tile
                    try:
                        if type(self.server.world["tiles"][int(y)][int(x)]) is WallTile: # int is effectively floor function // truncate
                            #check to see that player is not on y boundary
                            if x % 1 == 0: # if x is whole number exactly => exepmtion because traveling against wall, and probably in 1 block high gap
                                pass
                            else: # not on boundary
                                reverse = True
                    except KeyError: # caused by out of bounds and no tile information
                        teleport_to_spawn()
                        
                if reverse: # must back out to exactly edge of tile
                    self.position.y -= py % 1 - offset #subtract the distance into the tile it is
                    self.velocity.y = 0 # reset velocity to 0
            
            if self.velocity.y < 0: #is the y coord decreasing according to velocity// so need to check bottom side and decrese position if colliding
                #must be moving to the right
                #calc corners to check
                corners = (
                    (ox + offset, py+offset), # top left
                    (ox + 1-offset, py+offset), # top right
                )
                #check each corner to see if need to back up to border line
                reverse = False
                for x, y in corners:
                    #check if the corner is in a wall tile
                    try:
                        if type(self.server.world["tiles"][int(y)][int(x)]) is WallTile: # int is effectively floor function // truncate
                            #check to see that player is not on y boundary
                            if x % 1 == 0: # if x is whole number exactly => exepmtion because traveling against wall, and probably in 1 block high gap
                                pass
                            else: # not on boundary
                                reverse = True
                    except KeyError: # caused by out of bounds and no tile information
                        teleport_to_spawn()
                        
                if reverse: # must back out to exactly edge of tile
                    self.position.y += 1 - (py % 1) - offset #add the distance into the tile it is
                    self.velocity.y = 0 # reset velocity to 0


        else:
            #no collision detection because no movement!
            self.velocity = Vector2D()

    def update_combat_ai(self):
        # get closest player
        targets = []
        for _, player in self.server.players.items():
            dist = abs(player.position + -1*self.position)
            if player.accepts_damage:
                targets.append((player, dist))
        #apply damage to selected player
        if len(targets) > 0:
            targets = sorted(targets, key=lambda tup: tup[1])
            for target in targets[:self.cAIcount]: # closest (count) targets
                if target[1] <= self.cAIrange: # within range for combat
                    #deal damage
                    target[0].take_damage(self, self.damage_count())
                    #reset cooldown
                    self.lastattacktime = time.time()
                    #TODO damage particle

    def can_deal_damage(self):
        return time.time() - self.lastattacktime > self.cooldown

    def damage_count(self):
        return self.damage # This will be overwritten by some child classes which may choose to determine this on-the-fly based on enemy health too!

    def die(self, killer): # TODO account for dropping items as reward for player
        # if in normal game mode, then give players some drops
        if self.server.world["name"] == "Game World":
            x, y = self.position.totuple()
            #drop random ammo
            AmmoHolder(x, y, random.randint(3,10), self.server)
            #1 in 3 chance of a drop:
            if random.randint(1,3) == 2:
                #drop weapon (random chance)
                r = random.randint(1,100)
                #spawn random item
                if r == 100: # 1% chance
                    item = GatlingGun(self.server)
                elif r >= 95: # 5% chance
                    item = SniperRifel(self.server)
                elif r >= 85: # 10% chance
                    item = Shotgun(self.server)
                elif r >= 75: # 10% chance
                    item = Revolver(self.server)
                elif r >= 65: # 10% chance
                    item = Pistol(self.server)
                elif r >= 50: # 15% chance
                    item = BroadSword(self.server)
                elif r >= 35: # 15% chance
                    item = Axe(self.server)
                elif r >= 20: # 15% chance
                    item = MetalPole(self.server)
                else: # 20% chance
                    item = WoodenStick(self.server)
                item.itemholder.position = self.position.copy()


        #normal dying procedure
        if self in self.server.enemies:
            self.server.enemies.remove(self)
        if self in self.server.entities:
            self.server.entities.remove(self)

    def take_damage(self, dealer, quantity):
        super().take_damage(dealer, quantity)
        self.stun = True
        self.stuntime = time.time()
        x, y = self.position.totuple()
        for _ in range(quantity): # spawn one per damage dealt -> feedback on how much damage too!
            DamageParticle(x, y, self.server)

        #change tag to refect current status of being alive
        if self.health > self.maxhealth * 0.5: # green if health above 50%
            self.tag = f"#00ff00[{self.health}]"
        elif self.health > self.maxhealth * 0.2: # yellow if health 50%-20%
            self.tag = f"#ffff00[{self.health}]"
        elif self.health > 0: # red if below 20%
            self.tag = f"#ff0000[{self.health}]"

    def killmsg(self, killedname):
        return f"{killedname} was killed by {self.name}"

class Enemy0(Enemy): # corrupt stonks
    def __init__(self, x, y, server):
        super().__init__(x, y, 10, "", "E100", server)
        
        #movement AI stats
        self.mAIspeed = 1 # tile/second
        self.mAIrange = 10 # tiles

        self.target_finding_method = 0

        #combat AI stats 
        self.cAIrange = 2 # tiles
        self.cAIcount = 1

        self.damage = 1 # how many points the enemy deals
        self.cooldown = 0.5 # seconds between damages
        
        self.name = "Corrupt Stonks"

class Enemy1(Enemy): # corrupt Chungus
    def __init__(self, x, y, server):
        super().__init__(x, y, 25, "", "E101", server)
        
        #movement AI stats
        self.mAIspeed = 1 # tile/second
        self.mAIrange = 10 # tiles

        self.target_finding_method = 0

        #combat AI stats 
        self.cAIrange = 2 # tiles
        self.cAIcount = 1

        self.damage = 5 # how many points the enemy deals
        self.cooldown = 0.5 # seconds between damages

        self.name = "Corrupt Chungus"

class Enemy2(Enemy): # corrupt POG
    def __init__(self, x, y, server):
        super().__init__(x, y, 50, "", "E102", server)
        
        #movement AI stats
        self.mAIspeed = 1.5 # tile/second
        self.mAIrange = 10 # tiles

        self.target_finding_method = 0

        #combat AI stats 
        self.cAIrange = 2.5 # tiles
        self.cAIcount = 1

        self.damage = 10 # how many points the enemy deals
        self.cooldown = 0.5 # seconds between damages

        self.name = "Corrupt POG"

class Enemy3(Enemy): # corrupt shrek
    def __init__(self, x, y, server):
        super().__init__(x, y, 100, "", "E103", server)
        
        #movement AI stats
        self.mAIspeed = 1.5 # tile/second
        self.mAIrange = 10 # tiles

        self.target_finding_method = 1

        #combat AI stats 
        self.cAIrange = 2.5 # tiles
        self.cAIcount = 1

        self.damage = 12 # how many points the enemy deals
        self.cooldown = 0.3 # seconds between damages

        self.name = "Corrupt Shrek"

class Enemy4(Enemy): # corrupt gerry
    def __init__(self, x, y, server):
        super().__init__(x, y, 150, "", "E104", server)
        
        #movement AI stats
        self.mAIspeed = 1.5 # tile/second
        self.mAIrange = 10 # tiles

        self.target_finding_method = 1

        #combat AI stats 
        self.cAIrange = 2.5 # tiles
        self.cAIcount = 1

        self.damage = 18 # how many points the enemy deals
        self.cooldown = 0.3 # seconds between damages

        self.name = "Corrupt Gerry"

class Enemy5(Enemy): # corrupt tom
    def __init__(self, x, y, server):
        super().__init__(x, y, 200, "", "E105", server)
        
        #movement AI stats
        self.mAIspeed = 1.5 # tile/second
        self.mAIrange = 10 # tiles

        self.target_finding_method = 1

        #combat AI stats 
        self.cAIrange = 2.5 # tiles
        self.cAIcount = 1

        self.damage = 20 # how many points the enemy deals
        self.cooldown = 0.2 # seconds between damages

        self.name = "Corrupt Tom"

class Enemy6(Enemy): # corrupt spanish inquisition
    def __init__(self, x, y, server):
        super().__init__(x, y, 300, "", "E106", server)
        
        #movement AI stats
        self.mAIspeed = 2 # tile/second
        self.mAIrange = 15 # tiles

        self.target_finding_method = 2

        #combat AI stats 
        self.cAIrange = 3 # tiles
        self.cAIcount = 1

        self.damage = 20 # how many points the enemy deals
        self.cooldown = 0.1 # seconds between damages

        self.name = "Corrupt Spanish Inquisition"

class Enemy7(Enemy): # corrupt rick astley
    def __init__(self, x, y, server):
        super().__init__(x, y, 500, "", "E107", server)
        
        #movement AI stats
        self.mAIspeed = 2 # tile/second
        self.mAIrange = 20 # tiles

        self.target_finding_method = 2

        #combat AI stats 
        self.cAIrange = 3 # tiles
        self.cAIcount = 2

        self.damage = 20 # how many points the enemy deals
        self.cooldown = 0.2 # seconds between damages

        self.name = "Corrupt Rick Astley"


class MotionParticle(Entity):
    def __init__(self, startx, starty, endx, endy, server, speed = 5, texture = "BulletParticle", priority=False):
        super().__init__(startx, starty, 0, 0, "", texture)
        self.lastupdate = time.time()
        self.accepts_damage = False
        self.server = server
        server.particles.append(self)
        if priority:
            server.entities.append(self) # has to go last to be on top
        else:
            server.entities.insert(0,self) # has to go first to underneath
        #calculate how far to move each second
        self.target = Vector2D(endx, endy)
        self.velocity = ( self.target + -1*self.position )
        self.time = abs(self.velocity) / speed
        self.velocity.set_to_magnitude(speed)

    def update(self):
        #move towards the target
        time_elapsed_since_last_update = time.time() - self.lastupdate
        self.time -= time_elapsed_since_last_update
        if self.time <= 0: # must have finished
            self.finish()
        else:
            self.position = self.position + self.velocity * time_elapsed_since_last_update

    def finish(self):
        if self in self.server.entities:
            self.server.entities.remove(self)
        if self in self.server.particles:
            self.server.particles.remove(self)

class BulletParticle(MotionParticle):
    def __init__(self, x, y, ex, ey, server):
        super().__init__(
            x, y, 
            ex, ey,
            server,
            5,
            "BulletParticle"
        )

class DamageParticle(MotionParticle):
    def __init__(self, x, y, server):
        super().__init__(
            x+0.5, y-0.5, 
            x + random.random()*2-0.5,
            y + random.random()*2-1.5,
            server,
            1,
            "DamageParticle",
            priority=True
        )


class TagHolder(Entity):
    def __init__(self, text, x, y, texture):
        super().__init__(x, y, 0, 1, text, texture)
        self.accepts_damage = False
    def die(self, killer):
        print("Error, tag holder killed?")
        pass # override with nothing so that this does not get killed

class InteractiveTagHolder(Entity):
    def __init__(self, text, x, y, texture, function):
        super().__init__(x, y, 0, 1, text, texture)
        self.function = function # the function that will be called when the button is pressed
    def die(self, killer):
        self.accepts_damage = False
        # print(f"{killer.tag} pressed button with text {self.tag}")
        # # call teh function specified in the declaration
        self.function(killer, self)

class ItemHolder(Entity): # just a class to represent a dropped item
    def __init__(self, x, y, texture, parentItem):
        super().__init__(x, y, 0, -1, "", texture)
        self.item = parentItem
        self.accepts_damage = False
    def die(self, killer):
        print("Error, item holder killed?")
        pass # override with nothing so that this does not get killed
    def pickup(self, picker): # reference to the player entity picking up the item, so that the item can attach itself to the player
        #remove self as this is just the holding item so that the item has a presence in teh world
        if self in self.item.server.entities:
            self.item.server.entities.remove(self) # remove self from entities list
        if self in self.item.server.droppeditems:
            self.item.server.droppeditems.remove(self) # remove self from entities list
        self.item.pickup(picker)

class AmmoHolder(ItemHolder):
    def __init__(self, x, y, quantity, server):
        super().__init__(x, y, "D50", None)
        self.accepts_damage = False
        self.quantity = quantity
        self.server = server

        self.can_be_picked_up_after = time.time() + 2 # seconds in the future
        self.pickable = False

        if self.quantity > 0 : # only if the holder is needed:
            #add self to server things to make sure it exists in the world
            self.server.entities.insert(0,self)
            self.server.droppeditems.append(self)

    def pickup(self, picker):
        if not self.pickable:
            if self.can_be_picked_up_after < time.time():
                self.pickable = True  #this is seperated like this beccuase otherwise it will use up more resoruces if it is not entirely picked at once

        if self.pickable:
            remaining = picker.add_ammo(self.quantity)
            if remaining > 0: # keep holder on the floor, just with less value
                self.quantity = remaining

            else:
                #all used up so delete self
                if self in self.server.entities:
                    self.server.entities.remove(self) # remove self from entities list
                if self in self.server.droppeditems:
                    self.server.droppeditems.remove(self) # remove self from entities list
        

class Item: # usually this will be a weapon, but generally this is something that a player can hold
    def __init__(self, server, name, dropTEX, rotTEXs, parent=None):
        self.server = server # reference to the main server
        self.name = name
        self.dropped_texture = dropTEX
        self.rotational_textures = rotTEXs # list of 8 angled textures starting at 1:30 and going clockwise TODO decide proper starting point, 1:30 correct angle????
        self.parent = parent # None if there is no parent, ref to Player object if there is a parent
        self.itemholder = None # starting without anything
        if self.parent == None: # need to initalise with an item holder (put at world spawn) # TODO give each player a weapon when they join, but drop it when the disconnect
            x, y = self.server.world["spawn"]
            self.itemholder = ItemHolder(x, y, self.dropped_texture, self)
            self.server.entities.append(self.itemholder)
            self.server.droppeditems.append(self.itemholder)
        self.renderlayer = "B" # background

    def use(self):
        pass # this will be overriten by children, this is what is called by the player when the use button is pressed (also called attack) so for a weapon it would be the firing function
    
    def drop(self):
        #get coordinates of player to drop at
        x, y = self.parent.position.x, self.parent.position.y
        #tell parent that it is being dropped and to remove it's pointers
        self.parent.drop_item()
        #erase parent reference
        self.parent = None
        #create item holder at player's coords
        self.itemholder = ItemHolder(x, y, self.dropped_texture, self)
        self.server.entities.append(self.itemholder)
        self.server.droppeditems.append(self.itemholder)

    def pickup(self, parent):
        self.parent = parent
        self.parent.holding = self
        # # remove itemholder
        # self.itemholder.pickup(parent)

    def __str__(self): # used by player when compiling HUD data
        return self.name



class MeleeWeapon(Item):
    def __init__(self, server, name,  dropTEX, rotTEXs, parent=None):
        super().__init__(server, name, dropTEX, rotTEXs, parent)
        self.damage = 1
        self.cooldown = 1 # these will be overwritten by children with their stats
        self.cooldowntimer = 0
        self.range = 1.5
    #combat specific functions
    def use(self): # override to deal damage and use // called by parent
        if time.time() - self.cooldowntimer > self.cooldown: # timer has passed time and so should be allowed to fire weapon
            centre_of_attack = self.parent.position.copy()
            #attack the nearest entity within range, but also checkign PVP
            PvP = self.server.pvp_enabled
            #calculate nearest entities, sorted by ditance from centre of attack
            targets = []
            for entity in self.server.entities:
                if not (entity is self.parent): # validation to check that not attacking self
                    ent_pos = entity.position.copy()
                    distance = abs(ent_pos + (centre_of_attack * -1))
                    if distance < self.range: # only test for those that are in range, this saves time in the following sort too:: more optimisation
                        targets.append((entity, distance))
            #sort them
            targets.sort(key=lambda x: x[1]) # sort by distance
            #calculate entity to deal damage to 
            target = self.parent # must start with entity so that it can check against entity properies
            ind = 0
            while ( (target is self.parent) or ((type(target) is Player) == (not PvP)) or (not target.accepts_damage) ) and ind < len(targets): # keep going until found target
                target = targets[ind][0]
                ind += 1
            if target != None and target.accepts_damage and not ((type(target) is Player) and not PvP) and not (target is self.parent): # a target was found, and it is allowing it to be damaged (this is needed because if the last target in targets was not accepting damage it will not be replaced)
                target.take_damage(self.parent, self.damage)
                #reset timer only if used
                self.cooldowntimer = time.time()
                #add to XP
                self.parent.XP += self.damage


class WoodenStick(MeleeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D00"
        rotTEXs = ("W000","W001","W002","W003","W004","W005","W006","W007")
        super().__init__(server, "Wooden Stick", dropTEX, rotTEXs, parent)
        self.damage = 2
        self.cooldown = 0.1

class MetalPole(MeleeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D01"
        rotTEXs = ("W010","W011","W012","W013","W014","W015","W016","W017")
        super().__init__(server, "Metal Pole", dropTEX, rotTEXs, parent)
        self.damage = 5
        self.cooldown = 0.2

class Axe(MeleeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D02"
        rotTEXs = ("W020","W021","W022","W023","W024","W025","W026","W027")
        super().__init__(server, "Axe", dropTEX, rotTEXs, parent)
        self.damage = 10
        self.cooldown = 0.2

class BroadSword(MeleeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D03"
        rotTEXs = ("W030","W031","W032","W033","W034","W035","W036","W037")
        super().__init__(server, "Broad Sword", dropTEX, rotTEXs, parent)
        self.damage = 15
        self.cooldown = 0.3
 

class RangeWeapon(Item):
    def __init__(self, server, name,  dropTEX, rotTEXs, parent=None):
        super().__init__(server, name, dropTEX, rotTEXs, parent)
        self.renderlayer="F" # this type of item should render on top of the player
        self.damage = 20 # placeholder value, overwritten by child
        self.cooldown = 0.5 # placeholder value, overwritten by child
        self.lastfiretime = 0
        self.max_check_distance = 7 # tiles checked before giving up the search (saves resources)

    #combat specific functions
    def use(self): # override to deal damage and use // called by parent
        #determine by cooldown if can fire:,, and then by ammo cound
        if time.time() - self.lastfiretime >= self.cooldown and (self.parent.ammo >= 1 or self.server.world["name"] == "Lobby World"): # can fire
            self.lastfiretime = time.time() # reset as firing
            self.parent.ammo -= 1 # deduct ammo no matter what
            #find target to deal damage to
            target = self.calculate_target(self.parent.aim)
            if target != None:
                if not ( type(target[0]) is WallTile ): # can deal damage, so should
                    target[0].take_damage(self.parent, self.damage)
                    #add to XP
                    self.parent.XP += self.damage

                #create particle to give player visual feedback
                if self.parent != None: # (only if not suddenly changed world! -> weapon would become no longer attached to player by the line above)
                    x, y = self.parent.position.totuple()
                    tx, ty = target[2:4] # position of either wall or entity
                    BulletParticle(x+0.5, y-0.5, tx, ty, self.parent.server)

    def calculate_target(self, aimvec):
        """this function uses player position and either returns a reference to the entity that is targeted, or None if nothing was found before a wall or max distance"""
        PvP = self.server.pvp_enabled

        #get current player values
        x, y = self.parent.position.totuple() # centre of attack
        x += 0.5 # offset to centre of the player
        y += 0.5
        ax, ay = aimvec.totuple()
        ay = -ay # invert ay to correct issue

        #generate a general point that will be used only if nothing else is found, to show the player that something has indeed been fired
        mag = (ax**2 + ay**2)**0.5
        if mag == 0:
            return None# cancel action
        dist = 1000 / mag
        tx = ax * dist
        ty = ay * dist
        generalpoint = (
            WallTile(int(tx), int(ty)), 
            self.max_check_distance + 1,
            tx, 
            ty
        )
        targets = [generalpoint] # a list of all entities and tiles within range and also in path and accepting damage if an entity, with their distance from the centre of attack
        

        def check_colliding(x, y, ax, ay, ex, ey): # this is a function so that it can be used by both the eneity search as well as the tile serach without repeating any code unnecessarily
            colliding = False
            collidingx = 0
            collidingy = 0
            collidedist = 100000 # large number that any other distance will certainly be smaller than

            if ay != 0: # check the top side
                l = ( 
                    (ey + 1 - y) /
                    ay
                    ) # the x position where the line of the top side intersects the line of the aim vector
                if l > 0: # this is only true if firing forwards out of weapon
                    alpha = x + ax*l                    
                    this_colliding = (ex <= alpha and alpha <= ex+1 )
                    
                    colliding = colliding or this_colliding

                    if this_colliding: # only consider change if just altered
                        dist = ( (ex-x)**2 + (ey-y)**2 )**0.5
                        if dist < collidedist: # closer to change distance
                            collidingx = alpha
                            collidingy = ey + 1
                            collidedist = dist

            if ay != 0: # check the bottom side
                l = ( 
                    (ey - y) /
                    ay
                    ) # the x position where the line of the bottom side intersects the line of the aim vector
                if l > 0: # this is only true if firing forwards out of weapon
                    alpha = x + ax*l
                    this_colliding = (ex <= alpha and alpha <= ex+1 )

                    colliding = colliding or this_colliding

                    if this_colliding: # only consider change if just altered
                        dist = ( (ex-x)**2 + (ey-y)**2 )**0.5
                        if dist < collidedist: # closer to change distance
                            collidingx = alpha
                            collidingy = ey
                            collidedist = dist

            if ax != 0: # check the right side
                l = ( 
                    (ex + 1 - x) /
                    ax
                    ) # the y position where the line of the right side intersects the line of the aim vector
                if l > 0: # this is only true if firing forwards out of weapon
                    alpha = y + ay*l                        
                    this_colliding = (ey <= alpha and alpha <= ey+1 )

                    colliding = colliding or this_colliding

                    if this_colliding: # only consider change if just altered
                        dist = ( (ex-x)**2 + (ey-y)**2 )**0.5
                        if dist < collidedist: # closer to change distance
                            collidingx = ex + 1
                            collidingy = alpha
                            collidedist = dist

            # need to check all 4 sides now that i need to determine where the projectile will collide too!
            if ax != 0: # check the left side
                l = ( 
                    (ex - x) /
                    ax
                    ) # the y position where the line of the right side intersects the line of the aim vector
                if l > 0: # this is only true if firing forwards out of weapon
                    alpha = y + ay*l                        
                    this_colliding = (ey <= alpha and alpha <= ey+1 )

                    colliding = colliding or this_colliding

                    if this_colliding: # only consider change if just altered
                        dist = ( (ex-x)**2 + (ey-y)**2 )**0.5
                        if dist < collidedist: # closer to change distance
                            collidingx = ex
                            collidingy = alpha
                            collidedist = dist

            return colliding, collidingx, collidingy-1
                
        #check all entities within range
        for ent in self.server.entities: # all entities in the world
            ex, ey = ent.position.totuple() # entity x and y position
            distance = ( (ex - x) ** 2 + (ey - y) ** 2 ) ** 0.5 # use pythag to calcualte distance from centre of attack
            if ent.accepts_damage and (not ent is self.parent) and distance < self.max_check_distance and not ((type(ent) is Player) and not PvP): # only bother doing anything if it is able to accept damage, so excluding tagholders
                colliding, collidex, collidey = check_colliding(x, y, ax, ay, ex, ey)
                if colliding:
                    targets.append((ent, distance, collidex, collidey))
        
        #check all tiles within range
        for tile in self.server.tiles: # all tiles in the world
            tx, ty = tile.x, tile.y # tile coords
            distance = ( (tx - x) ** 2 + (ty - y) ** 2 ) ** 0.5 # use pythag to calcualte distance from centre of attack
            if tile.solid and distance < self.max_check_distance:
                colliding, collidex, collidey = check_colliding(x, y, ax, ay, tx, ty)
                if colliding:
                    targets.append((tile, distance, collidex, collidey))
        
        #order targets in order of distances from the player
        targets = sorted(targets, key=lambda tup: tup[1])
                
        if len(targets) > 0:
            # return target, beign wall or entity
            return targets[0]
        else:
            return None


class Pistol(RangeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D10"
        rotTEXs = ("W100","W101","W102","W103","W104","W105","W106","W107")
        super().__init__(server, "Pistol", dropTEX, rotTEXs, parent)
        self.damage = 20
        self.cooldown = 0.5
 
class Revolver(RangeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D11"
        rotTEXs = ("W110","W111","W112","W113","W114","W115","W116","W117")
        super().__init__(server, "Revolver", dropTEX, rotTEXs, parent)
        self.damage = 20
        self.cooldown = 0.4

class Shotgun(RangeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D12"
        rotTEXs = ("W120","W121","W122","W123","W124","W125","W126","W127")
        super().__init__(server, "Shotgun", dropTEX, rotTEXs, parent)
        self.damage = 5 # TODO this will be different when actually implementing algorithm
        self.cooldown = 0.5
    def use(self): # override to deal damage and use // called by parent
        #determine by cooldown if can fire:,, and then by ammo cound
        if time.time() - self.lastfiretime >= self.cooldown and (self.parent.ammo >= 3 or self.server.world["name"] == "Lobby World"): # can fire
            self.lastfiretime = time.time() # reset as firing
            self.parent.ammo -= 3 # deduct ammo no matter what
            #gen all aim vectors
            vecs = []
            vecs.append(self.parent.aim.get_copy_rotated_radians(0.19))
            vecs.append(self.parent.aim.get_copy_rotated_radians(-0.19))
            vecs.append(self.parent.aim)
            #find target to deal damage to, for each projectile
            for vec in vecs:
                target = self.calculate_target(vec)
                if target[0] != None:
                    if not ( type(target[0]) is WallTile ): # can deal damage, so should
                        target[0].take_damage(self.parent, self.damage)
                    #create particle to give player visual feedback
                    x, y = self.parent.position.totuple()
                    tx, ty = target[2:4] # position of either wall or entity
                    BulletParticle(x+0.5, y-0.5, tx, ty, self.parent.server)

class SniperRifel(RangeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D13"
        rotTEXs = ("W130","W131","W132","W133","W134","W135","W136","W137")
        super().__init__(server, "Sniper Rifel", dropTEX, rotTEXs, parent)
        self.damage = 40
        self.cooldown = 0.5

class GatlingGun(RangeWeapon):
    def __init__(self, server, parent = None):
        dropTEX = "D14"
        rotTEXs = ("W140","W141","W142","W143","W144","W145","W146","W147")
        super().__init__(server, "Gatling Gun", dropTEX, rotTEXs, parent)
        self.damage = 40
        self.cooldown = 0.1


class Player(Entity):
    def __init__(self, server, name):
        #get spawn x and y
        x,y = server.world["spawn"]
        super().__init__(x, y,10,100,name, "E00"+str(random.randint(0,7)))
        self.tag = f"{name}#00ff00 [{self.health}]"

        if name == "spectator":
            self.tag = ""
            self.name = ""
            self.texture = "BLANK"
            self.holding = None
            self.accepts_damage = False

        self.lastupdate = time.time()
        self.server = server
        self.name = name # name will never change, tag may do though

        #used to make sure that items are not picked or dropped quicker than the player intends
        self.pick_last_time = 0
        self.pick_time_threshold = 0.2
        self.drop_last_time = 0
        self.drop_time_threshold = 0.1

        self.aim = Vector2D()

        self.huddata = ""

    def die(self, killer):
        self.tag = f"{self.name}#ff0000 [DEAD]"
        self.server.add_to_log(killer.killmsg(self.name))
        self.accepts_damage = False
        #check to see if all players have died now, if all are dead then reset by loading lobby
        if self.server.world["name"][:13] == "Battle Royale": # in battle royale, if all other players dead then reset
            self.drop_everything() # make sure that nothing the player is carrying is going to be stuck out of the world, so remaining players can use the items
            #drop extra ammo as loot for killer
            AmmoHolder(self.position.x, self.position.y, random.randint(1,10), self.server) # randomly drop 1-10 pieces of ammunition as reward

            survivingplayers = 0
            lastplayer = None
            for _, player in self.server.players.items():
                if player.accepts_damage: 
                    survivingplayers += 1
                    lastplayer = player
            if survivingplayers <= 1: # only if there is one or less players alive then reset
                self.server.add_to_log(f"Round Won by {lastplayer.name}: Resetting to lobby...")
                self.server.load_lobby_world(message = f"Last Surviving player was #ffff00{lastplayer.name}")
        
        else: # if players all dead then reset
            self.drop_everything() # make sure that nothing the player is carrying is going to be stuck out of the world, so remaining players can use the items
            reset = True
            for _, player in self.server.players.items():
                if player.accepts_damage: 
                    reset = False
                    break
            if reset:
                self.server.add_to_log("All Players Dead: Resetting to lobby...")
                self.server.load_lobby_world(message = f"Last Surviving player was #ffff00{self.name}") 
            


    def killmsg(self, killedname):
        return f"{killedname} was killed by {self.name} using {self.holding.name}"

    def take_damage(self, dealer, quantity):
        super().take_damage(dealer, quantity)
        #change tag to refect current status of being alive
        if self.health > self.maxhealth * 0.5: # green if health above 50%
            self.tag = f"{self.name}#00ff00 [{self.health}]"
        elif self.health > self.maxhealth * 0.2: # yellow if health 50%-20%
            self.tag = f"{self.name}#ffff00 [{self.health}]"
        elif self.health > 0: # red if below 20%
            self.tag = f"{self.name}#ff0000 [{self.health}]"

        x, y = self.position.totuple()
        for _ in range(quantity): # spawn one per damage dealt -> feedback on how much damage too!
            DamageParticle(x, y, self.server)

    def giveitem(self, item): # this is called when a player joins so that they will have a weapon to start with // creates an item and gives it to the player
        #TODO validate to check that not already holding something
        self.holding = item
        item.pickup(self)

    def update(self, infostring):

        def teleport_to_spawn(): # called if out of bounds error
            #set the coordinates to those of the world spawn point
            self.position.x , self.position.y = self.server.world["spawn"]
            self.velocity = Vector2D() # reset velocity to 0 too

        # movement, aim, crouch, pick/swap/drop item, drop ammo, hud screen 2 (extra info)
        mx, my, ax, ay, crouch, attack, pick, dropammo, collectammo, info = infostring.split("|") # obtained from client of player

        #calculate time since last update
        t = time.time()-self.lastupdate
        self.lastupdate = time.time()

        if t > 0.5/self.terminalVelocity:
            t = 0.5/self.terminalVelocity # cap to threshold, to prevent teleporting glitch when client is paused by any means, making it possible to travel a large distance in one go if the time recorded is not capped

        #calculate new velocity and position
        self.velocity = Vector2D(float(mx), float(my)) * t # temporarily just set velocity to movement vector, normalised to terminal velocity
        # normalise or normalise to capped:        
        if abs(self.velocity) > 0: # avoid div by 0
            if bool(int(crouch)): # move slower
                compensation = (self.terminalVelocity / 2) / abs(self.velocity)
                self.velocity = self.velocity * compensation
            else:
                compensation = self.terminalVelocity / abs(self.velocity)
                self.velocity = self.velocity * compensation

        # store old position
        ox, oy = self.position.totuple()

        #update position
        self.position = self.position + self.velocity * t
        
        #collision detection
        
        #### as general rule, each player hitbox is 90% of width, with 5% missing off each side
        # to get tile at (x, y), use self.world["tiles"][y][x]

        px = self.position.x
        py = self.position.y

        #offset derived from 1-90% / 2 => 0.05
        offset = 0.05
        #when checking, the non-focus axis should use the previous coordinate becacuse otherwise it causes a very jittrey mess when moving through 1 wide gaps or against walls in general

        #accepts_damage is only False when dead, so should be spectating anyway
        if self.velocity.x > 0 and self.accepts_damage: #is the x coord increasing according to velocity// so need to check right side and decrese position if colliding
            #must be moving to the right
            #calc corners to check
            corners = (
                (px + 1 - offset, oy+offset), # bottom right
                (px + 1 - offset, oy+1-offset), # top right
            )
            #check each corner to see if need to back up to border line
            reverse = False
            for x, y in corners:
                #check if the corner is in a wall tile
                try:
                    if type(self.server.world["tiles"][int(y)][int(x)]) is WallTile: # int is effectively floor function // truncate
                        #check to see that player is not on y boundary
                        if y % 1 == 0: # if y is whole number exactly => exepmtion because traveling against wall, and probably in 1 block high gap
                            pass
                        else: # not on boundary
                            reverse = True
                except KeyError: # caused by out of bounds and no tile information
                    teleport_to_spawn()
                    
            if reverse: # must back out to exactly edge of tile
                self.position.x -= px % 1 - offset #subtract the distance into the tile it is
                self.velocity.x = 0 # reset velocity to 0

        if self.velocity.x < 0 and self.accepts_damage: #is the x coord decreasing according to velocity// so need to check leftt side and increase position if colliding
            #must be moving to the right
            #calc corners to check
            corners = (
                (px + offset, oy+offset), # bottom left
                (px + offset, oy+1-offset), # top left
            )
            #check each corner to see if need to back up to border line
            reverse = False
            for x, y in corners:
                #check if the corner is in a wall tile
                try:
                    if type(self.server.world["tiles"][int(y)][int(x)]) is WallTile: # int is effectively floor function // truncate
                        #check to see that player is not on y boundary
                        if y % 1 == 0: # if y is whole number exactly => exepmtion because traveling against wall, and probably in 1 block high gap
                            pass
                        else: # not on boundary
                            reverse = True
                except KeyError: # caused by out of bounds and no tile information
                    teleport_to_spawn()
                    
            if reverse: # must back out to exactly edge of tile
                self.position.x += 1 - (px % 1) - offset #add the distance into the tile it is
                self.velocity.x = 0 # reset velocity to 0
        
        if self.velocity.y > 0 and self.accepts_damage: #is the y coord increasing according to velocity// so need to check top side and decrese position if colliding
            #must be moving to the right
            #calc corners to check
            corners = (
                (ox + offset, py+1-offset), # top left
                (ox + 1-offset, py+1-offset), # top right
            )
            #check each corner to see if need to back up to border line
            reverse = False
            for x, y in corners:
                #check if the corner is in a wall tile
                try:
                    if type(self.server.world["tiles"][int(y)][int(x)]) is WallTile: # int is effectively floor function // truncate
                        #check to see that player is not on y boundary
                        if x % 1 == 0: # if x is whole number exactly => exepmtion because traveling against wall, and probably in 1 block high gap
                            pass
                        else: # not on boundary
                            reverse = True
                except KeyError: # caused by out of bounds and no tile information
                    teleport_to_spawn()
                    
            if reverse: # must back out to exactly edge of tile
                self.position.y -= py % 1 - offset #subtract the distance into the tile it is
                self.velocity.y = 0 # reset velocity to 0
        
        if self.velocity.y < 0 and self.accepts_damage: #is the y coord decreasing according to velocity// so need to check bottom side and decrese position if colliding
            #must be moving to the right
            #calc corners to check
            corners = (
                (ox + offset, py+offset), # top left
                (ox + 1-offset, py+offset), # top right
            )
            #check each corner to see if need to back up to border line
            reverse = False
            for x, y in corners:
                #check if the corner is in a wall tile
                try:
                    if type(self.server.world["tiles"][int(y)][int(x)]) is WallTile: # int is effectively floor function // truncate
                        #check to see that player is not on y boundary
                        if x % 1 == 0: # if x is whole number exactly => exepmtion because traveling against wall, and probably in 1 block high gap
                            pass
                        else: # not on boundary
                            reverse = True
                except KeyError: # caused by out of bounds and no tile information
                    teleport_to_spawn()
                    
            if reverse: # must back out to exactly edge of tile
                self.position.y += 1 - (py % 1) - offset #add the distance into the tile it is
                self.velocity.y = 0 # reset velocity to 0

        #make sure that the pick button is not over-pressed too oftem
        t = time.time() - self.pick_last_time
    
        if bool(int(pick)) and t > self.pick_time_threshold or bool(int(collectammo)) and self.accepts_damage: # only trigger if needed to for next function, or if picking up
            #picking alforithm, this needs to be run all the time because it needs to automatically detect when walking over some ammo
            #determine which is the first added to the world stack and within range
            itemholder = None
            ind = 0
            while ind < len(self.server.droppeditems) and itemholder == None:  #break once itemholder found #this has the effect of cycling to the oldeset placed so all will be able to be picked up at some point of stacked
                totest = self.server.droppeditems[ind]
                ix, iy = totest.position.totuple()
                px, py = self.position.totuple()
                dist = ( (ix-px)**2 + (iy-py)**2 ) ** 0.5
                if dist < 0.8: #the threshold distance from the player to pick something up
                    #account for edge case of ammo! => pick up no matter what, as not an item
                    if type(totest) is AmmoHolder:
                        totest.pickup(self)                        
                    else:
                        itemholder = totest

                ind += 1

        if bool(int(pick)) and t > self.pick_time_threshold and self.accepts_damage:
            #check ground to pick up if that button is pressed TODO
            if self.holding == None:
                if itemholder != None: # something has been found to be picked up => pick it up
                    itemholder.pickup(self)
                    self.pick_last_time = time.time() # reset the timer because an action has been performed
            else:
                self.pick_last_time = time.time() # reset the timer
                #drop item if holding and that button is pressed
                self.holding.drop()
                #the following works because it remembers what it would pick up before placing the current item, and picks it up afterwards as to not cause any conflicts
                if itemholder != None: # need to swap => pick up previously found item
                    itemholder.pickup(self)

            #TODO add a timer so that it cannot be picked up immediately by the same player that dropped it (add player-side rather than item-side so that anyone can pick up the item, but the player will not immidiately cycle through tons of items on the ground uncontrollably) 
        elif not bool(int(pick)) and t > 0.05 and self.accepts_damage: # acts to debounce
            self.pick_last_time = 0
            #this has the effect of resetting, meaning that even if the button is pressed one frame, then not and then again, it should be pressed a second time because it has been re-pressed rather than held
        
        t = time.time() - self.drop_last_time
        #drop ammo if that button is pressed 
        if bool(int(dropammo)) and t > self.drop_time_threshold and self.accepts_damage:
            #create ammo holder with dropped ammo
            x, y = self.position.totuple()
            AmmoHolder(x, y, self.dropammo_getquantity(), self.server)
            self.drop_last_time = time.time()


        #use item if holding
        if bool(int(attack)) and self.holding != None and self.accepts_damage:
            self.holding.use()

        #calculate direction of item for rendering correct item
        ax = float(ax)
        ay = float(ay)
        
        if ax > 0:
            if ay > 0: 
                if abs(ay) > abs(ax): 
                    textureID = 3
                else: 
                    textureID = 2
            else:
                if abs(ay) > abs(ax): 
                    textureID = 0
                else: 
                    textureID = 1
        else:
            if ay > 0: 
                if abs(ay) > abs(ax): 
                    textureID = 4
                else: 
                    textureID = 5
            else:
                if abs(ay) > abs(ax):
                    textureID = 7
                else:
                    textureID = 6

        self.aim = Vector2D(ax, ay)

        self.rotational_textureID = textureID # so it knows that direction to send to the client


        #update HUD data
        self.sethuddata()       

    def drop_item(self): # called by Item
        self.holding = None # remove refernece

    def drop_everything(self):
        if self.holding != None: # need to drop item
            self.holding.drop()
        #drop ammo
        if self.ammo > 0:
            AmmoHolder(self.position.x, self.position.y, self.ammo, self.server)


    def sethuddata(self): # TODO uncomment this after testing
        if self.server.world["name"] == "Lobby World":
            self.huddata = f"Holding: {self.holding}\n \n \n " # don't display things that are unnecessary
        else:
            self.huddata = f"Holding: {self.holding}\nHealth: {self.health}/{self.maxhealth}\nAmmo: {self.ammo}/{self.maxammo}\nXP: {self.XP}"

class LogEntry:
    def __init__(self, msg, seconds = 6):
        self.txt = msg
        self.removeby = time.time()+seconds

class Server:
    def __init__(self, name, public = False, port = 80, playerlimit = 20, showallhud=False): # showallhud shows system usernames and IP addresses when holding TAB
        self.name = name
        self.public = public
        self.playerlimit = playerlimit

        self.SHOWALLHUD = showallhud

        self.logs = []
        self.compile_logs()

        self.users = {} # key = name, value = IP of users currently connected to the server
        self.sysusers = {} # key = ip, value = systemusername
        self.players = {} # key = name, value = Player object

        self.entities = []

        self.droppeditems = [] # holds all dropped items
        self.particles = [] # holds all particles
        self.enemies = [] # holds all enemies

        self.pvp_enabled = False

        self.load_lobby_world() # enter default world
        # self.generate_random_world()
        # self.load_random_world()

        self.port = port
        self.address = socket.gethostbyname(socket.gethostname())
        print(f"Hosting server on {self.address}")

        self.networkingthread = threading.Thread(target=self.serve_forever)
        self.networkingthread.start() # run the self.serve_forever() function in seperate thread

        self.entitythread = threading.Thread(target=self.entityupdatethread)
        self.entitythread.start() # run the function in seperate thread to update entities
        
        self.logthread = threading.Thread(target=self.log_thread)
        self.logthread.start() # run the function in seperate thread to update the pre-compiled log txt

    def entityupdatethread(self):
        last_t = time.time()
        while True: # update entity data
            #update all particles
            for particle in self.particles:
                particle.update()
            #update all enemies' AIs
            for enemy in self.enemies:
                enemy.update()
            #update all entity data
            #order is:     success ¦ players in server ¦ entity1|entity2|...       for example single user looks like:  Success¦1¦5,5,0,0,0,0,E000,em,100
            self.playerdata = ":".join([str(len(self.players)),
                "|".join([str(e) for e in self.entities])
            ])
            t = time.time() - last_t
            t = 0.02 - t
            if t > 0:
                time.sleep(t)
            last_t = time.time()

    def stop(self):
        #TODO smooth exit things like kicking all clients or whatever
         
        pass


    def serve_forever(self): # the API is the networking side of the server
        
        def shutdown(environ, start_response):
            #deal with http things
            address = environ["REMOTE_ADDR"]
            arg = environ["PATH_INFO"][1:]
            method = environ["REQUEST_METHOD"]
            # end http things
            print("shutting down")
            if address == self.address and method == "PUT": #only allow if from this device
                self.stop() # smooth exiting of game things

                #return "Success", 200
                status = '200 OK'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)
                return [bytes("Success", "utf-8")]
            # return "Access Denied", 403
            status = '403 Forbidden'
            response_headers = [('Content-type','text/plain')]
            start_response(status, response_headers)
            return [bytes("Access Denied", "utf-8")]

        def responde_to_probe(environ, start_response):
            #deal with http things
            address = environ["REMOTE_ADDR"]
            arg = environ["PATH_INFO"][1:]
            method = environ["REQUEST_METHOD"]
            # end http things
            if self.public and method == "GET":
                # return "WAMSERVERv02@"+self.name, 200 
                status = '200 OK'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)        
                return [bytes(f"WAMSERVERv02@{self.name}", "utf-8")]
            else:
                if (address==self.address) and method == "GET": # request coming from this device so must be allowed
                    # return "WAMSERVERv02@"+self.name, 200
                    status = '200 OK'
                    response_headers = [('Content-type','text/plain')]
                    start_response(status, response_headers)        
                    return [bytes(f"WAMSERVERv02@{self.name}", "utf-8")]
                else: # request coming from elsewhere so as private game must be denied
                    # return "Access Denied", 403
                    status = '403 Forbidden'
                    response_headers = [('Content-type','text/plain')]
                    start_response(status, response_headers)        
                    return [bytes("Access Denied", "utf-8")]
        
        def adduser(environ, start_response): # name is the proposed name of the client wanting to join
            #deal with http things
            address = environ["REMOTE_ADDR"]
            arg = environ["PATH_INFO"][1:]
            method = environ["REQUEST_METHOD"]
            name = arg.split("/")[0]
            sysuser = "NotSpecified" # default if IF is not triggered
            if len(arg.split("/")) > 1: # name is specified
                sysuser = arg.split("/")[1]
            # end http things
            if ( self.public or address==self.address ) and ( len(self.players) < self.playerlimit ): # if public or user from the same device
                #check to see if the name is available
                free = True 
                for n, ip in self.users.items():
                    if n == name:
                        free = False
                if verify.isvalidusername(name) and free: # name is available and valid: assign it
                    self.adduser(name, address, sysuser)
                    # return "Success", 200
                    status = '200 OK'
                    response_headers = [('Content-type','text/plain')]
                    start_response(status, response_headers)
                    return [bytes("Success", "utf-8")]
                else:
                    # return "Access Denied", 403
                    status = '403 Forbidden'
                    response_headers = [('Content-type','text/plain')]
                    start_response(status, response_headers)        
                    return [bytes("Access Denied", "utf-8")]
            else: # deined access
                # return "Access Denied", 403
                status = '403 Forbidden'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)        
                return [bytes("Access Denied", "utf-8")]

        def quituser(environ, start_response): # name is the name of the user wanting to leave
            #deal with http things
            address = environ["REMOTE_ADDR"]
            arg = environ["PATH_INFO"][1:]
            method = environ["REQUEST_METHOD"]
            name = arg.split("/")[0]
            # end http things
            if self.users[name] == address: # check to see if this is the user asking => required permission
                self.removeuser(name)
                # return "Success", 200
                status = '200 OK'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)
                return [bytes("Success", "utf-8")]
            else:
                # return "Access Denied", 403
                status = '403 Forbidden'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)        
                return [bytes("Access Denied", "utf-8")]

        def send_tiles(environ, start_response):
            #deal with http things
            address = environ["REMOTE_ADDR"]
            arg = environ["PATH_INFO"][1:]
            method = environ["REQUEST_METHOD"]
            # end http things
            #check to see that the source is in the game
            allowed = False
            for name, ip in self.users.items():
                if ip == address:
                    allowed = True
            if allowed:
                # return self.tiledata, 200   # fetch pre-compiled data 
                status = '200 OK'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)
                return [bytes(self.tiledata, "utf-8")] 
            else:
                # return "Access Denied", 403
                status = '403 Forbidden'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)        
                return [bytes("Access Denied", "utf-8")]

        def updateuser(environ, start_response): # name is the name of the user making the request
            #deal with http things
            address = environ["REMOTE_ADDR"]
            arg = environ["PATH_INFO"][1:]
            method = environ["REQUEST_METHOD"]
            name, details = arg.split("/")[0:2]
            # end http things
            if self.users[name] == address: # check to see if this is the user asking => required permission
                updatethread = threading.Thread(target = self.players[name].update, args = (str(details),))
                updatethread.start() # relay to player to update // this is in a seperate thread so that this update takes a little time for the response time of the server's sake
                try:
                    # return self.name+" ~ "+self.world["name"]+"\n"+self.players[name].huddata + self.huddata + "|" + self.logs_compiled_txt, 200
                    status = '200 OK'
                    response_headers = [('Content-type','text/plain')]
                    start_response(status, response_headers)
                    return [bytes(f"{self.name} ~ {self.world['name']}\n{self.players[name].huddata}{self.huddata}|{self.logs_compiled_txt}", "utf-8")] 
                except: # this fails the first time it is called because the huddata is yet to be generated, after that this is not an issue
                    # return self.name
                    status = '200 OK'
                    response_headers = [('Content-type','text/plain')]
                    start_response(status, response_headers)
                    return [bytes(f"{self.name}", "utf-8")] 
            else:
                # return "Access Denied", 403
                status = '403 Forbidden'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)        
                return [bytes("Access Denied", "utf-8")]

        def givedata(environ, start_response): # name is the name of the user making the request
            #deal with http things
            address = environ["REMOTE_ADDR"]
            arg = environ["PATH_INFO"][1:]
            method = environ["REQUEST_METHOD"]
            name = arg.split("/")[0]
            # end http things
            if self.users[name] == address: # check to see if this is the user asking => required permission
                # return "Success:" + self.players[name].tag +":"+ self.playerdata, 200 # retrieve pre-compiled list of data to save time
                status = '200 OK'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)
                return [bytes(f"Success:{self.players[name].tag}:{self.playerdata}", "utf-8")] 
            else:
                # return "Access Denied", 403
                status = '403 Forbidden'
                response_headers = [('Content-type','text/plain')]
                start_response(status, response_headers)        
                return [bytes("Access Denied", "utf-8")]
        

        d = wsgiserver.WSGIPathInfoDispatcher({
            "/shutdown": shutdown,
            "/probe": responde_to_probe,
            "/adduser": adduser,
            "/quituser": quituser,
            "/gettiles": send_tiles,
            "/updateuser": updateuser,
            "/getentityandserverdata": givedata,
            })# '/': webpage, TODO add this to server as an instructional webpage??
        self.add_to_log("Starting Server")
        server = wsgiserver.WSGIServer(d, host=socket.gethostbyname(socket.gethostname()), port=self.port)
        server.start()

    def removeuser(self, name):
        self.sysusers.pop(self.users.pop(name)) # remove from the users list and sysusers
        player = self.players.pop(name)
        self.entities.remove(  player  )   #remove from list of player objects,, and from entities (takign advantage of pop returning here)
        self.compilehuddata()        
        self.add_to_log(name+" left the game")
        player.drop_everything() # make sure that they drop all they were holding as if they had been killed.
        
        if self.world["name"] == "Lobby World" and len(self.players) <= 2:
            self.world["entities"][0].accepts_damage = False # disable battle royale # entity 0 is the play battle royale game button
            self.world["entities"][0].tag = "#ff0000[Not enough players]"


    def adduser(self, name, address, sysuser = "NotSpecified"): # TODO determine giving player item properly in this function call other function to do so, and call that when loading lobby too, also remove when loading anything other than lobby
        self.users[name] = address
        self.sysusers[address] = sysuser # LOG system username
        p = Player(self, name)
        self.players[name] = p
        self.entities.append(p) # add to general entities list
        self.compilehuddata()
        self.add_to_log(name+" joined the game")

        if self.world["name"] == "Lobby World" and name != "spectator": # give them a weapon to interact with the buttons, only if they join in the lobby
            p.giveitem(MetalPole(self, p))
            if len(self.players) > 2:
                self.world["entities"][0].accepts_damage = True # enable battle royale
                self.world["entities"][0].tag = "#00ff00Play Battle Royale [PvP]"

    def compilehuddata(self):
        self.huddata = "\nPlayers ["+str(len(self.players))+"]:\n" + "\n".join([f"  {p.name} [{self.sysusers[self.users[n]]} on {self.users[n]}]" if self.SHOWALLHUD else f"  {p.name}" for n, p in self.players.items()])

    def generate_random_world(self):
        tempworld = {
            "spawn": (30,30), # world spawn, where players start off
            "tiles": {},
            "name": "Game World",
            "entities": [ # list of entities
                # InteractiveTagHolder("#00ff00Return to Lobby", 33, 33, "PRESS", self.returntolobbybutton),
            ]
        }

        #generate ground tiles
        
        lb=2 # bounds of the area allowed to be used
        ub=58
        centretarget = (30,30) # spawn
        positions = [centretarget] #add spawn and lines almost gauranteed to connect to another part of the world to make spawn always in the middle and accessible to all parts of the world
        positions += [(centretarget[0],y) for y in range(centretarget[1]-20, centretarget[1]+20)]
        positions += [(x,centretarget[1]) for x in range(centretarget[0]-20, centretarget[0]+20)]
        #actual random generation
        for _ in range(35):
            currpos = (random.randint(lb+15,ub-15),random.randint(lb+15,ub-15)) # random starting point, based on where is a good place to start from

            for n in range(100): # run each path 100 places
                # calculate which directions are preferred, this was not in the original specification for this algorithm, 
                # but since writing i decided that it needs to just eliminate the option of going outside of the standard coordinates, which are dermined by the bounds (lb, ub)
                biaseddirections = []
                for direct in [(0,1),(0,-1),(1,0),(-1,0)]:
                    newx = currpos[0] + direct[0]
                    newy = currpos[1] + direct[1]
                    if newx > lb and newx < ub and newy > lb and newy < ub:
                        biaseddirections += [direct] # only add if not violating position restraints

                if len(biaseddirections) > 0: # apply the direction randomly
                    dv = random.choice(biaseddirections)
                    currpos = (currpos[0]+dv[0], currpos[1]+dv[1])

                if not currpos in positions:
                    positions.append(currpos)

        #remove detached ground tiles

        goodpositions = [] # will contatin all attached positions
        def recur_search(x, y, depth = 0):
            if depth < 800:# maximum number of recursions
                if (x, y) in positions:
                    goodpositions.append((x, y))
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        if not (x+dx, y+dy) in goodpositions:
                            recur_search(x+dx, y+dy, depth+1)

        recur_search(centretarget[0], centretarget[1]) # start the search at the centre of the world

        #add ground tiles to dict
        for x, y in goodpositions:
            if not y in tempworld["tiles"]: # if row not already there, make sure that the row exists
                tempworld["tiles"][y] = {}
            tempworld["tiles"][y][x] = GroundTile(x, y)

        #now generate positions of all wall tiles 
        for pos in positions: 
            #add tiles for all 8 positions adjacent to the ground                
            for adj in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                currx, curry = pos[0] + adj[0], pos[1] + adj[1] # current coordinates are tehh coordinates of the proposed wall
                wall = True
                for innerpos in positions:
                    if curry in tempworld["tiles"]: # y coordinate exists in world
                        if currx in tempworld["tiles"][curry]: # tile has already been assigned => it must not be reassigned
                            wall = False # it could already be a wall or ground, but whatever it doesn't want to be overwritten
                if wall:
                    #add the wall to the world
                    if not curry in tempworld["tiles"]: # if row not already there, make sure that the row exists
                        tempworld["tiles"][curry] = {}
                    tempworld["tiles"][curry][currx] = WallTile(currx, curry)


        #set the new world
        self.randomworld = tempworld

    def spawnrandomammo(self, quantity):
        #spawn random ammo
        while quantity > 0:
            #try to find a position
            proposedx = -1
            proposedy = -1
            def isntfree(propx, propy):
                try:
                    return type(self.world["tiles"][propy][propx]) != GroundTile
                except KeyError: # cannot find position specified
                    return True
            while isntfree(proposedx, proposedy):
                proposedx = random.randint(1,60)
                proposedy = random.randint(1,60)  # try new random position

            #position has been found
            proposedammo = random.randint(1,10)
            if quantity < proposedammo:
                proposedammo = quantity # if barely any left, deduct all remaining
            #spawn ammo to position with quantity
            quantity -= proposedammo
            AmmoHolder(proposedx, proposedy, proposedammo, self)
    
    def spawnrandomitems(self, quantity, bias=0, proximitycentre=(30,30), proximity=30): #centre of square and shortest radius of spawning area (default is whole map)
        #spawn random ammo
        while quantity > 0:
            #try to find a position
            proposedx = -1
            proposedy = -1
            def isntfree(propx, propy):
                try:
                    return type(self.world["tiles"][propy][propx]) != GroundTile
                except KeyError: # cannot find position specified
                    return True
            while isntfree(proposedx, proposedy):
                proposedx = random.randint(proximitycentre[0]-proximity,proximitycentre[0]+proximity)
                proposedy = random.randint(proximitycentre[1]-proximity,proximitycentre[1]+proximity)  # try new random position, within the area defined

            #spawn item in determined position according to bias
            quantity -= 1

            r = random.randint(1, 8) + bias # bias will make it more likely to be either a better or worse weapon
            if r <= 1:
                item = WoodenStick(self)
            elif r == 2:
                item = MetalPole(self)
            elif r == 3:
                item = Axe(self)
            elif r == 4:
                item = BroadSword(self)
            elif r == 5:
                item = Pistol(self)
            elif r == 6:
                item = Revolver(self)
            elif r == 7:
                item = Shotgun(self)
            elif r == 8:
                item = SniperRifel(self)
            else:
                item = GatlingGun(self)

            item.itemholder.position = Vector2D(proposedx, proposedy) # set to the position specified

    def load_random_world(self):
        self.world = self.randomworld # set the current world data to be the world data generated beforehand ahead of time
        self.set_tile_data()
        self.reset_to_new_entities()
        self.pvp_enabled = False

        self.spawnrandomammo(300) # spawn 100 ammo randomly throughout the world
        self.spawnrandomitems(10, bias=-4, proximitycentre=(30,30), proximity=5) # spawn 3 times as many items as there are players
        

        # #TODO remove this; it is temp for testing world switching
        # for name, player in self.players.items():
        #     if name != "spectator":
        #         player.giveitem( WoodenStick(self, player) )

        #start the game loop
        self.donormalgameloop = True
        #start management thread
        self.normalgamethread = threading.Thread(target=self.normalgameloop)
        self.normalgamethread.start() # run the function in seperate thread 


        self.add_to_log("...done")

    def normalgameloop(self):
        def totalplayerXP():
            #returns the sum of all player's XP
            total = 0
            for player in self.players:
                total += self.players[player].XP
            return total

        def spawnenemy(x, y, difficulty):
            if difficulty <= 1:
                Enemy0(x, y, self)
            elif difficulty == 2:
                Enemy1(x, y, self)
            elif difficulty == 3:
                Enemy2(x, y, self)
            elif difficulty == 4:
                Enemy3(x, y, self)
            elif difficulty == 5:
                Enemy4(x, y, self)
            elif difficulty == 6:
                Enemy5(x, y, self)
            elif difficulty == 7:
                Enemy6(x, y, self)
            else:
                Enemy7(x, y, self)

        start_time = time.time()
        lastitemdrop = 0
        while self.donormalgameloop:
            time.sleep(0.1)
            t = time.time()-start_time # time the game has been running
            #drop more items based on XP
            if t-lastitemdrop > 60: # drop an item every __ seconds
                lastitemdrop += 60
                b = (totalplayerXP() // 100) - 3 # determine bias so more XP -> better drops
                self.spawnrandomitems(1, bias = b)
                #spawn in some random ammunition too
                self.spawnrandomammo(30)
            #enemy spawning:
            tnormal = t % 20 # what part through a 20 second cycle it is
            if t > 10 and 0 < tnormal and tnormal < 1:
                difficulty = t//120 + 1 #this means that difficulty starts at 1 at the beginning, and increases every <seconds specified>
                

                #determine how many enemies to spawn in each group 
                if difficulty < 3:
                    clumpsize = 3
                elif difficulty < 7:
                    clumpsize = 6
                else:
                    clumpsize = 15

                #self.add_to_log(f"spawning {difficulty} groups of {clumpsize} enemies",10) # TEMP TODO remove
                

                #spawn <difficulty> groups
                # for _ in range(int(difficulty)):
                if True: # TEmEP remove this so that there is only ever one group spawned (TESTING) TODO remove ???
                    angle = random.random()*2*math.pi # determine where in radius from centre to spawn enemies
                    proximitycentre=(30+int(10*math.sin(angle)),30+int(10*math.cos(angle))) # make centre be somewhere 2 tiles from the centre (anywhere on circle)
                    proximity=2
                    # spawn <clumpsize> enemies
                    for _ in range(clumpsize): 
                        #try to find a position to spawn in 
                        proposedx = -1
                        proposedy = -1
                        tries = 30
                        def isntfree(propx, propy):
                            try:
                                return type(self.world["tiles"][propy][propx]) != GroundTile
                            except KeyError: # cannot find position specified
                                return True
                        while isntfree(proposedx, proposedy) and tries > 0:   
                            proposedx = random.randint(proximitycentre[0]-proximity,proximitycentre[0]+proximity)
                            proposedy = random.randint(proximitycentre[1]-proximity,proximitycentre[1]+proximity)  # try new random position, within the area defined
                            #self.add_to_log(f"trying {proposedx},{proposedy}",10) # TEMP TODO remove
                            tries -= 1
                        
                        if tries >= 1:
                            #spawn in enemy at proposed location
                            spawnenemy(proposedx, proposedy, difficulty)
                            #self.add_to_log(f"spawned one",10) # TEMP TODO remove

                

                time.sleep(1) # make sure that it is not accidentally repeated

    def load_lobby_world(self, message = ""): # world should consist of tiles, non-player entities (here, just simply referred to as entities)
        self.add_to_log("loading lobby...")
        self.dobattleroyale = False # disable gamloop for other world
        self.donormalgameloop = False

        tagcol = "#00ff00"

        self.lobbyworld = {
            "spawn": (21.5,23.5), # world spawn, where players start off
            "tiles": {},
            "name": "Lobby World",
            "entities": [ # list of pre-defined entities
                InteractiveTagHolder("#00ff00Play Battle Royale [PvP]", 27, 22, "PRESS", self.startbattlegame_button),
                InteractiveTagHolder("#00ff00Play Random Game [AI]", 27, 25, "PRESS", self.startgame_button),
                InteractiveTagHolder(f"{tagcol}[Change Skin]", 19, 29, "E000", self.change_skin_0),
                InteractiveTagHolder(f"{tagcol}[Change Skin]", 16, 29, "E001", self.change_skin_1),
                InteractiveTagHolder(f"{tagcol}[Change Skin]", 16, 27, "E002", self.change_skin_2),
                InteractiveTagHolder(f"{tagcol}[Change Skin]", 16, 25, "E003", self.change_skin_3),
                InteractiveTagHolder(f"{tagcol}[Change Skin]", 16, 22, "E004", self.change_skin_4),
                InteractiveTagHolder(f"{tagcol}[Change Skin]", 16, 20, "E005", self.change_skin_5),
                InteractiveTagHolder(f"{tagcol}[Change Skin]", 16, 18, "E006", self.change_skin_6),
                InteractiveTagHolder(f"{tagcol}[Change Skin]", 19, 18, "E007", self.change_skin_7),
                TagHolder("#ff0000<< #ffffffChange Skin", 20, 24, "BLANK"),
                TagHolder("Game Controls #ff0000>>", 24, 24, "BLANK"),
                
                TagHolder("#ff5bffFor Help ~ Press ESC; Reference & Help", 21.5, 21, "BLANK"),

                TagHolder(message, 21.5, 25, "BLANK"),
                
            ]
        }
        #TODO lay this world gen out better when getting multiple worlds figured out and random generation too!
        #generate all tiles
        w = [ # w = world ,, 'X' = Wall, '-' = Ground, ' ' = nothing / None //////// x, y are normal positive to right and top
            "               XXXXXXXXXXXXX                ",
            "   XXXXXXX     X-----------X                ",
            "   X-----X     X-----------X                ",
            "   X-----XXXXXXX----XXXXX--XXXXXX           ",
            "   X--X--------X----X-----------X           ",
            "   X--X--------X----X-----------X           ",
            " XXX--XXXXXXX--XXXXXX--XXXXXXX--X           ",
            " X----X----------------X-----X--X           ",
            " X----X----------------X-----X--X           ",
            " X--XXXXXXXXXXXXXX--X--XXXX--X--XXXXXXXXXXXX",
            " X------------------X--------X-------------X",
            " X------------------X--------X-------------X",
            " XXXXXX--XXXXXXXXXXXX--XXXXXXXXX-----------X",
            " X----X-------X--------------X-------------X",
            " X----X-------X--------------X-------------X",
            " XXX--XXXXXX--X--------------X--X---X---XXXX",
            "   X--X-------X--------------X--X---X------X",
            "   X--X-------X----X----X----X--X---X------X",
            "   X--X--XXXXXX--------------X--X---X------X",
            "   X--X----------------------X--X---XXXX---X",
            "   X--X----------------------X--X---X------X",
            "XXXX--XXXX--XXX--------------X--X---X------X",
            "X-----------X-X----X----X----X--X---X------X",
            "X-----------X-X--------------X--X---X---XXXX",
            "X--XXXXXXX--X-X--------------X--X---X------X",
            "X--------X--X-X--------------X--X---X------X",
            "X--------X--X-X--------------X--X---X------X",
            "XXXX-----X--X-XXXXXXX--XXXXXXX--X---XXXX---X",
            "   X--X--X--X-X--------X-------------------X",
            "   X--X--X--X-X-XXXXX--X-------------------X",
            "   X--XXXX--X-X-----X----------------------X",
            "   X--------X-X-----X----------------------X",
            "   X--------X---XXX-X--X-------------------X",
            "   XXXXXXX--X-------X--X-------------------X",
            "         X---------------------------------X",
            "         X---------------------------------X",
            "         XXXXXXXXXXXXXXX-------------------X",
            "                       X-------------------X",
            "                       X-------------------X",
            "                       X-------------------X",
            "                       X-------------------X",
            "                       X-------------------X",
            "                       X-------------------X",
            "                       XXXXXXXXXXXXXXXXXXXXX",
        ]

        m = {}# map (but that's a reserved word so i'm using 'm' ) // because y=0 is the bottom row, this is actually an upside-down map

        for y in range(len(w)):
            temp = {}
            for x in range(len(w[0])):
                c = w[-(y+1)][x]# char
                if c == "X": # wall
                    temp[x] = WallTile(x, y)
                elif c == "-": # ground
                    temp[x] = GroundTile(x, y)
                else:
                    temp[x] = None
            m[y] = temp

        self.lobbyworld["tiles"] = m

        self.world = self.lobbyworld # set the current world data to be the lobby world data
        self.set_tile_data()
        self.reset_to_new_entities()
        self.pvp_enabled = False

        # WoodenStick(self) # TEMP remove later
        # MetalPole(self) # TEMP remove later
        # Axe(self) # TEMP remove later
        # BroadSword(self) # TEMP remove later
        Pistol(self) # TEMP remove later
        # Revolver(self) # TEMP remove later
        Shotgun(self) # TEMP remove later
        # SniperRifel(self) # TEMP remove later
        GatlingGun(self) # TEMP remove later

        # AmmoHolder(20,20, 10000, self) # TEMP remove later

        #enemies for testing:
        Enemy0(28, 12, self)

        Enemy0(40, 4, self)
        Enemy0(40, 5, self)

        Enemy1(40, 32, self)


        if len(self.players) <= 2:
            self.world["entities"][0].accepts_damage = False # disable battle royale by default, unless there are enough players to play it
            self.world["entities"][0].tag = "#ff0000[Not enough players]"

        #give each player a weapon to interact with the buttons with now that the lobby has loaded
        for name, player in self.players.items():
            if name != "spectator":
                player.giveitem( MetalPole(self, player) )
    
        self.add_to_log("...done")


    def load_battle_royale_world(self): # world should consist of tiles, non-player entities (here, just simply referred to as entities)
        self.add_to_log("loading battle royale world...")

        tagcol = "#00ff00"

        self.battleworld = {
            "spawn": (30,30), # world spawn, where players start off
            "tiles": {},
            "name": "Battle Royale Map 1",
            "entities": [ # list of pre-defined entities
                # InteractiveTagHolder("#00ff00Return to Lobby", 33, 33, "PRESS", self.returntolobbybutton),                
            ]
        }
        #TODO lay this world gen out better when getting multiple worlds figured out and random generation too!
        #generate all tiles
        w = [ # w = world ,, 'X' = Wall, '-' = Ground, ' ' = nothing / None //////// x, y are normal positive to right and top
            "XXXXXXXXXXXXXXXXXXXX                   XXXXXXXXXXXXXXXXXXXX",
            "X--XX-------X------XX                 XX------X-------XX--X",
            "X---X---XXX-X-X-----X                 X-----X-X-XXX---X---X",
            "XX---X---XX-X-X-----XXXXXXXXXXXXXXXXXXX-----X-X-XX---X---XX",
            "XXX---X---X---X-----------------------------X---X---X---XXX",
            "X--X-------XXXXX------XXXXXXXXXXXXXXX------XXXXX-------X--X",
            "X---X-----XX   XX-----X             X-----XX   XX-----X---X",
            "X--------XX     XX----XX           XX----XX     XX--------X",
            "X-X-----XX       X-----X           X-----X       XX-----X-X",
            "X-XX---XX        XX----XX         XX----XX        XX---XX-X",
            "X-XXX-XX          X-----X XXXXXXX X-----X          XX-XXX-X",
            "X----XX           XX----XXX-----XXX----XX           XX----X",
            "XXXX-X             X---------X---------X             X-XXXX",
            "X----X             XX-----XXXXXXX-----XX             X----X",
            "X-XXXXX             X-----X     X-----X             XXXXX-X",
            "X-----XXX           XX----XX   XX----XX           XXX-----X",
            "X-------XXX          X-----X   X-----X          XXX-------X",
            "X---------XXX        XX----XXXXX----XX        XXX---------X",
            "XXX---------XXX       X-------------X       XXX---------XXX",
            "  XXX---------XXX     XX-----------XX     XXX---------XXX  ",
            "    XXX---------XXX    XX---------XX    XXX---------XXX    ",
            "      XXX---------XXX XX-----------XX XXX---------XXX      ",
            "        XXX---------XXX----XXXXX----XXX---------XXX        ",
            "          XXX--------X----X-----X----X--------XXX          ",
            "            XXX-----------------------------XXX            ",
            "              XXX-------X---------X-------XXX              ",
            "                XXX----X-----------X----XXX                ",
            "                  X----X----X-X----X----X                  ",
            "                  X----X-----------X----X                  ",
            "                  X----X----X-X----X----X                  ",
            "                XXX----X-----------X----XXX                ",
            "XXXXXXXXXXXXXXXXX-------X---------X-------XXXXXXXXXXXXXXXXX",
            "X--X---------------------------------------------------X--X",
            "X--X---------X-------X----X-----X----X-------X---------X--X",
            "X------------X--------X----XXXXX----X--------X------------X",
            "XXX-----------XX-------X-----------X-------XX-----------XXX",
            "X-------XXX-------------X---------X-------------XXX-------X",
            "X--XX-------------------------------------------------XX--X",
            "X---X-------------------------------------------------X---X",
            "X---X-----XXXXXXX----------XXXXX----------XXXXXXX-----X---X",
            "X---------------X----------X   X----------X---------------X",
            "X---X-----XXX---X---------XX   XX---------X---XXX-----X---X",
            "X---XXX---X---------------X     X---------------X---XXX---X",
            "X---------X---------------XXXXXXX---------------X---------X",
            "X----------------------------X----------------------------X",
            "X-----------------------XXX-----XXX-----------------------X",
            "X--X--XXXX--------------X XXXXXXX X--------------XXXX--X--X",
            "X-----X  X-------------XX         XX-------------X  X-----X",
            "X-----XXXX-------X-----X           X-----X-------XXXX-----X",
            "X-----------------X---XX           XX---X-----------------X",
            "X--XXXX------------XXXX             XXXX------------XXXX--X",
            "X--X  X---------------XXXXXXXXXXXXXXX---------------X  X--X",
            "X--X  X---------------------------------------------X  X--X",
            "X--XXXX-------------XXXXXXXXXXXXXXXXXXX-------------XXXX--X",
            "X-------------------X                 X-------------------X",
            "X------------------XX                 XX------------------X",
            "XXXXXXXXXXXXXXXXXXXX                   XXXXXXXXXXXXXXXXXXXX",
        ]

        m = {}# map (but that's a reserved word so i'm using 'm' ) // because y=0 is the bottom row, this is actually an upside-down map

        for y in range(len(w)):
            temp = {}
            for x in range(len(w[0])):
                c = w[-(y+1)][x]# char
                if c == "X": # wall
                    temp[x] = WallTile(x, y)
                elif c == "-": # ground
                    temp[x] = GroundTile(x, y)
                else:
                    temp[x] = None
            m[y] = temp

        self.battleworld["tiles"] = m

        self.world = self.battleworld # set the current world data to be the lobby world data
        self.set_tile_data()
        self.reset_to_new_entities()
        self.pvp_enabled = False

        #give each player a weapon to interact with
        # for name, player in self.players.items():
        #     if name != "spectator":
        #         player.giveitem( WoodenStick(self, player) )

        #spawn random items // starting items -> a few weak ones in the centre, and some more stronger ones farther away / stronger ones will spawn later on in the game
        centrepositions = [
            (24,28),
            (29,23),
            (34,28),
            (29,33)
        ]
        toppositions = [
            (2,54),
            (56,54)
        ]
        bottompositions = [
            (56.5, 23.25),
            (1.5, 23.25),
            (56, 14),
            (2, 14),
            (56.5, 1.5),
            (1.5, 1.5),
            (45, 5),
            (13, 5),
            (44, 15),
            (14, 15),
            (30.5, 11.5),
            (27.5, 11.5)
        ]
        def randomitem(bias):
            r = random.randint(1, 8) + bias # bias will make it more likely to be either a better or worse weapon
            if r <= 1:
                return WoodenStick(self)
            elif r == 2:
                return MetalPole(self)
            elif r == 3:
                return Axe(self)
            elif r == 4:
                return BroadSword(self)
            elif r == 5:
                return Pistol(self)
            elif r == 6:
                return Revolver(self)
            elif r == 7:
                return Shotgun(self)
            elif r == 8:
                return SniperRifel(self)
            #else
            return GatlingGun(self)
        #spawn a random item at each position
        for coord in centrepositions:
            # instantiate item
            i = randomitem(bias = -3)
            #set to position
            i.itemholder.position = Vector2D(coord[0], coord[1]) # set to specified coordinates
        for coord in toppositions:
            # instantiate item
            i = randomitem(bias = 4)
            #set to position
            i.itemholder.position = Vector2D(coord[0], coord[1]) # set to specified coordinates
        for coord in bottompositions:
            # instantiate item
            i = randomitem(bias = 0)
            #set to position
            i.itemholder.position = Vector2D(coord[0], coord[1]) # set to specified coordinates

        #spawn random ammo, no more ammo will be spawned (except when player dies)
        self.spawnrandomammo(100) # 100 pieces to be randomly distributed
        
    
        #start the game loop
        self.dobattleroyale = True
        #start management thread
        self.battleroyalethread = threading.Thread(target=self.battleroyalegameloop)
        self.battleroyalethread.start() # run the function in seperate thread 


        self.add_to_log("...done")

    def battleroyalegameloop(self):
        self.add_to_log("30 Second grace period started...", 20)
        start_time = time.time()
        while self.dobattleroyale:
            time.sleep(0.1)
            t = time.time()-start_time
            if 25<t and t<25.5:
                self.add_to_log("PvP enabling in 5",2)
                time.sleep(0.7)
            if 26<t and t<26.5:
                self.add_to_log("PvP enabling in 4",2)
                time.sleep(0.7)
            if 27<t and t<27.5:
                self.add_to_log("PvP enabling in 3",2)
                time.sleep(0.7)
            if 28<t and t<28.5:
                self.add_to_log("PvP enabling in 2",2)
                time.sleep(0.7)
            if 29<t and t<29.5:
                self.add_to_log("PvP enabling in 1",2)
                time.sleep(0.7)
            if 30<t and t<30.5:
                self.add_to_log("FIGHT!",10)
                self.pvp_enabled = True
                time.sleep(0.7)


    def reset_to_new_entities(self):
        """this function resets all non-player entities and adds all deault ones in"""
        for _, player in self.players.items():
            player.drop_everything()

        self.entities = []
        self.droppeditems = [] # reset all dropped items (which are entities) - they should not be carried on to the new world
        self.particles = [] # reset all particles
        self.enemies = [] # reset all enemies

        #get new world spawn
        spawn_point = Vector2D( self.world["spawn"][0], self.world["spawn"][1] )

        self.entities = self.entities + self.world["entities"] # combine with copy of list of entities in default

        for _, player in self.players.items():
            self.entities.append(player)
            player.position = spawn_point.copy()
            player.velocity = Vector2D() # reset to 0
            player.health = player.maxhealth
            player.ammo = 0
            player.XP = 0
            # have to drop before erasing floor entities so that the item is fully deleted
            if player.name != "spectator":    
                player.tag = f"{player.name}#00ff00 [{player.health}]" # reset to remove " [DEAD]" ending
                player.accepts_damage = True # make sure no longer dead, so will be able to be tracked by AIs and take damage


    def set_tile_data(self): # return a string of all tiles
        tilelist = []
        for y, row in self.world["tiles"].items():
            for x, tile in row.items():
                if tile != None:
                    tilelist.append(tile)
        self.tiledata = "|".join([str(tile) for tile in tilelist]) # take advantage of __str__ in Tile to 
        self.tiles = tilelist # saved for later with range weapon raycasting to detect walls


    def add_to_log(self, msg, time=6):
        print(msg)
        self.logs.append(LogEntry(msg, time))
        self.compile_logs()

    def log_thread(self):
        while True:
            self.compile_logs()
            time.sleep(0.3)
            #this does not need to update that often, so 3-4 times in any given second seems more than enough.

    def compile_logs(self):
        #check to see if any logs have expired
        for log in self.logs:
            if log.removeby < time.time():
                self.logs.remove(log)
        #comile string
        self.logs_compiled_txt = "\n".join([log.txt for log in self.logs[::-1]])

    def change_skin_0(self, activator, interactivetagholder):
        interactivetagholder.health = 1 # reset the button to be able to be pressed again immediately
        interactivetagholder.accepts_damage = True
        activator.texture = "E000"
    def change_skin_1(self, activator, interactivetagholder):
        interactivetagholder.health = 1 # reset the button to be able to be pressed again immediately
        interactivetagholder.accepts_damage = True
        activator.texture = "E001"
    def change_skin_2(self, activator, interactivetagholder):
        interactivetagholder.health = 1 # reset the button to be able to be pressed again immediately
        interactivetagholder.accepts_damage = True
        activator.texture = "E002"
    def change_skin_3(self, activator, interactivetagholder):
        interactivetagholder.health = 1 # reset the button to be able to be pressed again immediately
        interactivetagholder.accepts_damage = True
        activator.texture = "E003"
    def change_skin_4(self, activator, interactivetagholder):
        interactivetagholder.health = 1 # reset the button to be able to be pressed again immediately
        interactivetagholder.accepts_damage = True
        activator.texture = "E004"
    def change_skin_5(self, activator, interactivetagholder):
        interactivetagholder.health = 1 # reset the button to be able to be pressed again immediately
        interactivetagholder.accepts_damage = True
        activator.texture = "E005"
    def change_skin_6(self, activator, interactivetagholder):
        interactivetagholder.health = 1 # reset the button to be able to be pressed again immediately
        interactivetagholder.accepts_damage = True
        activator.texture = "E006"
    def change_skin_7(self, activator, interactivetagholder):
        interactivetagholder.health = 1 # reset the button to be able to be pressed again immediately
        interactivetagholder.accepts_damage = True
        activator.texture = "E007"

    def startgame_button(self, activator, interavtivetagholder):
        t = threading.Thread(target = self.startgame_function, args=(interavtivetagholder,))
        t.start() # run the function of the button in seperate thread, this means that it will become deactivated once it is pressed

    def startgame_function(self, interavtivetagholder): # this is a sperate function so that it can be threaded to generate the world in the background
        self.add_to_log("Generating random world... [PREPARE TO TELEPORT!]")
        
        #de-activate ALL load world buttons! TODO deactivate all as they are added
        interavtivetagholder.tag = "#ff0000Start Game" # change colour to red to signal that it cannot be pressed

        self.generate_random_world()

        self.add_to_log("...Done. Loading game world...")

        self.load_random_world()

        # interactivetagholder.accepts_damage = True
        self.add_to_log("...done")

    def startbattlegame_button(self, activator, interavtivetagholder):
        self.load_battle_royale_world()

    def returntolobbybutton(self, activator, interavtivetagholder):
        print("returning to lobby")
        self.load_lobby_world()
        #TODO make this more complete


if __name__ == "__main__": # run the server standalone
    s = Server("TestServer", public=True, port=80)  #   Development_TestServer
