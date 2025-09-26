import sys
import os
# Ensure project root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, repo_root)
# Also ensure the `src` directory is on sys.path so modules using bare imports (e.g. `from functions import ...`)
# resolve correctly when running this script standalone.
sys.path.insert(0, os.path.join(repo_root, 'src'))

from src.player import Player
import src.functions as functions
import src.items as items

class FakeRoom:
    def __init__(self):
        self.items_here = []
    def spawn_item(self, item_type: str):
        cls = getattr(items, item_type, None)
        if cls:
            inst = cls()
            self.items_here.append(inst)


p = Player()
# attach a fake room so drop() has somewhere to put items
p.current_room = FakeRoom()

print("Initial weight_tolerance_base:", p.weight_tolerance_base)
print("Initial weight_tolerance:", p.weight_tolerance)
print("Initial weight_current:", p.weight_current)

print('\nCalling refresh_stat_bonuses first time...')
functions.refresh_stat_bonuses(p)
print("After 1st refresh: weight_tolerance=", p.weight_tolerance)

print('\nCalling refresh_stat_bonuses second time...')
functions.refresh_stat_bonuses(p)
print("After 2nd refresh: weight_tolerance=", p.weight_tolerance)

# Find a droppable item (TatteredCloth is present in the default inventory)
cloth = None
for it in list(p.inventory):
    if it.__class__.__name__ == 'TatteredCloth':
        cloth = it
        break

if cloth:
    print('\nDropping TatteredCloth...')
    cloth.drop(p)
    print('After drop: weight_tolerance=', p.weight_tolerance)
    print('After drop: weight_current=', p.weight_current)
    print('Room items count:', len(p.current_room.items_here))
else:
    print('No TatteredCloth found in inventory; inventory contents:')
    for it in p.inventory:
        print(' -', it.__class__.__name__)
