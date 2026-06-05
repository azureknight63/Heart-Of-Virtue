import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure both project root and src directory are on path for direct module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from story.effects import (
    memory_border, MemoryFlash, Effect, MoveEffect, FlareArrowImpact,
    GoldFromHeaven, Block, MakeKey, Teleport, Shrine, StMichael,
    NPCSpawnerEvent, PulsingGlandEvent
)
from items import Item, Shortsword
import states

# Fakes
class FakeTile:
    def __init__(self):
        self.block_exit = []
        self.events_here = []
        self.items_here = []
        self.map = {}
        self.spawned_items = []
        self.spawned_npcs = []
        
    def spawn_item(self, item_name, amt=1, hidden=False, hfactor=0):
        # Fake item object with name
        class FakeItem:
            def __init__(self):
                self.name = item_name
                self.lock = None
                self.description = ""
                self.announce = ""
        item = FakeItem()
        self.items_here.append(item)
        self.spawned_items.append(item)
        return item
        
    def spawn_npc(self, npc_class_name):
        class FakeNpc:
            def __init__(self):
                self.name = npc_class_name
                self.awareness = 10
        npc = FakeNpc()
        self.spawned_npcs.append(npc)
        return npc

class FakePlayer:
    def __init__(self):
        self.name = "Jean"
        self.tile = FakeTile()
        self.combat_events = []
        self.teleport_dest = None
        
    def teleport(self, dest_map, dest_coords):
        self.teleport_dest = (dest_map, dest_coords)

class FakeUniverse:
    def __init__(self):
        self.locked_chests = []

def test_memory_border():
    with patch('animations.animate_to_main_screen') as mock_anim, patch('story.effects.cprint') as mock_cprint:
        # style = top
        memory_border("top")
        assert mock_anim.called
        
        mock_anim.reset_mock()
        # style = bottom
        memory_border("bottom")
        assert not mock_anim.called
        
        # style = other
        memory_border("other")
        assert not mock_anim.called

def test_memory_flash_edge_cases():
    player = FakePlayer()
    tile = FakeTile()
    lines = [("Line 1", 1), ("Line 2", 1)]

    # check_conditions() calls pass_conditions_to_process() -> process(user_input=None),
    # which sets needs_input=True. Patch all I/O before calling it.
    with patch('story.effects.cprint'), patch('story.effects.time.sleep'), \
            patch('animations.animate_to_main_screen'):

        # 1. check_conditions / first-pass process (user_input=None)
        ev = MemoryFlash(player, tile, lines, aftermath_text=["Aftermath 1"])
        ev.check_conditions()         # internally calls process(user_input=None)
        assert ev.needs_input is True
        assert ev.input_type == "choice"
        assert ev.input_prompt == "The memory fades..."
        assert ev.description is not None

        # 2. second pass: user_input provided — clears needs_input and removes from tile
        tile.events_here.append(ev)
        ev.process(user_input="continue")
        assert ev.needs_input is False
        assert ev.completed is True
        assert ev not in tile.events_here

        # 3. repeat=True — should stay in tile.events_here after second pass
        ev_repeat = MemoryFlash(player, tile, lines, repeat=True)
        tile.events_here.append(ev_repeat)
        ev_repeat.process(user_input="continue")
        assert ev_repeat in tile.events_here

        # 4. not in tile.events_here but in player.combat_events — removes from there
        ev_combat = MemoryFlash(player, tile, lines)
        player.combat_events.append(ev_combat)
        ev_combat.process(user_input="continue")
        assert ev_combat not in player.combat_events

def test_effect_base():
    player = FakePlayer()
    ev = Effect("BaseEffect", player)
    # process spy
    ev.process = MagicMock()
    ev.pass_conditions_to_process()
    assert ev.process.called

