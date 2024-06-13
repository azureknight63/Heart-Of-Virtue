from src.tiles import *


class GrondiaPassage(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        A great passage opens up here. Scuffs on the rock and dirt floor suggest this is a well-traveled path. 
        The air is tinged with moisture and a variety of smells, some familiar, and some entirely alien. Light has 
        made its way into this part of the underground, emitted by a distant source. A muted cacophony echoes 
        percussively against the walls, creating a disorienting effect.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaGateWest(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        A large, smooth wall stands to the east. To the west, the passage winds back into the cold darkness of the 
        cavern. The distinct sounds of a bustling city can be heard somewhere behind the wall, reverberating dully 
        against the rock. There is no obvious handle or chain with which to open the door faintly outlined against 
        the sheer blockade. The size of the door and the lack of a handle is evidence that this is not an entrance 
        designed for humans.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaAntechamber(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        This room was entirely unlike the cavern preceding it. The walls and ceiling were angular and distinct; 
        More like a man's house than a naturally occuring hole in the earth. Pink crystals hang from the ceiling like 
        exotic chandeliers, emitting their bright glow in ebbing pulsations. The pattern of the oscillating glow
        seemed random to Jean at first, but steadily began to form an intricate dance, hypnotic and calming 
        in its susserations.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaArcology(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The Grondia Arcology is the western district of the city where most Grondites find their homes. The actual 
        living chambers comprise a hive-like structure digging deeply into the greater concourse and branching streets. 
        Most shops and businesses are found in the walls or under the strikingly clean floor like the residences, 
        with the few restaurants and stalls that cater to foreigners making up most of the obstacles visible at 
        first glance. There is a steady stream of traffic going one direction or another. The area is brightly lit in a 
        vibrant shade of red by numerous large crystalline protrusions thrusting downward from the ceiling.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaResidences(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        This area is comprised of densely packed residences and is likely where the lower classes of Grondites make 
        their homes. There is considerably less traffic here, with the echoes of the surrounding areas creating a 
        muted, incoherent din. It is, nonetheless, a relatively good space to stop and rest from the cacophony 
        of the city.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaConclave(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        Description TBD.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaCitadel(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        In sharp contrast to the rock holes that comprise the various residences and domestic shops throughout 
        the rest of Grondia, the Citadel is an impressive construction rising up from the center of the city.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaEcumerium(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        Description TBD.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaFabricarium(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        Description TBD.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaGateEast(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        A large, smooth wall stands to the west. To the east, a path rounds a corner out of sight. 
        The distinct sounds of a bustling city can be heard somewhere behind the wall, reverberating dully 
        against the rock. A large imposing door is set in the western wall, swung open to allow visitors
        passage.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaGateSouth(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        A large, smooth wall stands to the north. To the south, a cavern opens up to a large chamber dotted with
        small pools of water that glow a faint blue in the dim light. The distinct sounds of a bustling city can be 
        heard somewhere behind the wall, reverberating dully against the rock. There is no obvious handle or chain 
        with which to open the door faintly outlined against the sheer blockade. The size of the door and the 
        lack of a handle is evidence that this is not an entrance designed for humans.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass
