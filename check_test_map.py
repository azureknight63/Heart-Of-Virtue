import json

with open('src/resources/maps/testing-map.json') as f:
    test_map = json.load(f)

# Get all coordinates
tiles = sorted([eval(k) for k in test_map.keys()])
print(f"Testing map has {len(tiles)} tiles:")
for x, y in tiles:
    exits = test_map[str((x, y))].get('exits', [])
    print(f"  ({x}, {y}): exits={exits}")