def test_flare_arrow_impact():
    player = FakePlayer()
    
    class DummyTarget:
        def __init__(self):
            self.name = "TargetNPC"
            self.states = []
            
    class DummyMove:
        def __init__(self):
            self.user = player
            self.target = DummyTarget()
            
    move = DummyMove()
    ev = FlareArrowImpact(player, move)
    
    # Mock functions.inflict
    with patch('functions.inflict') as mock_inflict:
        ev.process()
        assert mock_inflict.called
        assert isinstance(mock_inflict.call_args[0][0], states.Enflamed)

def test_gold_from_heaven():
    player = FakePlayer()
    tile = player.tile
    ev = GoldFromHeaven(player, tile)
    
    ev.check_conditions()
    assert len(tile.spawned_items) == 1
    assert tile.spawned_items[0].name == "Gold"

def test_block():
    player = FakePlayer()
    tile = player.tile
    
    # 1. No params (blocks all directions)
    ev = Block(player, tile)
    ev.check_conditions()
    assert "north" in tile.block_exit
    assert "south" in tile.block_exit
    assert "east" in tile.block_exit
    assert "west" in tile.block_exit
    
    # 2. With params
    tile.block_exit = []
    ev2 = Block(player, tile, params=["northeast", "southwest"])
    ev2.process()
    assert "northeast" in tile.block_exit
    assert "southwest" in tile.block_exit
    assert "north" not in tile.block_exit

def test_make_key():
    player = FakePlayer()
    tile = player.tile
    uni = FakeUniverse()
    player.universe = uni
    
    # Add a locked chest mapping (lock_code, chest_alias)
    uni.locked_chests.append(("lock_123", "chest_A"))
    
    # Params include alias '^chest_A', 'name=SpecialKey', 'desc=My~Special~Key'
    ev = MakeKey(player, tile, params=["^chest_A", "name=SpecialKey", "desc=My~Special~Key"])
    ev.check_conditions()
    
    assert len(tile.spawned_items) == 1
    key = tile.spawned_items[0]
    assert key.lock == "lock_123"
    assert key.name == "SpecialKey"
    assert key.description == "My.Special.Key"
    assert "specialkey" in key.announce

def test_teleport():
    player = FakePlayer()
    tile = player.tile
    ev = Teleport(player, tile, target_map_name="map_b", target_coordinates=(5, 5))
    ev.check_conditions()
    assert player.teleport_dest == ("map_b", (5, 5))

def test_shrine_base():
    player = FakePlayer()
    tile = player.tile
    ev = Shrine(player, tile)
    ev.check_conditions()
    # base process does nothing
    ev.process()

def test_st_michael_shrine(capsys):
    player = FakePlayer()
    tile = player.tile
    ev = StMichael(player, tile)
    
    # Verify weapon choices generated
    assert len(ev.available_choices) == 3
    assert len(ev.input_options) == 3
    
    # get_input_prompt and get_input_options
    assert "INSTRUMENT" in ev.get_input_prompt()
    assert len(ev.get_input_options()) == 3
    
    # process with user_input = None (CLI presentation path)
    with patch('story.effects.time.sleep'), patch('story.effects.cprint'):
        ev.process(user_input=None)
        assert ev.needs_input is True
        
    # process with integer user_input
    # Choose option 1
    chosen_weapon_cls = ev.available_choices[1][1]
    with patch('functions.add_random_enchantments') as mock_enchant, patch('story.effects.cprint'):
        ev.process(user_input="1")
        assert ev.needs_input is False
        assert ev.completed is True
        # verify correct weapon spawned on tile
        assert any(item.name == chosen_weapon_cls for item in tile.spawned_items)
        assert mock_enchant.called

    # process with invalid/non-integer user_input (should default to choice 0)
    ev_invalid = StMichael(player, tile)
    chosen_weapon_default = ev_invalid.available_choices[0][1]
    with patch('functions.add_random_enchantments'), patch('story.effects.cprint'):
        ev_invalid.process(user_input="invalid")
        assert any(item.name == chosen_weapon_default for item in tile.spawned_items)
        
    # process with out of range index (should default to 0)
    ev_range = StMichael(player, tile)
    chosen_weapon_range = ev_range.available_choices[0][1]
    with patch('functions.add_random_enchantments'), patch('story.effects.cprint'):
        ev_range.process(user_input="99")
        assert any(item.name == chosen_weapon_range for item in tile.spawned_items)

