# UAT Guide: Memory Flash System

## Quick Test - Standalone Memory Flash

Run this to see just the memory flash sequence without playing through the game:

```powershell
python test_memory_flash.py
```

**What to verify:**
- [ ] Animation plays (magenta "MEMORY" text with stars)
- [ ] Decorative borders appear properly
- [ ] Memory text is magenta and readable
- [ ] Timing feels appropriate (not too fast/slow)
- [ ] Aftermath text (Jean's reaction) appears in cyan
- [ ] Press any key prompt works
- [ ] No errors or crashes

---

## Full Integration Test - Play Through Game

To test the memory flash in actual gameplay context:

### Option 1: Quick Start from Save (Recommended)
If you have a save file near the first Rumbler encounter, load it and proceed to the battle.

### Option 2: Start New Game
1. Start the game:
   ```powershell
   python src/game.py
   ```

2. Create a new character when prompted

3. Navigate through the tutorial:
   - Press the wall depression to open the exit
   - Go east to the bridge
   - Continue east to the chamber with the chest

4. Open the wooden chest
   - This triggers the first Rock Rumbler battle

5. **Defeat the first Rock Rumbler**
   - After victory, the memory flash should trigger automatically
   - You'll see the animation and Emily memory sequence

6. Verify the experience:
   - [ ] Memory triggers at the right moment (after first Rumbler defeat)
   - [ ] Doesn't interrupt combat flow awkwardly
   - [ ] Emotional impact is appropriate
   - [ ] Transition back to gameplay is smooth
   - [ ] More Rumblers spawn after the memory ends

---

## Rapid Testing Setup

To quickly get to the memory flash without playing through:

### Create a test save file:
```powershell
python -c "
import sys
sys.path.insert(0, 'src')
from src.player import Player
from src.universe import Universe
import pickle

# Create player and universe
p = Player()
p.name = 'Test'
u = Universe()
u.player = p

# Teleport to the chest room (adjust coordinates as needed)
# This is the room where the first Rumbler battle happens
p.tile = u.get_tile('dark-grotto', (7, 1))  # Adjust if needed
p.location = (7, 1)
p.map = u.maps['dark-grotto']

# Give basic equipment for the fight
from src.items import RustedIronMace
p.inventory.append(RustedIronMace())
p.equip_item('Rusted Iron Mace')

# Set reasonable stats
p.level = 2
p.hp = 50
p.maxhp = 50

# Save
with open('uat_memory_test.sav', 'wb') as f:
    pickle.dump((p, u), f)

print('✓ UAT save file created: uat_memory_test.sav')
"
```

Then load it:
```powershell
python src/game.py
# Select the load option and choose uat_memory_test.sav
```

---

## What to Look For

### ✅ Success Criteria:
1. **Animation Quality**
   - Clean, smooth animation
   - Magenta color is visible and aesthetic
   - Stars effect adds to atmosphere

2. **Memory Content**
   - Text is evocative and emotional
   - Pacing allows reading without rushing
   - Emily memory hints at loss effectively
   - Fragmentation at end conveys trauma

3. **Integration**
   - Triggers at appropriate story moment
   - Doesn't break immersion
   - Transition in/out feels natural

4. **Technical**
   - No errors or crashes
   - Aftermath text displays correctly
   - Player can continue after memory

### ❌ Issues to Watch For:
- Animation doesn't play or crashes
- Text scrolls too fast to read
- Colors don't display (terminal compatibility)
- Memory triggers at wrong time
- Can't continue gameplay after memory
- Timing feels off (too rushed or too slow)

---

## Feedback Template

After testing, note any issues:

**Animation:**
- [ ] Plays correctly
- Issues: ___________

**Memory Content:**
- [ ] Emotionally engaging
- [ ] Readable pacing
- Issues: ___________

**Integration:**
- [ ] Triggers at right moment
- [ ] Smooth transitions
- Issues: ___________

**Suggested Changes:**
___________

---

## Quick Fixes

If you encounter issues:

**Animation doesn't play:**
- Check terminal supports Unicode/ANSI colors
- Try different terminal (Windows Terminal recommended)

**Text too fast/slow:**
- Edit timing values in `src/story/ch01.py` (Ch01_Memory_Emily class)
- Each tuple is (text, pause_duration_in_seconds)

**Wrong trigger point:**
- Memory triggers in `Ch01PostRumbler.process()` method
- Can be moved to different event if needed

**Colors not visible:**
- Ensure neotermcolor is installed
- Check terminal color support

---

## Next Steps After UAT

Based on test results:
1. Adjust timing if needed
2. Refine memory text for better impact
3. Consider adding more memories at other story points
4. Merge to master once satisfied
