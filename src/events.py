"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""

from neotermcolor import colored
from functions import print_slow, await_input
from typing import Optional


def dialogue(speaker, text, speaker_color="cyan", text_color="white"):
    """
    Displays a dialogue line with colored speaker and text, then waits for user input.
    This handles line breaks on its own, no need for newlines in the text.

    Args:
        speaker (str): Name of the speaker.
        text (str): Dialogue text to display.
        speaker_color (str, optional): Color for the speaker's name. Defaults to "cyan".
        text_color (str, optional): Color for the dialogue text. Defaults to "white".
    """
    print_slow(
        (colored(speaker + ": ", speaker_color) + colored(text, text_color)),
        "fast",
    )
    await_input()


class Event:  # master class for all events
    """
    Events are added to tiles much like NPCs and items. These are evaluated each game loop to see if the conditions
    of the event are met. If so, execute the 'process' function, else pass.
    Events can also be added to the combat loop.
    Set repeat to True to automatically repeat for each game loop
    params is a list of additional parameters, None if omitted.

    """

    def __init__(
        self,
        name,
        player=None,
        tile=None,
        repeat=False,
        params=None,
        combat_effect: bool = False,
        delay_duration: int = 3000,
        delay_mode: Optional[str] = "combat",
    ):
        self.name = name
        self.player = player
        self.tile = tile
        self.repeat = repeat
        self.thread = None
        self.has_run = False
        self.params = params
        self.referenceobj = (
            None  # objects being referenced for special conditions can be put here
        )
        self.combat_effect = combat_effect
        self.delay_duration = delay_duration
        self.delay_mode = (
            delay_mode  # "exploration", "combat", or "both" (None means no delay)
        )
        self.completed = False
        self.api_event_id = None
        self.needs_input = False

    def pass_conditions_to_process(self):
        self.process()
        # If the event requires input, we don't want to remove it yet;
        # it will be removed once it's completed or on subsequent check
        if not self.repeat and not getattr(self, "needs_input", False):
            if self in self.tile.events_here:
                self.tile.events_here.remove(
                    self
                )  # if this is a one-time event, kill it after it executes
            elif self in self.player.combat_events:
                self.player.combat_events.remove(self)

    def check_conditions(self):
        self.pass_conditions_to_process()

    def process(self):
        """
        to be overwritten by an event subclass
        """


class CombatEvent(Event):
    """
    Event that initiates parameterized combat using a CombatEventConfig.
    """

    def __init__(self, name, player=None, tile=None, repeat=False, config=None):
        """
        Args:
            config (CombatEventConfig): Configuration for the combat encounter
        """
        super().__init__(name, player, tile, repeat, params=[config])
        self.config = config

        # Declare input requirements for API mode
        self.needs_input = True
        self.input_type = "choice"
        self.input_prompt = "Prepare for combat!"
        self.input_options = [{"value": "combat_start", "label": "FIGHT FOR YOUR LIFE"}]

        # Use narrative text from config if available, otherwise use a default
        if hasattr(self.config, "narrative_text") and self.config.narrative_text:
            self.description = self.config.narrative_text
        else:
            self.description = (
                f"As you move forward, the air grows cold... {name} begins!"
            )

    def process(self, user_input=None):
        """
        Initiates combat with the configured parameters.
        """
        # If API input is "combat_start", we prepare the NPCs for GameService to pick up.
        if user_input == "combat_start":
            # Spawn the configured NPCs onto the tile
            if self.config and hasattr(self.config, "enemy_list"):
                for enemy_name, count in self.config.enemy_list:
                    for _ in range(count):
                        npc = self.tile.spawn_npc(enemy_name)
                        if npc:
                            # Force aggro and in_combat so they are picked up immediately
                            npc.aggro = True

            # Return a signal that combat is ready to be initialized
            if not self.repeat:
                if self in self.tile.events_here:
                    self.tile.events_here.remove(self)

            self.needs_input = False
            self.completed = True

            return {"combat_ready": True}

        # Terminal fallback
        from src.combat import combat

        # We assume combat() has been updated to accept an optional config
        combat(self.player, event_config=self.config)


class LootEvent(Event):
    """
    Event that handles looting a container via a choice dialog.
    """

    def __init__(self, name, player=None, tile=None, container=None):
        super().__init__(name, player, tile, repeat=False, params=[container])
        self.container = container
        self.needs_input = True
        self.input_type = "choice"
        self.input_prompt = "Select an item to take:"
        self.description = (
            f"Jean rifles through the contents of the {container.nickname}."
        )
        self._rebuild_options()

    def _rebuild_options(self):
        self.input_options = []
        if not hasattr(self.container, "inventory") or not self.container.inventory:
            self.input_options.append({"value": "exit", "label": "Close (Empty)"})
            return

        for i, item in enumerate(self.container.inventory):
            label = f"Take {item.name}"
            if hasattr(item, "count") and item.count > 1:
                label += f" ({item.count})"
            self.input_options.append({"value": str(i), "label": label})

        self.input_options.append({"value": "all", "label": "Take All"})
        self.input_options.append({"value": "exit", "label": "Exit"})

    def process(self, user_input=None):
        if not user_input or user_input == "exit":
            self.completed = True
            self.needs_input = False
            return {"success": True, "message": "Interaction ended."}

        from neotermcolor import cprint

        try:
            from interface import transfer_item
        except ImportError:
            from src.interface import transfer_item

        if user_input == "all":
            snapshot = list(self.container.inventory)
            taken_names = []
            for item in snapshot:
                qty = getattr(item, "count", 1)
                transfer_item(self.container, self.player, item, qty)
                taken_names.append(item.name)

            if taken_names:
                cprint(f"Jean takes everything: {', '.join(taken_names)}", "green")
            else:
                cprint("The container is empty.", "yellow")

            # Since everything is taken, we can end the event
            if hasattr(self.container, "refresh_description"):
                self.container.refresh_description()

            self.completed = True
            self.needs_input = False
            return {"success": True}

        if user_input.isdigit():
            idx = int(user_input)
            if 0 <= idx < len(self.container.inventory):
                item = self.container.inventory[idx]
                qty = getattr(item, "count", 1)
                transfer_item(self.container, self.player, item, qty)
                cprint(f"Jean takes the {item.name}.", "green")

                if hasattr(self.container, "refresh_description"):
                    self.container.refresh_description()

                # Rebuild options for next choice
                self._rebuild_options()
            else:
                cprint("Invalid item choice.", "red")

        # Keep pending if we didn't exit or take all
        return {"success": True}