def test_npc_spawner_event_class_resolution():
    player = FakePlayer()
    tile = FakeTile()
    
    # 1. npc_cls as None
    ev1 = NPCSpawnerEvent(player, tile)
    assert ev1._resolve_npc_class_name() is None
    
    # 2. npc_cls as dict format
    ev2 = NPCSpawnerEvent(player, tile, npc_cls={"__class_type__": "npc:Slime"})
    assert ev2._resolve_npc_class_name() == "Slime"
    
    ev3 = NPCSpawnerEvent(player, tile, npc_cls={"__class_type__": "bareclass"})
    assert ev3._resolve_npc_class_name() == "bareclass"
    
    # 3. npc_cls as type (NPC subclass)
    from npc import Slime
    ev4 = NPCSpawnerEvent(player, tile, npc_cls=Slime)
    assert ev4._resolve_npc_class_name() == "Slime"

def test_npc_spawner_spawn_failures():
    player = FakePlayer()
    tile = FakeTile()
    
    # Mock spawn_npc to raise Exception
    tile.spawn_npc = MagicMock(side_effect=Exception("Spawn failed"))
    
    # should catch exception and not crash
    ev = NPCSpawnerEvent(player, tile, npc_cls="Slime", count=2)
    ev.process()
    assert len(ev.spawned_npcs) == 0

def test_pulsing_gland_event():
    player = FakePlayer()
    tile = FakeTile()
    
    pg = PulsingGlandEvent(player, tile, npc_cls="Slime")
    assert pg.npc_cls == "Slime"
    
    # evaluate_for_map_entry is a no-op
    pg.evaluate_for_map_entry(player)
    
    # process
    with patch('time.sleep'), patch('builtins.print'):
        pg.process()
        assert pg.has_run is True
        assert len(tile.spawned_npcs) == 1
        assert tile.spawned_npcs[0].name == "Slime"
        
        # repeat call does nothing if has_run is True and not repeat
        tile.spawned_npcs = []
        pg.process()
        assert len(tile.spawned_npcs) == 0


# ---------------------------------------------------------------------------
# Additional coverage: StMichael duplicate-rejection loop (line 385)
# ---------------------------------------------------------------------------
def test_st_michael_duplicate_rejection():
    """Force random to always return the same value so the while-loop fires."""
    player = FakePlayer()
    tile = player.tile
    # Patch random.randint to cycle: first two calls return 0 (duplicate), third returns 1
    side_effects = [0, 0, 0, 1, 0, 2]
    with patch('random.randint', side_effect=side_effects):
        ev = StMichael(player, tile)
    # We just need the constructor to complete without error; choices may not be 3-unique
    # due to limited side_effect length, but the loop path was exercised.
    assert isinstance(ev.available_choices, list)


# ---------------------------------------------------------------------------
# NPCSpawnerEvent params-based initialisation paths
# ---------------------------------------------------------------------------
def test_npc_spawner_event_params_init():
    player = FakePlayer()
    tile = FakeTile()

    # params[0]=cls_name, params[1]=count — basic params path (lines 503-506)
    ev = NPCSpawnerEvent(player, tile, params=["Slime", 3])
    assert ev.npc_cls == "Slime"
    assert ev.count == 3

    # params with a coordinate override whose coord IS in tile.map (lines 507-515)
    coord = (1, 2)
    fake_other_tile = FakeTile()
    tile.map = {coord: fake_other_tile}
    ev2 = NPCSpawnerEvent(player, tile, params=["Slime", 1, list(coord)])
    assert ev2.spawn_tile is fake_other_tile

    # params with coordinate but coord NOT in map (branch: tile.map exists but coord absent)
    tile.map = {}
    ev3 = NPCSpawnerEvent(player, tile, params=["Slime", 1, [9, 9]])
    assert ev3.spawn_tile is tile  # falls back to default

    # params that raise an exception during parsing (line 516-517)
    ev4 = NPCSpawnerEvent(player, tile, params=None)  # no params → no try block needed
    assert ev4.count == 1


def test_npc_spawner_count_coercion_failure():
    """Trigger the except-branch when count cannot be cast to int (lines 520-521)."""
    player = FakePlayer()
    tile = FakeTile()
    # Pass a params list where params[1] is a non-numeric string
    ev = NPCSpawnerEvent(player, tile, params=["Slime", "not_a_number"])
    # count should fall back to 1
    assert ev.count == 1


# ---------------------------------------------------------------------------
# _resolve_npc_class_name — exception path & final None return (lines 540-542)
# ---------------------------------------------------------------------------
def test_resolve_npc_class_name_exception_and_none():
    player = FakePlayer()
    tile = FakeTile()

    # Non-str, non-dict, non-NPC-subclass object triggers the try/except
    class WeirdObject:
        pass

    ev = NPCSpawnerEvent(player, tile, npc_cls=WeirdObject())
    # Should return None via the except branch (or the final return None)
    result = ev._resolve_npc_class_name()
    assert result is None

    # dict with empty class_type → strip() returns "" → or None → None (line 534)
    ev2 = NPCSpawnerEvent(player, tile, npc_cls={"__class_type__": ""})
    assert ev2._resolve_npc_class_name() is None


# ---------------------------------------------------------------------------
# _do_spawn edge cases (lines 545-552)
# ---------------------------------------------------------------------------
def test_do_spawn_no_spawn_tile_uses_tile():
    """_do_spawn when spawn_tile is None but tile is set → uses tile (lines 546-547)."""
    player = FakePlayer()
    tile = FakeTile()
    ev = NPCSpawnerEvent(player, tile, npc_cls="Slime", count=1)
    ev.spawn_tile = None  # force None
    ev._do_spawn()
    assert len(tile.spawned_npcs) == 1


def test_do_spawn_no_spawn_tile_no_tile_returns_early():
    """_do_spawn when both spawn_tile and tile are None → early return (lines 548-549)."""
    player = FakePlayer()
    ev = NPCSpawnerEvent(player, None, npc_cls="Slime", count=1)
    ev.spawn_tile = None
    ev.tile = None
    ev._do_spawn()
    assert len(ev.spawned_npcs) == 0


def test_do_spawn_no_cls_name_returns_early():
    """_do_spawn when _resolve_npc_class_name() returns None → early return (line 552)."""
    player = FakePlayer()
    tile = FakeTile()
    ev = NPCSpawnerEvent(player, tile)  # npc_cls is None
    ev._do_spawn()
    assert len(tile.spawned_npcs) == 0


# ---------------------------------------------------------------------------
# NPCSpawnerEvent.process early-return (line 562)
# ---------------------------------------------------------------------------
def test_npc_spawner_process_early_return():
    """process() returns immediately when has_run=True and repeat=False (line 562)."""
    player = FakePlayer()
    tile = FakeTile()
    ev = NPCSpawnerEvent(player, tile, npc_cls="Slime", count=1)
    ev.process()  # first call spawns
    spawned_before = len(tile.spawned_npcs)
    ev.process()  # second call should be a no-op
    assert len(tile.spawned_npcs) == spawned_before


# ---------------------------------------------------------------------------
# NPCSpawnerEvent.evaluate_for_map_entry (lines 567-576)
# ---------------------------------------------------------------------------
def test_evaluate_for_map_entry_has_run_no_repeat():
    """Returns immediately when has_run=True and repeat=False (line 567-568)."""
    player = FakePlayer()
    tile = FakeTile()
    ev = NPCSpawnerEvent(player, tile, npc_cls="Slime")
    ev.has_run = True
    tile2 = FakeTile()
    tile2.map = object()
    player.map = tile2.map
    ev.spawn_tile = tile2
    ev.evaluate_for_map_entry(player)
    assert len(tile2.spawned_npcs) == 0


