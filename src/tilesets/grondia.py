from src.tiles import *


class GrondiaPassage(MapTile):
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


class GrondiaGateWest(MapTile):
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


class GrondiaAntechamber(MapTile):
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


class GrondiaArcology(MapTile):
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


class GrondiaResidences(MapTile):
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


class GrondiaConclave(MapTile):
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The Conclave is the spiritual heart of Grondia, where the Grondites gather to worship and seek guidance from
        their ancestors. The walls are adorned with intricate carvings and murals depicting the history of the
        Grondites, their struggles, and their triumphs. The air is thick with the scent of incense and the sound of
        chanting fills the air. The Grondites here are deeply reverent, their eyes closed in prayer or
        meditation. The atmosphere is one of peace and reflection, a stark contrast to the bustling
        activity of the city outside.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaCitadel(MapTile):
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        In sharp contrast to the rock holes that comprise the various residences and domestic shops throughout 
        the rest of Grondia, the Citadel is an impressive construction rising up from the center of the city.
        Its walls are smooth and polished, with intricate carvings depicting the history of the Grondites.
        The Citadel serves as the seat of power for the Grondite leadership, housing their council chambers, 
        administrative offices, and a grand hall for public gatherings. The atmosphere here is one of authority and 
        reverence, with Grondites moving about with a sense of purpose and respect for their leaders.
        The air is filled with the faint scent of incense, and the walls are adorned with banners
        representing the various clans and factions within Grondia. The Citadel stands as a testament
        to the strength and unity of the Grondite people, a symbol of their resilience and
        determination to thrive in the harsh underground environment.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaEcumerium(MapTile):
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The Ecumerium is a dedicated space for the Grondites to interact with the outside world. It is a large, 
        open area with a high ceiling, filled with stalls and booths where merchants from various regions set up shop.
        The air is filled with the sounds of haggling and the smells of exotic goods.
        Grondites and visitors alike browse the wares, which range from rare minerals to intricate
        jewelry and weapons. The walls are adorned with murals depicting the history of Grondia and
        its interactions with other cultures. The atmosphere is lively and bustling, with a sense of camaraderie 
        among the traders and customers.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaFabricarium(MapTile):
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The Fabricarium is the industrial heart of Grondia, where raw materials are processed and transformed into
        finished goods. The air is thick with the smell of molten metal and the sound of machinery
        reverberates through the cavernous space. Grondites work tirelessly, their hands skilled and efficient, 
        crafting everything from weapons to intricate jewelry. The walls are lined with shelves filled with tools and 
        materials, and the floor is scattered with scraps of metal and stone. The atmosphere is one of industriousness 
        and purpose, with Grondites moving about with a sense of pride in their work.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class GrondiaGateEast(MapTile):
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


class GrondiaGateSouth(MapTile):
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


class GrondelithMineralPoolsEntrance(MapTile):  # leads southwest to the Grondelith Mineral Pools
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        The chamber opens up into a breathtaking expanse filled with massive, shimmering crystal formations that 
        jut from the ground and walls. Pools of mineral-rich water reflect the vibrant colors of the crystals, 
        casting prismatic patterns across the cavern. Grondites gather here to feast on the crystals, their 
        primary source of sustenance. The air is thick with the sound of gentle chipping and the low hum of 
        conversation, creating a tranquil, communal atmosphere unique to this subterranean dining hall.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass
