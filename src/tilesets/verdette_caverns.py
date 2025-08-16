from src.tiles import *


class VerdetteRoom(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        This cavern chamber is dimly lit with a strange pink glow. Scattered on the walls are torches with illuminated 
        crystals instead of flames. Strange, ethereal sounds echo off of the rock surfaces with no decipherable pattern. 
        The air is cold and slightly humid. The stone walls are damp to the touch.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class VerdetteRoom2(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The cave narrows a bit here and the ceiling hangs low. A steady breeze sings through crystalline fingers that thrust out at scattered points 
        along the walls and floor. Ethereal noises echo hauntingly from distant chambers. The tight space makes for an uncomfortable passage, but 
        nonetheless yields further exploration for those willing to squeeze through.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class VerdetteRoom3(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The ceiling rises quickly here as the cave opens up into a large chamber. The far wall is lost in a haze of darkness only slightly abated by 
        the soft neon glow of scattered crystal formations. There is an oppressive silence, as if the world is holding it's breath in trepidation. 
        Any traveler, too, might become wary when faced with such silence and unspeakable distances. An odd sense of vulnerability permeates the dank 
        stillness of the place.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class VerdetteRoom4(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The area brightens significantly thanks to a skylight cut into the ceiling. The opening, as brutal in shape as the painful brightness 
        spilling through it, is much too small for most creatures, but nonetheless is a welcome change from the darkness. 
        Thick tapestries of green moss cling to the walls, grateful too for the life-giving illumination. The juxtaposition of the light against 
        the darkness of the rest of the cavern carries with it the dangers of a false sense of security in this inhospitable tomb.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class VerdetteRoom5(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The floor slopes downward slightly, disappearing under a barely-discernible pool of water. The pool is ankle deep, broken only where a 
        few stone spires have dared to pierce upward from the floor into the damp air of the chamber like the groping fingers of a desperate victim. 
        Indeed, footfalls are best placed carefully here, or some of the more hidden fingers may find painful purchase.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class VerdetteSpring(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The unmistakable sound of water trickling over rock can be heard echoing throughout this small chamber. The air is filled
        with a fresh, life-giving smell that immediately improves Jean's mood. This would be an excellent place to stop for a short
        rest before continuing on.
        """)
        self.symbol = '~'

    def modify_player(self, the_player):
        #Room has no action on player
        pass
