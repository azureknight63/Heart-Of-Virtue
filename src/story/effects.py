"""
Effects are small, one-time-only events typically fired during combat or in response to some player action
"""
from typing import List, Optional

from neotermcolor import colored, cprint
import random
import time

from npc import NPC
import functions
import states
from events import Event
import animations


def memory_border(style="top"):
    """Print decorative borders for memory flashes."""
    border = "═" * 79
    if style == "top":
        # Play the memory flash animation
        animations.animate_to_main_screen("memory_flash")
        print()  # Blank line after animation
        cprint(border, "magenta")
        cprint("✧ A MEMORY STIRS ✧".center(79), "magenta", attrs=["bold"])
        cprint(border, "magenta")
        print()  # Blank line for readability
    elif style == "bottom":
        print()  # Blank line before bottom border
        cprint(border, "magenta")
        cprint("✧ THE MEMORY FADES ✧".center(79), "magenta", attrs=["bold"])
        cprint(border, "magenta")
    else:
        cprint(border, "magenta")


class MemoryFlash(Event):
    """
    A memory flash event that displays a fragment of Jean's past.
    These are powerful story moments that reveal Jean's background and motivations.
    
    Memory fragments should be:
    - Brief (5-10 lines of text)
    - Sensory and evocative
    - Mysterious but revealing
    - Emotionally resonant
    
    Args:
        player: The player object
        tile: The tile where this event triggers
        memory_lines: List of tuples (text, pause_duration) for each line of the memory
        aftermath_text: Optional text shown after the memory fades
        repeat: Whether this memory can trigger again (usually False)
        name: Event name for tracking
    """
    def __init__(self, player, tile, memory_lines, aftermath_text=None, repeat=False, name='MemoryFlash'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=None)
        self.memory_lines = memory_lines
        self.aftermath_text = aftermath_text
    
    def check_conditions(self):
        # Memory flashes trigger automatically when conditions are met
        # Override this in subclasses for specific trigger conditions
        self.pass_conditions_to_process()
    
    def process(self, user_input=None):
        """Display the memory flash sequence."""
        if user_input is None:
            # First pass: display the memory and aftermath, then pause for input
            # Pause before the memory begins
            time.sleep(1)
            print()
            cprint("For a moment, there is only silence...", "white")
            time.sleep(0.5) # Reduced for API responsiveness
            print()
            
            # Top border with animation
            memory_border("top")
            
            # Display each memory line with individual timing
            for line, pause in self.memory_lines:
                cprint(line, "magenta")
                # Removed long sleeps to prevent API timeouts, frontend handles pacing
            
            # Bottom border
            memory_border("bottom")
            print()
            
            # Aftermath - Jean's reaction to the memory
            if self.aftermath_text:
                for line in self.aftermath_text:
                    cprint(line, "cyan")
            
            # Signal requirement for input
            self.needs_input = True
            self.input_type = "choice"
            self.input_prompt = "The memory fades..."
            self.input_options = [{"value": "continue", "label": "Continue"}]
            return

        # Second pass: user has clicked continue
        print()
        cprint("═" * 79, "cyan")
        print()
        self.needs_input = False
        self.completed = True
        
        # Remove from tile/combat events if not repeating
        if not self.repeat:
            if hasattr(self, "tile") and self.tile and self in getattr(self.tile, "events_here", []):
                self.tile.events_here.remove(self)
            elif hasattr(self, "player") and self.player and self in getattr(self.player, "combat_events", []):
                self.player.combat_events.remove(self)


class Effect(Event):
    def __init__(self, name, player):
        super().__init__(name=name, player=player, tile=player.tile, repeat=False, params=None)

    def pass_conditions_to_process(self):
        self.process()


class MoveEffect(Effect):  # Generic class for move-based effects.
    def __init__(self, player, name, move, target, trigger, announcement):
        super().__init__(name=name, player=player)
        self.move = move
        self.target = target  # must be updated at the time the effect is processed!
        self.trigger = trigger  # on what stage may the effect occur?
        self.announcement=announcement


class FlareArrowImpact(MoveEffect):
    def __init__(self, player, move):
        super().__init__(player=player, move=move, target=move.target, name="FlareArrowImpact", trigger="execute",
                         announcement="{}'s arrow bursts into flames on impact!".format(move.user.name))

    def process(self):
        self.target = self.move.target
        self.announcement = "{}'s arrow bursts into flames on impact!".format(self.move.user.name)
        status = states.Enflamed(self.target)
        functions.inflict(status, self.target, chance=0.75)


class GoldFromHeaven(Event):  # Gives the player a certain amount of gold... for testing? Or just fun.
    def __init__(self, player, tile, params=None, repeat=False, name='Gold From Heaven'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        print("Oddly enough, a pouch of gold materializes in front of you.")
        self.tile.spawn_item('Gold', amt=77)


class Block(Event):  # blocks exit in tile, blocks all if none are declared
    def __init__(self, player, tile, params=None, repeat=False, name='Block'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)
        self.directions = []
        if not params:
            self.directions = ['north', 'south', 'east', 'west', 'northeast', 'northwest', 'southeast', 'southwest']
        else:
            self.directions = params

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        for direction in self.directions:
            if direction == 'east' and 'east' not in self.tile.block_exit:
                self.tile.block_exit.append('east')
            if direction == 'west' and 'west' not in self.tile.block_exit:
                self.tile.block_exit.append('west')
            if direction == 'north' and 'north' not in self.tile.block_exit:
                self.tile.block_exit.append('north')
            if direction == 'south' and 'south' not in self.tile.block_exit:
                self.tile.block_exit.append('south')
            if direction == 'northeast' and 'northeast' not in self.tile.block_exit:
                self.tile.block_exit.append('northeast')
            if direction == 'northwest' and 'northwest' not in self.tile.block_exit:
                self.tile.block_exit.append('northwest')
            if direction == 'southeast' and 'southeast' not in self.tile.block_exit:
                self.tile.block_exit.append('southeast')
            if direction == 'southwest' and 'southwest' not in self.tile.block_exit:
                self.tile.block_exit.append('southwest')


class MakeKey(Event):  # Spawns a key for the chest with the given alias (as a param).
    def __init__(self, player, tile, params=None, repeat=False, name='MakeKey'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        alias = "unknown"
        name = "Key"
        desc = "A small, metal key."
        for thing in self.params:
            if '^' in thing:
                alias = thing[1:]
                continue
            if "name=" in thing:
                name = thing[5:]
                continue
            if "desc=" in thing:
                desc = thing[5:].replace('~', '.')
                continue
        lock = None
        for chest in self.player.universe.locked_chests:
            if chest[1] == alias:
                lock = chest[0]
                break
        key = self.tile.spawn_item('Key')
        key.lock = lock
        key.name = name
        key.description = desc
        key.announce = "There's a {} here.".format(key.name.lower())


class Teleport(Event):
    """
    Event that teleports the player to a specified location on a target map.

    Args:
        player: The player to teleport.
        tile: The current tile of the player.
        target_map_name (str): Name of the destination map.
        target_coordinates (tuple): Coordinates (x, y) on the destination map.
        repeat (bool): Whether the event can repeat.
        name (str): Name of the event.
    """
    def __init__(self, player, tile, target_map_name: str, target_coordinates: tuple=(0,0), repeat=False, name='Teleport'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=None)
        self.target_map_name = target_map_name
        self.target_coordinates = target_coordinates

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        self.player.teleport(self.target_map_name, self.target_coordinates)

class Shrine(Event):  # Generic class for Shrine-based events
    def __init__(self, player, tile, params=None, repeat=False, name='Shrine'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        pass


class StMichael(Shrine):
    def __init__(self, player, tile, params=None, repeat=False, name='Shrine of St Michael the Archangel'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)
        # Declare input requirements for API mode
        self.input_type = "choice"
        self.input_prompt = "Selection:"
        # Generate weapon choices at init time
        self._generate_weapon_choices()

    def _generate_weapon_choices(self):
        """Generate 3 random weapon choices for the event."""
        all_choices = [
            ("A crafty dagger.", "Dagger"),
            ("A trusty sword.", "Shortsword"),
            ("An imposing battleaxe.", "Battleaxe"),
            ("A useful mace.", "Mace"),
            ("A sharp pick.", "Pickaxe"),
            ("An intimidating scythe.", "Scythe"),
            ("A long spear.", "Spear"),
            ("A deadly halberd.", "Halberd"),
            ("A powerful warhammer.", "Hammer"),
            ("A reliable bow.", "Shortbow"),
            ("A convenient crossbow.", "Crossbow"),
            ("A sturdy pole.", "Pole"),
        ]
        self.available_choices = []
        for i in range(0, 3):
            choice = all_choices[random.randint(0, len(all_choices) - 1)]
            while choice in self.available_choices:
                choice = all_choices[random.randint(0, len(all_choices) - 1)]
            self.available_choices.append(choice)
        
        # Create input_options for API serialization
        self.input_options = [
            {"value": str(i), "label": choice[0]} 
            for i, choice in enumerate(self.available_choices)
        ]

    def get_input_prompt(self):
        """Return the weapon selection prompt."""
        return "TELL ME THE INSTRUMENT OF JUSTICE THOU DESIREST."

    def get_input_options(self):
        """Return the available weapon choices."""
        return self.input_options

    def process(self, user_input=None):
        print("This, particularly, is a shrine to Saint Michael the Archangel.")
        print("There is a small statue depicting St Michael spearing a vicious dragon.")
        print("""An inscription on the shrine reads,

        Sáncte Míchael Archángele, defénde nos in proélio, cóntra nequítiam et insídias diáboli ésto præsídium.
        Ímperet ílli Déus, súpplices deprecámur: tuque, prínceps milítiæ cæléstis, Sátanam aliósque spíritus malígnos,
        qui ad perditiónem animárum pervagántur in múndo, divína virtúte, in inférnum detrúde. Ámen.

        """)
        print("Suddenly, Jean has the feeling of intense heat all around him. "
              "He hears a voice echoing inside his head.")
        time.sleep(2)
        cprint("""CHILD, THY FAITH PRESERVES THEE. TELL ME THE INSTRUMENT OF JUSTICE THOU DESIREST.""", "red")
        
        for i, choice in enumerate(self.available_choices):
            print("{}: {}".format(i, choice[0]))

        if user_input is None:
            self.needs_input = True
            return

        selection = user_input
        if selection is None:
            # Fallback for terminal mode, but skip await_input if in API mode (user_input provided)
            # Actually, just remove the blocking await_input as well
            # functions.await_input()
            try:
                selection = input(colored("Selection: ", "cyan"))
            except (EOFError, OSError, ValueError):
                # Default to first option if no input available
                selection = "0"
        
        if functions.is_input_integer(selection):
            selection = int(selection)
        else:
            selection = 0  # Default to first option if invalid
        
        # Ensure selection is within valid range
        if selection < 0 or selection >= len(self.available_choices):
            selection = 0
        
        drop = self.tile.spawn_item(self.available_choices[selection][1], amt=1, hidden=False, hfactor=0)
        functions.add_random_enchantments(drop, 1)
        cprint("There's a brief flash of light (or was it imagined?) \nSuddenly, at the foot of the shrine, "
               "there sits a {}.".format(drop.name), "cyan")

        # Mark as completed so it doesn't prompt again
        self.needs_input = False
        self.completed = True
        
        # Remove from tile if not repeating
        if not self.repeat:
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)

class NPCSpawnerEvent(Event):
    """Spawns a number of NPCs of a given class onto a specified tile.

    Usage / JSON params patterns supported (params field on event):
        ["Slime", 3]                       -> spawn 3 Slime on event tile
        [Slime, 5]                          -> spawn 5 Slime (class object deserialized) on event tile
        ["Slime", 2, (x, y)]               -> spawn 2 Slime on the tile at coordinates (x,y) within same map
        [Slime, 4, (x, y)]                  -> class object variant with coordinate override

    The constructor ALSO accepts npc_cls / count directly if map editor supplies them as properties instead of params.
    Priority order for resolving values:
        explicit npc_cls argument > params[0]
        explicit count argument  > params[1]
        optional spawn coords    = params[2]

    Trigger conditions:
    - Fires once the first time the player is in the same map (even if not on the spawn tile yet), OR immediately if
      the player starts / moves onto the spawn tile before global scan catches it.

    Removal:
    - Event removes itself after spawning unless repeat=True (repeat use not generally recommended).
    """
    def __init__(self, player=None, tile=None, params=None, repeat: bool = False,
                 npc_cls: type[NPC]=None, count: int | None = None, name: str = "NPCSpawnerEvent"):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)
        self.spawn_tile = tile  # default
        self.npc_cls = npc_cls
        self.count = count
        if params:
            try:
                if self.npc_cls is None:
                    self.npc_cls = params[0]
                if self.count is None and len(params) > 1:
                    self.count = params[1]
                if len(params) > 2 and isinstance(params[2], (list, tuple)) and len(params[2]) == 2:
                    # attempt coordinate override within same map
                    coord = tuple(params[2])
                    if tile and tile.map and coord in tile.map:
                        self.spawn_tile = tile.map.get(coord)
            except Exception:
                pass
        try:
            self.count = max(1, int(self.count)) if self.count is not None else 1
        except Exception:
            self.count = 1
        self.spawned_npcs: List = []

    def _resolve_npc_class_name(self) -> Optional[str]:
        if self.npc_cls is None:
            return None
        if isinstance(self.npc_cls, str):
            return self.npc_cls
        try:
            from npc import NPC  # local import avoids circular on module load
            if isinstance(self.npc_cls, type) and issubclass(self.npc_cls, NPC):
                return self.npc_cls.__name__
        except Exception:
            return None
        return None

    def _do_spawn(self):
        if not self.spawn_tile:
            if self.tile:
                self.spawn_tile = self.tile
            else:
                return
        cls_name = self._resolve_npc_class_name()
        if not cls_name:
            return
        for _ in range(self.count):
            try:
                npc_obj = self.spawn_tile.spawn_npc(cls_name)
                self.spawned_npcs.append(npc_obj)
            except Exception:
                continue

    def process(self):
        if self.has_run and not self.repeat:
            return
        self._do_spawn()
        self.has_run = True

    def evaluate_for_map_entry(self, player):
        if self.has_run and not self.repeat:
            return
        # trigger if player map matches spawn tile's map
        try:
            if self.spawn_tile and self.spawn_tile.map is player.map:
                self.pass_conditions_to_process()
        except Exception:
            return

class WhisperingStatue(Event):
    def __init__(self, player, tile, params=None, repeat=False, name='The Whispering Statue'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=params)
        # Declare input requirements for API mode
        self.input_type = "choice"
        self.input_prompt = "I have a mouth but never speak. I have a bed but never sleep. I run but have no legs. What am I?"
        self.input_options = [
            {"value": "1", "label": "A River"},
            {"value": "2", "label": "The Wind"},
            {"value": "3", "label": "A Shadow"}
        ]
        self.description = f"{player.name} stands before an ancient, moss-covered statue of a hooded figure. Its stone eyes seem to track {player.name}'s movements. Suddenly, a raspy voice emanates from the stone..."

    def check_conditions(self):
        # Always trigger if the player interacts with it
        self.pass_conditions_to_process()

    def get_input_prompt(self):
        """Return the riddle question for display."""
        return '"I have a mouth but never speak. I have a bed but never sleep. I run but have no legs. What am I?"'

    def get_input_options(self):
        """Return the available choices for this riddle."""
        return self.input_options

    def process(self, user_input=None):
        if user_input is None:
            # First pass: show description and prompt, then request input
            cprint(self.description, "cyan")
            cprint(self.input_prompt, "yellow")
            self.needs_input = True
            return

        # Try to get input, but handle cases where input() is mocked or unavailable
        choice = user_input  # Use provided input if available (from API)
        if choice is None:
            # If no input provided, we might be in a CLI session
            # Print the riddle first if not already shown via description
            cprint(self.description, "cyan")
            cprint(self.input_prompt, "yellow")
            try:
                choice = input(colored("\nYour answer (1-3): ", "white"))
            except (EOFError, OSError, ValueError):
                choice = "1"
        
        if not choice:
            choice = "1"
        
        time.sleep(1)
        
        if choice == "1":
            cprint("\nThe statue's eyes glow with a soft blue light.", "cyan")
            time.sleep(1)
            cprint('"Wisdom flows like water," the voice rumbles.', "yellow")
            cprint("A hidden compartment opens at the statue's base!", "green")
            
            # Reward
            cprint(f"{self.player.name} found a pouch of Gold!", "green", attrs=['bold'])
            self.tile.spawn_item('Gold', amt=500)
            
        else:
            cprint("\nThe statue's eyes flare with an angry red light.", "red")
            time.sleep(1)
            cprint('"Foolishness invites destruction," the voice hisses.', "red", attrs=['bold'])
            cprint(f"The ground beneath {self.player.name} trembles!", "red")
            
            # Punishment - Spawn a low level enemy
            cprint("A Slime oozes out from cracks in the earth!", "red")
            slime = self.tile.spawn_npc('Slime')
            if slime:
                # Force combat initiation by setting awareness high for this scripted ambush
                # This ensures check_for_combat() in GameService will always detect it regardless of player finesse
                slime.awareness = 999
            
        # Mark as completed so it doesn't prompt again
        self.needs_input = False
        self.completed = True
        
        # Remove from tile if not repeating
        if not self.repeat:
            if self in self.tile.events_here:
                self.tile.events_here.remove(self)
            
        # await_input is removed because it blocks the API request. The frontend handles dialog continuation.
