# Acceptance Testing Plan

To make the most efficient use of your time, the `needs-testing` issues have been grouped by context. This allows you to test multiple related features or bugs within a single play session or workflow, minimizing context switching.

## 1. Core Systems & Configuration
*Test these before jumping into gameplay to ensure the foundation is stable.*

- [ ] **#56 Need config fallback**: Launch a fresh session without any `CONFIG_FILE` environment variable set. Verify that the game correctly falls back to a default map (like `dark-grotto`) and doesn't throw 404/400 errors on world endpoints.
- [ ] **#115 Save command failed**: In-game, go to the Command menu and click **Save**. Verify the game saves successfully without returning a "Command Failed" error.

## 2. Combat & Tactical Phase
*Engage in a battle (preferably with multiple enemies like Rock Rumblers) to test this cluster of issues.*

- [ ] **#121 Battlefield map needs work**: Observe the general map polish. Check animations, centering on Jean, clear friend/foe visuals, and verify zooming behavior (e.g., auto-zooming).
- [ ] **#127 Combat - Move cooldown card**: Use a move with a cooldown. Verify that a small cooldown card appears (likely in the LeftPanel or under HeroPanel), showing the remaining beats.
- [ ] **#122 Tactical Advisor targets far enemies**: Check the Tactical Advisor's suggestions. Ensure it only suggests viable moves (like Advance) for distant enemies instead of suggesting an Attack out of range.
- [ ] **#138 Not advancing towards the enemy**: Select the `Advance` maneuver. Verify that Jean actually moves closer to the targeted enemy.
- [ ] **#124 Improve UI around ally item use**: Use a restorative or stat-affecting item on an ally. Check if the UI clearly communicates the stat changes (e.g., different color text for HP gained).
- [ ] **#118 Rock Rumbler AI breakage**: Fight Rock Rumblers. Try resting during the combat. Ensure the enemy AI responds properly (doesn't just keep advancing when adjacent) and that fatigue resets correctly when the fight ends or resets.
- [ ] **#116 Death scene needs work**: Let your character die in combat. Verify that the death scene displays properly and correctly formatted.
- [ ] **#125 Add a loot management UI after battle**: Win the battle. Verify that a new loot management UI appears immediately after, allowing you to manage dropped loot without having to manually pick it up from the ground afterward.

## 3. Inventory & Narrative (Out of Combat)
*Test these while exploring the world and managing your character.*

- [ ] **#126 Add stack count indicator on Inventory panel**: Open your inventory. Look at stacked items and verify there is a clear, visible quantity indicator without needing to click into the item.
- [ ] **#123 Break up event text**: Trigger an event with a long text description. Verify that the text is broken up into readable chunks to control pacing, rather than scrolling too fast.
- [ ] **#117 Mynx LLM response contains error**: Find Mynx. Rapidly sequence interactions (Talk -> Pet -> Play) and verify no errors are thrown in the LLM response.

## 4. Map Editor
*Requires launching the Map Editor tool separately.*

- [ ] **#131 Container item loss on save**: Open the map editor (e.g., load `dark-grotto.json`). Open the properties dialog for a container with items (like `remains` at 5,5). Close the dialog without making changes, then reopen it. Verify the items are still there.

## 5. Infrastructure / CI
*No in-game testing required.*

- [ ] **#136 Remove black from CI**: Open a dummy PR or check recent GitHub Actions runs to verify that the Black formatter is no longer part of the CI pipeline.