def test_evaluate_for_map_entry_map_matches_spawns():
    """Fires spawn when player.map matches spawn_tile.map (lines 571-574)."""
    player = FakePlayer()
    shared_map = object()

    tile = FakeTile()
    tile.map = shared_map

    player.map = shared_map

    ev = NPCSpawnerEvent(player, tile, npc_cls="Slime", count=1)
    ev.spawn_tile = tile

    ev.evaluate_for_map_entry(player)
    assert len(tile.spawned_npcs) == 1


def test_evaluate_for_map_entry_exception_returns():
    """Exception inside the try block is caught and returns silently (lines 575-576)."""
    player = FakePlayer()
    tile = FakeTile()
    ev = NPCSpawnerEvent(player, tile, npc_cls="Slime")
    # spawn_tile.map raises AttributeError → caught by except
    ev.spawn_tile = None
    ev.tile = None
    ev.evaluate_for_map_entry(player)  # must not raise


# ---------------------------------------------------------------------------
# PulsingGlandEvent default npc_cls / count guards (lines 607-611)
# ---------------------------------------------------------------------------
def test_pulsing_gland_defaults_when_no_npc_cls():
    """Default npc_cls is 'Slime', count is 1 when neither is supplied (lines 609, 611)."""
    player = FakePlayer()
    tile = FakeTile()
    pg = PulsingGlandEvent(player, tile)  # no npc_cls, no count
    assert pg.npc_cls == "Slime"
    assert pg.count == 1


# ---------------------------------------------------------------------------
# WhisperingStatue — full coverage (lines 629-728)
# ---------------------------------------------------------------------------
from story.effects import WhisperingStatue


def test_whispering_statue_correct_answer():
    player = FakePlayer()
    tile = player.tile
    tile.events_here = []
    ev = WhisperingStatue(player, tile)
    tile.events_here.append(ev)

    assert "River" in ev.input_options[0]["label"]
    assert "mouth" in ev.get_input_prompt()
    assert ev.get_input_options() == ev.input_options
    assert player.name in ev.description

    # check_conditions triggers process chain (it calls pass_conditions_to_process)
    # We test process() directly in API mode instead to avoid terminal input()
    with patch('story.effects.cprint'), patch('story.effects.time.sleep'):
        ev.process(user_input="1")  # correct answer
        assert ev.completed is True
        assert ev.needs_input is False
        # Gold should be spawned on the tile
        assert any(item.name == "Gold" for item in tile.spawned_items)
        # Event removed from tile
        assert ev not in tile.events_here


def test_whispering_statue_wrong_answer():
    player = FakePlayer()
    tile = player.tile
    tile.events_here = []
    ev = WhisperingStatue(player, tile)
    tile.events_here.append(ev)

    with patch('story.effects.cprint'), patch('story.effects.time.sleep'):
        ev.process(user_input="2")  # wrong answer
        assert ev.completed is True
        # A Slime should have been spawned (wrong answer punishment)
        assert len(tile.spawned_npcs) == 1
        assert tile.spawned_npcs[0].awareness == 999


def test_whispering_statue_empty_choice_defaults():
    """Empty string choice defaults to '1' (correct answer path)."""
    player = FakePlayer()
    tile = player.tile
    tile.events_here = []
    ev = WhisperingStatue(player, tile)
    tile.events_here.append(ev)

    with patch('story.effects.cprint'), patch('story.effects.time.sleep'):
        ev.process(user_input="")  # empty → defaults to "1"
        assert ev.completed is True
        assert any(item.name == "Gold" for item in tile.spawned_items)


def test_whispering_statue_repeat_stays_in_tile():
    """When repeat=True, event is NOT removed from events_here."""
    player = FakePlayer()
    tile = player.tile
    tile.events_here = []
    ev = WhisperingStatue(player, tile, repeat=True)
    tile.events_here.append(ev)

    with patch('story.effects.cprint'), patch('story.effects.time.sleep'):
        ev.process(user_input="1")
        assert ev in tile.events_here


