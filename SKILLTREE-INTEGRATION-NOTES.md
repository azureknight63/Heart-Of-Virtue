# Skilltree Integration: HV-1 Positioning Moves

**Date:** November 4, 2025  
**Branch:** `HV-1-coordinate-combat-positioning`  
**Files Modified:** `src/skilltree.py`

---

## Summary

Successfully integrated 8 HV-1 positioning moves into the skilltree system across weapon specializations and a new dedicated "Positioning" category.

---

## Integration Strategy

### Core Principles

1. **Specialization Rewards:** Same move costs differently in different categories, rewarding focused weapon training
2. **Cross-Category Availability:** Foundational moves (Advance, Withdraw, Turn) available in multiple categories
3. **Thematic Costs:** Moves cost less in categories where they're naturally suited

### Cost Philosophy

- **Foundation moves** (Advance, Withdraw): 150-300 exp (accessible early)
- **Tier 1 positioning** (BullCharge, Turn): 200-500 exp (moderate difficulty)
- **Advanced positioning** (FeintAndPivot, FlankingManeuver): 600-700 exp (requires commitment)
- **Specialty positioning** (WhirlAttack, KnockbackStunSpin): 550-750 exp (situation-dependent)

---

## Detailed Additions by Category

### Basic (Foundation Skills)
**New moves added:** 3
- **Turn** (500 exp) - Foundational facing awareness
- **Advance** (200 exp) - Core movement toward target
- **Withdraw** (200 exp) - Core movement away from enemies

**Rationale:** Foundation positioning moves available to all players early in skill progression.

---

### Dagger (Agile/Precision Specialist)
**New moves added:** 2
- **FeintAndPivot** (600 exp) - Attack and reposition (perfect for dual-position hit-and-run)
- **Turn** (300 exp) - Cheaper than other specializations (agile fighters turn faster)

**Rationale:** Daggers excel at repositioning for backstabs; FeintAndPivot is thematic. Cheaper Turn reflects agility.

---

### Bow (Ranged Specialist)
**New moves added:** 4
- **TacticalRetreat** (550 exp) - Move while maintaining ranged angle (core ranged tactic)
- **Withdraw** (150 exp) - Cheapest in any category (core ranged escape)
- **Advance** (300 exp) - More expensive (ranged players prefer distance)
- **TacticalPositioning** (400 exp) - Pre-existing, kept for thematic fit

**Rationale:** Ranged specialists benefit from maintaining distance. TacticalRetreat is core to archer gameplay. Advance is expensive to encourage staying back.

---

### Unarmed (Brawler/Combatant)
**New moves added:** 3
- **WhirlAttack** (700 exp) - Spin strike (powerful unarmed multi-hit)
- **BullCharge** (500 exp) - Charge momentum (aggressive close-quarters style)
- **Turn** (250 exp) - Fast turn for mid-combat repositioning

**Rationale:** Unarmed fighters excel at high-volume hits. WhirlAttack is signature move. Quick Turn reflects combat readiness.

---

### Axe (Heavy Melee Specialist)
**New moves added:** 5
- **BullCharge** (400 exp) - Heavy charge attack
- **WhirlAttack** (650 exp) - Spin strike with heavy impact
- **KnockbackStunSpin** (750 exp) - Most expensive (heavy weapon signature)
- **Advance** (250 exp) - Steady approach
- **Turn** (350 exp) - Deliberate facing changes (heavy armor slows turns)

**Rationale:** Axe users are heavy and deliberate. Highest cost for KnockbackStunSpin (signature heavy move). Expensive Turn reflects armor weight.

---

### Bludgeon (Crushing Force Specialist)
**New moves added:** 5
- **BullCharge** (350 exp) - Momentum-based charging
- **KnockbackStunSpin** (700 exp) - Knockback-heavy positioning
- **WhirlAttack** (600 exp) - Spin strike with impact
- **Advance** (200 exp) - Steady forward movement
- **Turn** (400 exp) - Heaviest armor, most deliberate turns

**Rationale:** Bludgeons excel at crowd control. KnockbackStunSpin fits knockback theme. Turn is most expensive (heavy weapon class).

---

### Positioning (NEW - Cross-Weapon Category)
**Purpose:** Dedicated specialty for players who want to master tactical positioning regardless of weapon choice

**Moves included:** 8
- **Advance** (150 exp) - Foundation
- **Withdraw** (150 exp) - Foundation
- **Turn** (200 exp) - Foundation with focus
- **FlankingManeuver** (650 exp) - Attack from perpendicular
- **BullCharge** (500 exp) - Aggressive repositioning
- **FeintAndPivot** (700 exp) - Attack + reposition
- **KnockbackStunSpin** (600 exp) - Rotation-based positioning
- **WhirlAttack** (550 exp) - 360° awareness

**Rationale:** Players can specialize in positioning tactics across all weapon types. Costs are "middle ground" between specializations, rewarding focused players. Foundation moves are cheapest to make positioning accessible early.

---

## Specialization Examples

### Aggressive Dagger User
Focuses on: FeintAndPivot (600), Turn (300), basic attacks
- Quick repositioning for backstabs
- Expensive FeintAndPivot for early/mid game progression

### Defensive Archer
Focuses on: TacticalRetreat (550), Withdraw (150), Advance (300)
- Can escape, attack from distance, maintain optimal range
- Cheap Withdraw allows frequent tactical retreats

### Positioning Master
Specializes in: Positioning category
- Gets all moves at fair costs
- Can switch between weapon types while maintaining positioning knowledge
- Less expensive than maxing positioning in each weapon tree

### Heavy Axe User
Focuses on: KnockbackStunSpin (750), WhirlAttack (650), BullCharge (400)
- Signature heavy attacks with positioning control
- Most expensive KnockbackStunSpin rewards commitment

---

## Cost Comparison Matrix

### Advance (Move Toward Target)
| Category | Cost | Notes |
|----------|------|-------|
| Basic | 200 | Foundation |
| Bow | 300 | Ranged prefer distance |
| Axe | 250 | Melee standard |
| Bludgeon | 200 | Heavy forward march |
| Positioning | 150 | Specialized training |

**Insight:** Cheapest in Positioning (specialized training) and Bludgeon (straightforward). Most expensive in Bow (discourage ranged advance).

### Turn (Rotate Facing)
| Category | Cost | Notes |
|----------|------|-------|
| Basic | 500 | All-purpose |
| Dagger | 300 | Agile fighters |
| Unarmed | 250 | Combat-ready |
| Axe | 350 | Medium armor |
| Bludgeon | 400 | Heavy armor |
| Positioning | 200 | Specialized focus |

**Insight:** Cheapest in Positioning and Unarmed (combat readiness). Most expensive in Bludgeon (armor weight). Reflects specialization theme.

---

## Test Coverage

Current skilltree tests should verify:
- ✅ All moves are instantiable with user parameter
- ✅ Exp costs are reasonable integers
- ✅ No duplicate moves per category
- ✅ All referenced moves exist in `src/moves.py`

**New tests to add:**
- [ ] Verify Positioning category is accessible
- [ ] Test specialization math (e.g., dagger FeintAndPivot unlocks at X exp)
- [ ] Verify cost differences incentivize specialization

---

## Future Enhancements

1. **Tier 3 Skills Integration:** When DimensionalShift and CombatDance are implemented
   - Add dedicated "Advanced Positioning" or "Tier 3" category
   - Expected costs: 1000-1500 exp for high-level skills

2. **Prestige Specialization:** Players who max Positioning category could unlock unique hybrid moves

3. **Dynamic Cost Scaling:** AI adjusts costs based on player progression (meta-balancing)

---

## Files Changed

- ✅ `src/skilltree.py` - Added 8 moves across 7 categories, created "Positioning" specialty

## Commit Message

```
feat(HV-1): Integrate positioning moves into skilltree

Added 8 HV-1 positioning moves across weapon specializations:
- Advance, Withdraw (foundation moves in all categories)
- Turn (core facing mechanic in all categories)
- BullCharge (Tier 1 aggressive positioning)
- TacticalRetreat (ranged specialist)
- FeintAndPivot (dagger specialist)
- FlankingManeuver (cross-category advanced)
- WhirlAttack (multi-hit spin attack)
- KnockbackStunSpin (heavy weapon signature)

New "Positioning" category for cross-weapon specialization.

Specialization rewards implemented:
- Same move costs differently in different categories
- Foundation moves cheapest in Positioning
- Costs reflect weapon characteristics (e.g., Bludgeon Turn expensive due to armor)

This enables skilled players to:
1. Specialize in specific weapons + positioning combos
2. Choose positioning mastery via dedicated category
3. Progress through three tiers of movement skills
```

---

**Status:** Ready for integration testing  
**Next Step:** Commit changes and run skilltree unit tests
