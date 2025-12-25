import sys
import os
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from unittest.mock import MagicMock, patch
from player import Player, generate_output_grid
import items

class TestPlayerCore:
    @pytest.fixture
    def player(self):
        return Player()

    def test_generate_output_grid(self):
        data = ["A", "B", "C", "D"]
        grid = generate_output_grid(data, rows=2, cols=2)
        assert "A" in grid
        assert "B" in grid
        assert "C" in grid
        assert "D" in grid
        assert "*" in grid

    def test_attack_no_target(self, player):
        player.current_room = MagicMock()
        player.current_room.npcs_here = []
        
        with patch('builtins.print') as mock_print:
            player.attack()
            # Should print "There's nothing here for Jean to attack."
            mock_print.assert_called()
            # Check if "nothing here for Jean to attack" is in any of the calls
            found = False
            for call in mock_print.call_args_list:
                if "nothing here for Jean to attack" in call[0][0]:
                    found = True
                    break
            assert found

    def test_attack_with_target(self, player):
        player.current_room = MagicMock()
        target = MagicMock()
        target.name = "Goblin"
        target.hidden = False
        target.finesse = 10
        target.protection = 0
        target.hp = 100
        target.is_alive.return_value = True
        target.alert_message = "is angry!"
        
        player.current_room.npcs_here = [target]
        player.strength = 10
        player.finesse = 10
        player.eq_weapon = MagicMock()
        player.eq_weapon.name = "Sword"
        player.eq_weapon.damage = 10
        player.eq_weapon.str_mod = 1.0
        player.eq_weapon.fin_mod = 1.0
        player.combat_exp = {"Basic": 0}
        
        # Mock input to select target '0'
        # Mock random to ensure a hit
        with patch('builtins.input', return_value='0'):
            with patch('random.randint', return_value=50): # hit_chance = (98-10)+10 = 98. 50 < 98 is a hit.
                with patch('random.uniform', return_value=1.0):
                    with patch('functions.check_for_combat', return_value=[]):
                        with patch('player.combat') as mock_combat_module:
                            player.attack()
                            assert target.hp < 100
                            assert target.in_combat is True
                            assert player.combat_list == [target]
                            mock_combat_module.combat.assert_called_once_with(player)

    def test_testevent(self, player):
        player.current_room = MagicMock()
        player.testevent("EventName")
        player.current_room.spawn_event.assert_called_once_with("EventName", player, player.current_room, repeat=False, params=[])

    def test_player_init(self, player):
        assert player.name == "Jean"
        assert player.hp == 100
        assert player.maxhp == 100
        assert len(player.inventory) > 0
        assert player.level == 1
        assert player.is_alive() is True

    def test_get_hp_pcnt(self, player):
        player.hp = 50
        player.maxhp = 100
        assert player.get_hp_pcnt() == 0.5

    def test_is_alive(self, player):
        player.hp = 10
        assert player.is_alive() is True
        player.hp = 0
        assert player.is_alive() is False
        player.hp = -5
        assert player.is_alive() is False

    def test_change_heat(self, player):
        player.heat = 1.0
        player.change_heat(mult=2, add=0.5)
        assert player.heat == 2.5
        
        player.change_heat(mult=1, add=10)
        assert player.heat == 10.0  # Max heat
        
        player.change_heat(mult=1, add=-20)
        assert player.heat == 0.5  # Min heat

    def test_cycle_states(self, player):
        state1 = MagicMock()
        state2 = MagicMock()
        player.states = [state1, state2]
        
        player.cycle_states()
        state1.process.assert_called_once_with(player)
        state2.process.assert_called_once_with(player)

    def test_gain_exp_skill_announcement(self, player):
        player.skill_exp = {"Dagger": 0}
        player.known_moves = []
        
        # Mock skilltree
        skill = MagicMock()
        skill.name = "Slash"
        player.skilltree = MagicMock()
        player.skilltree.subtypes = {"Dagger": {skill: 10}}
        
        with patch('player.cprint') as mock_cprint:
            player.gain_exp(15, "Dagger")
            assert player.skill_exp["Dagger"] == 15
            mock_cprint.assert_called()
            # Check if "Jean may spend some of his earned exp" is in the call
            args, _ = mock_cprint.call_args
            assert "Jean may spend some of his earned exp" in args[0]

    def test_equip_item_multiple_candidates(self, player):
        item1 = MagicMock()
        item1.name = "Iron Sword"
        item1.announce = "A heavy sword"
        item1.isequipped = False
        item1.maintype = "Weapon"
        
        item2 = MagicMock()
        item2.name = "Steel Sword"
        item2.announce = "A sharp sword"
        item2.isequipped = False
        item2.maintype = "Weapon"
        
        player.inventory = [item1, item2]
        player.current_room = MagicMock()
        player.current_room.items_here = []
        
        # Mock input to select the second one
        # First call to confirm(item1) -> 'n'
        # Second call to confirm(item2) -> 'y'
        with patch('builtins.input', side_effect=['n', 'y']):
            player.equip_item("Sword")
            assert item1.isequipped is False
            assert item2.isequipped is True

    def test_equip_item_menu(self, player):
        item = MagicMock()
        item.name = "Iron Sword"
        item.maintype = "Weapon"
        item.isequipped = False
        
        player.inventory = [item]
        
        # Mock input: 'w' to select weapons, then '0' to select the first item
        with patch('builtins.input', side_effect=['w', '0']):
            selected = player.equip_item_menu()
            assert selected == item

    def test_commands(self, player):
        player.current_room = MagicMock()
        action = MagicMock()
        action.name = "Look"
        action.hotkey = "L"
        player.current_room.available_actions.return_value = [action]
        
        with patch('functions.await_input') as mock_await:
            player.commands()
            mock_await.assert_called_once()

    def test_move_fail(self, player):
        player.universe = MagicMock()
        player.location_x = 0
        player.location_y = 0
        player.map = {}
        
        with patch('player.tile_exists', return_value=None):
            with patch('player.time.sleep'): # Avoid sleeping in tests
                player.move(1, 0)
                assert player.location_x == 0
                assert player.location_y == 0

    def test_directional_moves(self, player):
        player.universe = MagicMock()
        player.map = {}
        tile = MagicMock()
        
        with patch('player.tile_exists', return_value=tile):
            player.move_north()
            assert player.location_y == -1
            player.move_south()
            assert player.location_y == 0
            player.move_east()
            assert player.location_x == 1
            player.move_west()
            assert player.location_x == 0
            player.move_northeast()
            assert player.location_x == 1
            assert player.location_y == -1
            player.move_northwest()
            assert player.location_x == 0
            assert player.location_y == -2
            player.move_southeast()
            assert player.location_x == 1
            assert player.location_y == -1
            player.move_southwest()
            assert player.location_x == 0
            assert player.location_y == 0

    def test_apply_state_replacement(self, player):
        state1 = MagicMock()
        state1.name = "Poison"
        state1.compounding = False
        
        state2 = MagicMock()
        state2.name = "Poison"
        state2.compounding = False
        
        player.states = [state1]
        player.apply_state(state2)
        
        assert state1 not in player.states
        assert state2 in player.states
        assert len(player.states) == 1

    def test_save(self, player):
        with patch('functions.save_select') as mock_save:
            player.save()
            mock_save.assert_called_once_with(player)

    def test_get_hp_pcnt_full(self, player):
        player.hp = 100
        player.maxhp = 100
        assert player.get_hp_pcnt() == 1.0

    def test_change_heat_bounds(self, player):
        player.heat = 5.0
        player.change_heat(mult=3) # 15.0 -> 10.0
        assert player.heat == 10.0
        
        player.change_heat(mult=0.01) # 0.1 -> 0.5
        assert player.heat == 0.5

    def test_refresh_weight_with_counts(self, player):
        item1 = MagicMock()
        item1.weight = 1.0
        item1.count = 5
        
        item2 = MagicMock()
        item2.weight = 2.0
        item2.count = 2
        
        player.inventory = [item1, item2]
        player.refresh_weight()
        assert player.weight_current == 9.0

    def test_stack_gold_complex(self, player):
        player.inventory = [items.Gold(10), items.TatteredCloth(), items.Gold(20), items.Gold(5)]
        player.stack_gold()
        
        gold_items = [item for item in player.inventory if isinstance(item, items.Gold)]
        assert len(gold_items) == 1
        assert gold_items[0].amt == 35
        assert items.TatteredCloth in [type(i) for i in player.inventory]

    def test_refresh_weight(self, player):
        # Mock items with weight
        item1 = MagicMock()
        item1.weight = 5.0
        item1.count = 1
        
        item2 = MagicMock()
        item2.weight = 2.0
        item2.count = 3
        
        player.inventory = [item1, item2]
        player.refresh_weight()
        assert player.weight_current == 11.0

    def test_get_equipped_items(self, player):
        item1 = MagicMock()
        item1.isequipped = True
        
        item2 = MagicMock()
        item2.isequipped = False
        
        player.inventory = [item1, item2]
        equipped = player.get_equipped_items()
        assert len(equipped) == 1
        assert equipped[0] == item1

    def test_learn_skill(self, player):
        skill = MagicMock()
        skill.name = "New Skill"
        
        # Initially doesn't know it
        player.known_moves = []
        player.learn_skill(skill)
        assert skill in player.known_moves
        
        # Learning again shouldn't add it twice
        player.learn_skill(skill)
        assert player.known_moves.count(skill) == 1

    def test_apply_state(self, player):
        state = MagicMock()
        state.name = "Poison"
        state.compounding = False
        
        player.states = []
        player.apply_state(state)
        assert state in player.states
        
        # Apply same state again (non-compounding)
        state2 = MagicMock()
        state2.name = "Poison"
        state2.compounding = False
        player.apply_state(state2)
        assert state2 in player.states
        assert state not in player.states
        assert len(player.states) == 1

    def test_apply_state_compounding(self, player):
        state = MagicMock()
        state.name = "Bleed"
        state.compounding = True
        
        player.states = []
        player.apply_state(state)
        assert state in player.states
        
        player.apply_state(state)
        state.compound.assert_called_once_with(player)
        assert len(player.states) == 1

    def test_gain_exp(self, player):
        player.exp = 0
        player.level = 1
        player.exp_to_level = 100
        
        # Gain some exp
        player.gain_exp(50)
        assert player.exp == 50
        assert player.level == 1
        
        # Gain enough to level up
        # Mock level_up to avoid interactive input and infinite loop
        def mock_level_up_side_effect():
            player.level += 1
            player.exp -= player.exp_to_level
            player.exp_to_level = player.level * 100

        with patch.object(Player, 'level_up', side_effect=mock_level_up_side_effect) as mock_level_up:
            player.gain_exp(60)
            assert player.level == 2
            mock_level_up.assert_called_once()

    def test_refresh_protection_rating(self, player):
        player.endurance = 20
        player.finesse = 10
        # Base protection = endurance / 10 = 2.0

        item = MagicMock()
        item.isequipped = True
        item.protection = 5
        item.str_mod = 0.1
        item.fin_mod = 0.1
        player.strength = 10
        # Item protection = 5 + (0.1 * 10) + (0.1 * 10) = 7

        player.inventory = [item]
        player.refresh_protection_rating()
        assert player.protection == 9.0

    def test_add_items_to_inventory(self, player):
        player.inventory = []
        player.weight_current = 0
        player.weight_tolerance = 10

        item = MagicMock()
        item.name = "Light Item"
        item.weight = 2
        item.count = 1

        player.add_items_to_inventory([item])
        assert item in player.inventory

        # Item too heavy
        heavy_item = MagicMock()
        heavy_item.name = "Heavy Item"
        heavy_item.weight = 20
        heavy_item.count = 1
        player.current_room = MagicMock()
        player.current_room.items_here = []
        
        player.add_items_to_inventory([heavy_item])
        assert heavy_item not in player.inventory
        assert heavy_item in player.current_room.items_here

    def test_move(self, player):
        player.universe = MagicMock()
        player.universe.game_tick = 0
        player.location_x = 0
        player.location_y = 0
        player.map = {}
        
        # Mock tile_exists to return a tile
        tile = MagicMock()
        tile.intro_text.return_value = "A room"
        
        with patch('player.tile_exists', return_value=tile):
            player.move(1, 0)
            assert player.location_x == 1
            assert player.location_y == 0
            assert player.universe.game_tick == 1
            
        # Move to non-existent tile
        with patch('player.tile_exists', return_value=None):
            player.move(1, 0)
            assert player.location_x == 1 # Stayed at 1 because move failed and it reverted
            assert player.location_y == 0

    def test_equip_item_success(self, player):
        item = MagicMock()
        item.name = "Sword"
        item.announce = "A sharp sword"
        item.isequipped = False
        item.maintype = "Weapon"
        item.interactions = ["equip"]
        
        player.inventory = [item]
        player.current_room = MagicMock()
        player.current_room.items_here = []
        
        player.equip_item("Sword")
        assert item.isequipped is True
        assert "unequip" in item.interactions
        assert "equip" not in item.interactions

    def test_equip_item_from_room(self, player):
        item = MagicMock()
        item.name = "Shield"
        item.announce = "A sturdy shield"
        item.isequipped = False
        item.maintype = "Armor"
        item.interactions = ["equip"]
        item.weight = 5
        
        player.inventory = []
        player.current_room = MagicMock()
        player.current_room.items_here = [item]
        player.weight_tolerance = 10
        player.weight_current = 0
        
        player.equip_item("Shield")
        assert item.isequipped is True
        assert item in player.inventory
        assert item not in player.current_room.items_here

    def test_unequip_item(self, player):
        item = MagicMock()
        item.name = "Sword"
        item.announce = "A sharp sword"
        item.isequipped = True
        item.maintype = "Weapon"
        item.interactions = ["unequip"]
        
        player.inventory = [item]
        player.current_room = MagicMock()
        player.current_room.items_here = []
        
        with patch('builtins.input', return_value='y'):
            player.equip_item("Sword")
            assert item.isequipped is False
            assert player.eq_weapon == player.fists
            assert "equip" in item.interactions
            assert "unequip" not in item.interactions

    def test_supersaiyan(self, player):
        player.supersaiyan()
        assert player.strength == 1000
        assert player.hp == 10000
        assert player.fatigue == 10000

    def test_stack_inv_items(self, player):
        item1 = MagicMock()
        item1.name = "Herb"
        item1.count = 1
        item1.stack_key.return_value = ("Herb",)
        
        item2 = MagicMock()
        item2.name = "Herb"
        item2.count = 2
        item2.stack_key.return_value = ("Herb",)
        
        player.inventory = [item1, item2]
        
        with patch('player.stack_inv_items') as mock_stack:
            player.stack_inv_items()
            mock_stack.assert_called_once_with(player)

    @patch('player.input', side_effect=['1', '2', '2', '3']) # Select Strength (1), then 2 points, then Finesse (2), then 3 points
    @patch('player.time.sleep')
    @patch('player.random.randint', side_effect=[1, 1, 1, 1, 1, 1, 5, 1, 2]) # Random bonuses (6x1), then 5 points to distribute, then selection 1, then 2 points
    def test_level_up_interactive(self, mock_randint, mock_sleep, mock_input, player):
        # Initial stats
        player.strength_base = 10
        player.finesse_base = 10
        player.exp = 200
        player.exp_to_level = 100
        player.level = 1
        player.intelligence = 10
        
        player.level_up()
        
        assert player.level == 2
        assert player.exp == 100
        # 10 (base) + 1 (random bonus) + 2 (allocated) = 13
        assert player.strength_base == 13
        # 10 (base) + 1 (random bonus) + 3 (allocated) = 14
        assert player.finesse_base == 14
        assert player.exp_to_level == 2 * (150 - 10) # 280

    @patch('player.input', return_value='y')
    def test_equip_item_with_phrase(self, mock_input, player):
        item = MagicMock()
        item.name = "Iron Sword"
        item.announce = "A sharp blade"
        item.isequipped = False
        item.maintype = "Weapon"
        item.interactions = ["equip"]
        player.inventory = [item]
        player.current_room = MagicMock()
        player.current_room.items_here = []
        
        player.equip_item(phrase="iron")
        
        assert item.isequipped is True
        assert "unequip" in item.interactions
        assert "equip" not in item.interactions

    @patch('player.input', return_value='y')
    def test_equip_item_from_room(self, mock_input, player):
        item = MagicMock()
        item.name = "Iron Sword"
        item.announce = "A sharp blade"
        item.isequipped = False
        item.maintype = "Weapon"
        item.weight = 5.0
        item.interactions = ["equip"]
        player.current_room = MagicMock()
        player.current_room.items_here = [item]
        player.weight_current = 0
        player.weight_tolerance = 100
        
        player.equip_item(phrase="iron")
        
        assert item in player.inventory
        assert item.isequipped is True
        assert item not in player.current_room.items_here

    @patch('player.input', return_value='y')
    def test_equip_item_already_equipped_remove(self, mock_input, player):
        item = MagicMock()
        item.name = "Iron Sword"
        item.announce = "A sharp blade"
        item.isequipped = True
        item.maintype = "Weapon"
        item.interactions = ["unequip"]
        player.inventory = [item]
        player.fists = MagicMock()
        player.current_room = MagicMock()
        player.current_room.items_here = []
        
        player.equip_item(phrase="iron")
        
        assert item.isequipped is False
        assert player.eq_weapon == player.fists
        assert "equip" in item.interactions

    def test_equip_item_accessory_logic(self, player):
        # Test that we can have two rings but a third replaces one
        ring1 = MagicMock()
        ring1.name = "Ring 1"
        ring1.announce = "A ring"
        ring1.maintype = "Accessory"
        ring1.subtype = "Ring"
        ring1.isequipped = True
        ring1.interactions = ["unequip"]
        
        ring2 = MagicMock()
        ring2.name = "Ring 2"
        ring2.announce = "A ring"
        ring2.maintype = "Accessory"
        ring2.subtype = "Ring"
        ring2.isequipped = True
        ring2.interactions = ["unequip"]
        
        ring3 = MagicMock()
        ring3.name = "Ring 3"
        ring3.announce = "A ring"
        ring3.maintype = "Accessory"
        ring3.subtype = "Ring"
        ring3.isequipped = False
        ring3.interactions = ["equip"]
        
        player.inventory = [ring1, ring2, ring3]
        player.current_room = MagicMock()
        player.current_room.items_here = []
        
        player.equip_item(phrase="Ring 3")
        
        assert ring3.isequipped is True
        assert ring1.isequipped is True
        assert ring2.isequipped is False

    @patch('player.time.sleep')
    @patch('functions.await_input')
    def test_death(self, mock_await, mock_sleep, player):
        player.hp = 0
        player.combat_hurt_msg = ["Ouch"]
        player.death()
        mock_await.assert_called_once()

    @patch('player.tile_exists')
    @patch('functions.print_items_in_room')
    @patch('functions.print_objects_in_room')
    @patch('functions.advise_player_actions')
    def test_move_success(self, mock_advise, mock_objs, mock_items, mock_tile_exists, player):
        player.universe = MagicMock()
        player.universe.game_tick = 0
        player.location_x = 0
        player.location_y = 0
        player.map = {}
        
        tile = MagicMock()
        tile.intro_text.return_value = "A new room"
        mock_tile_exists.return_value = tile
        
        player.move(1, 0)
        
        assert player.location_x == 1
        assert player.location_y == 0
        assert player.universe.game_tick == 1
        mock_tile_exists.assert_called_once()

    def test_look(self, player):
        player.current_room = MagicMock()
        player.current_room.intro_text.return_value = "Room description"
        
        with patch('functions.print_items_in_room'), \
             patch('functions.print_objects_in_room'), \
             patch('functions.advise_player_actions'):
            player.look()
            player.current_room.intro_text.assert_called_once()

    @patch('player.input', return_value='0')
    @patch('functions.await_input')
    def test_view_interactive(self, mock_await, mock_input, player):
        npc = MagicMock()
        npc.name = "Old Man"
        npc.description = "A wise old man"
        npc.hidden = False
        
        player.current_room = MagicMock()
        player.current_room.npcs_here = [npc]
        player.current_room.items_here = []
        player.current_room.objects_here = []
        
        player.view()
        mock_await.assert_called_once()

    @patch('functions.await_input')
    def test_view_phrase(self, mock_await, player):
        npc = MagicMock()
        npc.name = "Old Man"
        npc.description = "A wise old man"
        npc.hidden = False
        npc.announce = "He looks at you"
        npc.idle_message = ""
        
        player.current_room = MagicMock()
        player.current_room.npcs_here = [npc]
        player.current_room.items_here = []
        player.current_room.objects_here = []
        
        player.view(phrase="looks")
        mock_await.assert_called_once()

    @patch('player.time.sleep')
    @patch('player.random.uniform', return_value=1.0)
    def test_search(self, mock_uniform, mock_sleep, player):
        npc = MagicMock()
        npc.name = "Hidden Thief"
        npc.hidden = True
        npc.hide_factor = 10
        
        player.finesse = 10
        player.intelligence = 10
        player.faith = 10
        # search_ability = (10*2 + 10*3 + 10) * 1.0 = 60
        
        player.current_room = MagicMock()
        player.current_room.npcs_here = [npc]
        player.current_room.items_here = []
        player.current_room.objects_here = []
        
        player.search()
        assert npc.hidden is False

    @patch('player.input', return_value='0')
    @patch('player.combat')
    @patch('functions.check_for_combat', return_value=[])
    @patch('player.random.randint', return_value=50)
    @patch('player.random.uniform', return_value=1.0)
    def test_attack_interactive(self, mock_uniform, mock_randint, mock_check, mock_combat_mod, mock_input, player):
        npc = MagicMock()
        npc.name = "Goblin"
        npc.hidden = False
        npc.finesse = 10
        npc.protection = 5
        npc.hp = 20
        npc.is_alive.return_value = True
        npc.alert_message = "attacks!"
        
        player.current_room = MagicMock()
        player.current_room.npcs_here = [npc]
        player.eq_weapon = MagicMock()
        player.eq_weapon.name = "Sword"
        player.eq_weapon.damage = 10
        player.eq_weapon.str_mod = 1.0
        player.eq_weapon.fin_mod = 0.0
        player.strength = 10
        player.finesse = 10
        player.combat_exp = {"Basic": 0}
        
        player.attack()
        
        # power = 10 + (10 * 1.0) + (10 * 0.0) = 20
        # damage = (20 - 5) * 1.0 = 15
        assert npc.hp == 5
        assert player.combat_exp["Basic"] == 10
        mock_combat_mod.combat.assert_called_once_with(player)

    @patch('player.random.uniform', return_value=1.0)
    @patch('player.random.randint', return_value=50)
    @patch('functions.check_for_combat', return_value=[])
    def test_attack_phrase(self, mock_check, mock_randint, mock_uniform, player):
        npc = MagicMock()
        npc.name = "Goblin"
        npc.hidden = False
        npc.finesse = 10
        npc.protection = 5
        npc.hp = 20
        npc.is_alive.return_value = True
        npc.alert_message = "attacks!"
        npc.announce = "A green creature"
        npc.idle_message = ""

        player.current_room = MagicMock()
        player.current_room.npcs_here = [npc]
        player.eq_weapon = MagicMock()
        player.eq_weapon.name = "Sword"
        player.eq_weapon.damage = 10
        player.eq_weapon.str_mod = 1.0
        player.eq_weapon.fin_mod = 0.0
        player.strength = 10
        player.finesse = 10
        player.combat_exp = {"Basic": 0}

        with patch('player.combat') as mock_combat_mod:
            player.attack(phrase="green")
            assert npc.hp == 5
            mock_combat_mod.combat.assert_called_once_with(player)

    def test_teleport_success(self, player):
        mock_tile = MagicMock()
        mock_tile.intro_text.return_value = "Welcome to the new area!"
        
        target_map_name = "New Map"
        target_map = {'name': target_map_name}
        player.universe = MagicMock()
        player.universe.maps = [target_map]
        player.universe.game_tick = 0
        player.location_x = 0
        player.location_y = 0
        
        with patch('player.tile_exists', return_value=mock_tile), \
             patch('player.Player.drop_merchandise_items') as mock_drop:
            player.teleport(target_map_name, (5, 10))
            
            assert player.map == target_map
            assert player.location_x == 5
            assert player.location_y == 10
            assert player.universe.game_tick == 1
            mock_drop.assert_called_once()

    def test_teleport_invalid_location(self, player):
        target_map_name = "New Map"
        target_map = {'name': target_map_name}
        player.universe = MagicMock()
        player.universe.maps = [target_map]
        player.location_x = 0
        player.location_y = 0
        
        with patch('player.tile_exists', return_value=None), \
             patch('player.Player.drop_merchandise_items'):
            player.teleport(target_map_name, (5, 10))
            # Should not change location
            assert player.location_x == 0
            assert player.location_y == 0

    def test_spawnobject_npc(self, player):
        player.current_room = MagicMock()
        player.spawnobject("npc Guard hidden hfactor=5 delay=10 count=2")
        assert player.current_room.spawn_npc.call_count == 2
        player.current_room.spawn_npc.assert_any_call("Guard", hidden=True, hfactor=5, delay=10)

    def test_spawnobject_item(self, player):
        player.current_room = MagicMock()
        player.spawnobject("item Sword hidden hfactor=3")
        player.current_room.spawn_item.assert_called_once_with("Sword", hidden=True, hfactor=3)

    def test_spawnobject_event(self, player):
        player.current_room = MagicMock()
        player.spawnobject("event Trap repeat params=fire,10")
        player.current_room.spawn_event.assert_called_once_with("Trap", player, player.current_room, repeat=True, params=["fire", "10"])

    def test_spawnobject_object(self, player):
        player.current_room = MagicMock()
        player.spawnobject("object Chest params=locked,gold")
        player.current_room.spawn_object.assert_called_once_with("Chest", player, player.current_room, ["locked", "gold"], hidden=False, hfactor=0)

    def test_skillmenu_learn_skill(self, player):
        # Setup skilltree and skill_exp
        player.skill_exp = {"Combat": 1000}
        mock_skill = MagicMock()
        mock_skill.name = "Power Strike"
        mock_skill.description = "A powerful strike."
        
        player.skilltree = MagicMock()
        player.skilltree.subtypes = {"Combat": {mock_skill: 500}}
        player.known_moves = []
        
        # Inputs: 
        # "0" (select Combat)
        # "0" (select Power Strike)
        # "learn" (learn it)
        # "k" (return to skill menu)
        # "x" (exit)
        with patch('builtins.input', side_effect=["0", "0", "learn", "k", "x"]), \
             patch('player.Player.learn_skill') as mock_learn, \
             patch('functions.await_input'), \
             patch('player.functions.is_input_integer', side_effect=lambda x: x.isdigit()):
            player.skillmenu()
            
            mock_learn.assert_called_once_with(mock_skill)
            assert player.skill_exp["Combat"] == 500

    def test_view_map(self, player):
        mock_tile1 = MagicMock()
        mock_tile1.discovered = True
        mock_tile1.last_entered = 1
        mock_tile1.symbol = "O"
        
        mock_tile2 = MagicMock()
        mock_tile2.discovered = True
        mock_tile2.last_entered = 0 # Discovered but not visited
        
        player.map = {
            'name': 'Test Map',
            (0, 0): mock_tile1,
            (1, 0): mock_tile2
        }
        player.current_room = mock_tile1
        player.location_x = 0
        player.location_y = 0
        player.prev_location_x = 0
        player.prev_location_y = 0
        
        with patch('builtins.print') as mock_print, \
             patch('functions.await_input'):
            player.view_map()
            # Should print the map. We just check if it ran without error and called print.
            assert mock_print.called

    def test_alter(self, player):
        player.universe = MagicMock()
        player.universe.story = {"test_var": "old_value"}
        player.alter("test_var new_value")
        assert player.universe.story["test_var"] == "new_value"

    def test_drop_merchandise_items(self, player):
        mock_tile = MagicMock()
        mock_tile.items_here = []
        player.map = {}
        player.location_x = 0
        player.location_y = 0
        
        item1 = MagicMock()
        item1.merchandise = True
        item1.name = "Stolen Sword"
        
        item2 = MagicMock()
        item2.merchandise = False
        item2.name = "My Sword"
        
        player.inventory = [item1, item2]
        
        with patch('player.tile_exists', return_value=mock_tile), \
             patch('time.sleep'):
            player.drop_merchandise_items()
            
            assert item1 not in player.inventory
            assert item1 in mock_tile.items_here
            assert item2 in player.inventory

    def test_recall_friends(self, player):
        player.current_room = MagicMock()
        player.current_room.npcs_here = []
        
        friend_room = MagicMock()
        friend = MagicMock()
        friend.name = "Ally"
        friend.current_room = friend_room
        friend_room.npcs_here = [friend]
        
        player.combat_list_allies = [player, friend]
        
        player.recall_friends()
        
        assert friend.current_room == player.current_room
        assert friend in player.current_room.npcs_here
        assert friend not in friend_room.npcs_here

    def test_recall_friends_multiple(self, player):
        player.current_room = MagicMock()
        player.current_room.npcs_here = []
        
        friend1 = MagicMock()
        friend1.name = "Ally1"
        friend1.current_room = MagicMock()
        
        friend2 = MagicMock()
        friend2.name = "Ally2"
        friend2.current_room = MagicMock()
        
        friend3 = MagicMock()
        friend3.name = "Ally3"
        friend3.current_room = MagicMock()
        
        # Test party_size == 2
        player.combat_list_allies = [player, friend1, friend2]
        with patch('builtins.print') as mock_print:
            player.recall_friends()
            # Check if Ally1 and Ally2 are in the output
            output = "".join([call[0][0] for call in mock_print.call_args_list])
            assert "Ally1" in output
            assert "Ally2" in output
            
        # Test party_size == 3
        player.combat_list_allies = [player, friend1, friend2, friend3]
        with patch('builtins.print') as mock_print:
            player.recall_friends()
            output = "".join([call[0][0] for call in mock_print.call_args_list])
            assert "Ally1" in output
            assert "Ally2" in output
            assert "Ally3" in output

    def test_view_map_directions(self, player):
        mock_tile = MagicMock()
        mock_tile.discovered = True
        mock_tile.last_entered = 1
        
        player.map = {(0, 0): mock_tile, (1, 0): mock_tile, (0, 1): mock_tile, (1, 1): mock_tile}
        player.current_room = mock_tile
        
        with patch('builtins.print'), patch('functions.await_input'):
            # East
            player.prev_location_x, player.prev_location_y = 0, 0
            player.location_x, player.location_y = 1, 0
            player.view_map()
            
            # South
            player.prev_location_x, player.prev_location_y = 0, 0
            player.location_x, player.location_y = 0, 1
            player.view_map()
            
            # Diagonal
            player.prev_location_x, player.prev_location_y = 0, 0
            player.location_x, player.location_y = 1, 1
            player.view_map()

    def test_view_map_diagonals(self, player):
        mock_tile = MagicMock()
        mock_tile.discovered = True
        mock_tile.last_entered = 1
        
        player.map = {
            (0, 0): mock_tile, (1, 1): mock_tile,
            (1, 0): mock_tile, (0, 1): mock_tile
        }
        player.current_room = mock_tile
        
        with patch('builtins.print'), patch('functions.await_input'):
            # SE (dx=1, dy=1)
            player.prev_location_x, player.prev_location_y = 0, 0
            player.location_x, player.location_y = 1, 1
            player.view_map()
            
            # SW (dx=-1, dy=1)
            player.prev_location_x, player.prev_location_y = 1, 0
            player.location_x, player.location_y = 0, 1
            player.view_map()
            
            # NE (dx=1, dy=-1)
            player.prev_location_x, player.prev_location_y = 0, 1
            player.location_x, player.location_y = 1, 0
            player.view_map()
            
            # NW (dx=-1, dy=-1)
            player.prev_location_x, player.prev_location_y = 1, 1
            player.location_x, player.location_y = 0, 0
            player.view_map()

    def test_get_equipped_items(self, player):
        item1 = MagicMock()
        item1.isequipped = True
        item2 = MagicMock()
        item2.isequipped = False
        player.inventory = [item1, item2]
        
        equipped = player.get_equipped_items()
        assert item1 in equipped
        assert item2 not in equipped

    def test_print_status(self, player):
        state = MagicMock()
        state.name = "Poisoned"
        state.steps_left = 5
        player.states = [state]
        
        with patch('player.functions.refresh_stat_bonuses'), \
             patch('player.Player.refresh_protection_rating'), \
             patch('player.generate_output_grid', return_value="GRID"), \
             patch('builtins.print') as mock_print, \
             patch('player.cprint') as mock_cprint, \
             patch('functions.await_input'):
            player.print_status()
            
            assert mock_print.called
            assert mock_cprint.called

    def test_print_inventory(self, player):
        with patch('interface.InventoryInterface') as mock_iface:
            player.print_inventory()
            mock_iface.assert_called_once_with(player)
            mock_iface.return_value.run.assert_called_once()

    def test_take(self, player):
        with patch('interface.RoomTakeInterface') as mock_iface:
            player.take("all")
            mock_iface.assert_called_once_with(player)
            mock_iface.return_value.run.assert_called_once_with("all")

    def test_refresh_merchants(self, player):
        player.universe = MagicMock()
        mock_merchant = MagicMock()
        mock_cls = MagicMock()
        mock_merchant.__class__ = mock_cls
        # Mock MRO to include a class named 'Merchant'
        mock_cls.mro.return_value = [MagicMock(__name__='Merchant')]
        mock_merchant.name = "Trader Joe"
        mock_merchant.shop = MagicMock()
        
        mock_tile = MagicMock()
        mock_tile.npcs_here = [mock_merchant]
        player.universe.maps = [{(0, 0): mock_tile}]
        
        with patch('player.cprint'), patch('time.sleep'):
            player.refresh_merchants()
            mock_merchant.update_goods.assert_called_once()

    def test_level_up_interactive(self, player):
        player.level = 1
        player.exp = 200
        player.exp_to_level = 100
        player.intelligence = 10
        player.strength_base = 10
        player.finesse_base = 10
        player.speed_base = 10
        player.endurance_base = 10
        player.charisma_base = 10
        player.intelligence_base = 10
        
        # random.randint(0, 2) called 6 times for bonuses, then random.randint(6, 9) for points
        with patch('player.random.randint', side_effect=[1, 1, 1, 1, 1, 1, 8]), \
             patch('builtins.input', side_effect=["1", "5", "1", "3"]), \
             patch('player.cprint'), \
             patch('builtins.print'), \
             patch('time.sleep'):
            player.level_up()
            
            # Initial strength 10 + 1 (bonus) + 5 (allocated) + 3 (allocated) = 19
            assert player.strength_base == 19
            assert player.level == 2

    def test_stack_gold(self, player):
        gold1 = items.Gold(10)
        gold2 = items.Gold(20)
        player.inventory = [gold1, gold2, items.TatteredCloth()]
        
        player.stack_gold()
        
        gold_items = [i for i in player.inventory if isinstance(i, items.Gold)]
        assert len(gold_items) == 1
        assert gold_items[0].amt == 30

    def test_apply_state_new(self, player):
        state = MagicMock()
        state.name = "Poison"
        player.states = []
        player.apply_state(state)
        assert state in player.states

    def test_apply_state_compounding(self, player):
        state1 = MagicMock()
        state1.name = "Poison"
        state1.compounding = True
        player.states = [state1]
        
        state2 = MagicMock()
        state2.name = "Poison"
        
        player.apply_state(state2)
        state1.compound.assert_called_once_with(player)

    def test_cycle_states(self, player):
        state = MagicMock()
        player.states = [state]
        player.cycle_states()
        state.process.assert_called_once_with(player)

    def test_use_item_phrase(self, player):
        mock_item = MagicMock(spec=items.Restorative)
        mock_item.name = "Potion"
        mock_item.announce = "A red potion"
        mock_item.interactions = ["use"]
        mock_item.merchandise = False
        mock_item.__class__ = items.Restorative
        
        player.inventory = [mock_item]
        
        with patch('builtins.input', return_value="y"):
            player.use_item("Potion")
            mock_item.use.assert_called_once_with(player)

    def test_use_item_interactive(self, player):
        mock_item = MagicMock(spec=items.Restorative)
        mock_item.name = "Potion"
        mock_item.interactions = ["use"]
        mock_item.merchandise = False
        mock_item.__class__ = items.Restorative
        
        player.inventory = [mock_item]
        
        # Inputs:
        # "c" (select Consumables)
        # "0" (select Potion)
        # "x" (exit)
        with patch('builtins.input', side_effect=["c", "0", "x"]), \
             patch('player.cprint'), \
             patch('builtins.print'), \
             patch('player.functions.is_input_integer', side_effect=lambda x: x.isdigit()):
            player.use_item()
            mock_item.use.assert_called_once_with(player)

    def test_add_items_to_inventory(self, player):
        player.weight_tolerance = 100
        player.weight_current = 90
        player.current_room = MagicMock()
        player.current_room.items_here = []
        
        item1 = MagicMock()
        item1.name = "Heavy Rock"
        item1.weight = 20
        # Remove count to test the branch where it doesn't exist
        if hasattr(item1, 'count'):
            del item1.count
        
        item2 = MagicMock()
        item2.name = "Light Feather"
        item2.weight = 1
        item2.count = 1
        
        with patch('player.stack_inv_items'):
            player.add_items_to_inventory([item1, item2])
            
            assert item1 not in player.inventory
            assert item1 in player.current_room.items_here
            assert item2 in player.inventory

    def test_show_bars(self, player):
        player.hp = 50
        player.maxhp = 100
        player.fatigue = 75
        player.maxfatigue = 150
        
        with patch('builtins.print') as mock_print:
            player.show_bars()
            assert mock_print.called

    def test_commands(self, player):
        player.current_room = MagicMock()
        action = MagicMock()
        action.name = "Look"
        action.hotkey = "L"
        player.current_room.available_actions.return_value = [action]
        
        with patch('player.cprint'), patch('functions.await_input'):
            player.commands()
            player.current_room.available_actions.assert_called_once()

    def test_refresh_moves(self, player):
        move1 = MagicMock()
        move1.viable.return_value = True
        move2 = MagicMock()
        move2.viable.return_value = False
        player.known_moves = [move1, move2]
        
        viable = player.refresh_moves()
        assert move1 in viable
        assert move2 not in viable