def test_whispering_statue_check_conditions():
    """check_conditions() routes to process() (CLI path with no user_input)."""
    player = FakePlayer()
    tile = player.tile
    tile.events_here = []
    ev = WhisperingStatue(player, tile)
    tile.events_here.append(ev)

    # In CLI mode process(user_input=None) calls input() — patch it
    with patch('story.effects.cprint'), patch('story.effects.time.sleep'), \
            patch('builtins.input', return_value="1"):
        ev.check_conditions()
        assert ev.completed is True


# ---------------------------------------------------------------------------
# StMichael: tile removal path (line 459)
# ---------------------------------------------------------------------------
def test_st_michael_removes_from_tile_events_here():
    """StMichael.process() with valid input removes the event from tile.events_here (line 459)."""
    player = FakePlayer()
    tile = player.tile
    tile.events_here = []
    ev = StMichael(player, tile)
    tile.events_here.append(ev)  # <-- ensure ev IS in events_here

    with patch('functions.add_random_enchantments'), patch('story.effects.cprint'):
        ev.process(user_input="0")

    assert ev not in tile.events_here


# ---------------------------------------------------------------------------
# NPCSpawnerEvent params exception path (lines 516-517)
# ---------------------------------------------------------------------------
def test_npc_spawner_event_params_exception():
    """params that raise during parsing are caught silently (lines 516-517)."""
    player = FakePlayer()
    tile = FakeTile()
    # params[0] is an object that raises when accessed via len() in the third if-block
    # Easiest way: pass a params object whose __len__ raises
    class BadParams:
        def __getitem__(self, idx):
            if idx == 0:
                return "Slime"
            if idx == 1:
                return 1
            raise RuntimeError("boom")
        def __len__(self):
            return 3
        def __bool__(self):
            return True

    ev = NPCSpawnerEvent(player, tile, params=BadParams())
    # Should not raise; count coerces to 1 because params[1] succeeded
    assert ev.npc_cls == "Slime"


# ---------------------------------------------------------------------------
# _resolve_npc_class_name: final return None for non-NPC type (line 542)
# ---------------------------------------------------------------------------
def test_resolve_npc_class_name_non_npc_type_returns_none():
    """A plain class (type) that is NOT a NPC subclass reaches line 542 and returns None."""
    player = FakePlayer()
    tile = FakeTile()

    class NotAnNPC:
        pass

    ev = NPCSpawnerEvent(player, tile, npc_cls=NotAnNPC)
    result = ev._resolve_npc_class_name()
    assert result is None


# ---------------------------------------------------------------------------
# PulsingGlandEvent count < 1 guard (line 611)
# ---------------------------------------------------------------------------
def test_pulsing_gland_count_zero_defaults_to_one():
    """count=0 triggers the count < 1 branch and resets to 1 (line 611)."""
    player = FakePlayer()
    tile = FakeTile()
    pg = PulsingGlandEvent(player, tile, npc_cls="Slime", count=0)
    assert pg.count == 1


# ---------------------------------------------------------------------------
# WhisperingStatue: EOFError fallback in CLI path (lines 671-672)
# ---------------------------------------------------------------------------
def test_whispering_statue_cli_eoferror_fallback():
    """input() raising EOFError defaults choice to '1' (lines 671-672)."""
    player = FakePlayer()
    tile = player.tile
    tile.events_here = []
    ev = WhisperingStatue(player, tile)
    tile.events_here.append(ev)

    with patch('story.effects.cprint'), patch('story.effects.time.sleep'), \
            patch('builtins.input', side_effect=EOFError):
        ev.process(user_input=None)
        assert ev.completed is True
        # EOFError → choice="1" → correct answer → Gold spawned
        assert any(item.name == "Gold" for item in tile.spawned_items)
