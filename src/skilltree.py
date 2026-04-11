import moves


class Skilltree:
    def __init__(self, user):
        """
        List all learnable skills. When the player gains exp from a specific action, like attacking with a weapon,
        that exp goes into a pool.
        When the player has earned enough exp to learn a skill, he may "buy" the skill from the skill menu.
        Skills are represented in this format: "Skill_name": exp_required
        """
        self.subtypes = {  # todo add more skills
            "Basic": {  # Basic class skills always gain exp along with the player and
                # don't need to be called out in an ability
                moves.Dodge(user): 100,
                moves.TacticalPositioning(user): 1000,
                moves.StrategicInsight(user): 500,
                moves.MasterTactician(user): 1500,
                # Note: Turn, Advance, Withdraw are available by default (not in skilltree)
                # moves.AggressiveStance(user): 150  # Shift to an aggressive fighting stance; ++str, spd; -fin, end
                # moves.DefensiveStance(user): 150  # ++fin, end, -str, fth, cha
            },
            "Dagger": {
                moves.Slash(user): 15,  # 150
                moves.QuietMovement(user): 350,
                moves.FeintAndPivot(
                    user
                ): 600,  # HV-1: Attack and reposition behind target (specialized for dual-position attacks)
                moves.QuickSwap(
                    user
                ): 450,  # HV-1 Tier 2: Swap with ally (precision timing)
                moves.Backstab(user): 300,  # positional bonus damage from flank/behind
                moves.ShadowStep(user): 400,  # passive: silent approach
            },
            "Bow": {
                # moves.Hawkeye(user): 100,  # Focus on surroundings;
                # increases base accuracy for a duration (adds a status)
                moves.TacticalPositioning(user): 300,  # cheaper than Basic (300 vs 1000): repositioning is the core loop for archers
                moves.TacticalRetreat(
                    user
                ): 550,  # HV-1: Move away while maintaining ranged angle (core ranged tactic)
                moves.FlankingManeuver(
                    user
                ): 700,  # HV-1: Move to the side of the target to gain advantage (advanced ranged tactic)
                moves.QuickSwap(
                    user
                ): 500,  # HV-1 Tier 2: Swap with ally (tactical coordination)
                moves.EagleEye(user): 350,  # passive: accuracy at range
            },
            "Unarmed": {
                moves.Jab(
                    user
                ): 100,  # quick unarmed attack that causes little damage but has a
                # very low fatigue cost and zero cooldown
                moves.WhirlAttack(
                    user
                ): 600,  # HV-1: Spin strike hitting nearby enemies — cheaper than Axe/Bludgeon (no weapon weight to manage)
                moves.BullCharge(
                    user
                ): 500,  # HV-1: Charge with momentum (aggressive unarmed style)
                moves.QuickSwap(
                    user
                ): 400,  # HV-1 Tier 2: Swap with ally (team-based fighting)
                moves.IronFist(user): 450,  # passive: increased unarmed damage — core investment for fists-as-weapons
                # moves.Kick(user): 150  # quick leg attack; more damaging than a jab with a higher
                # fatigue cost and small cooldown
                # moves.Haymaker(user): 250  # strong unarmed attack that causes significant damage but has
                # a high fatigue and cooldown cost, slower cast
                # moves.Trip(user): 250  # sweeping leg attack with a 25% chance to trip
                # humanoid opponents, stunning them
                # moves.Throw(user): 250  # unarmed; attempt to toss an opponent, causing moderate damage and
                # increasing their distance from the player
                # moves.Combo(user): 250  # arrange a succession of unarmed attacks against a target.
                # Each successful hit boosts Heat. A miss or parry breaks the combo.
                # moves.Disarm(user): 500  # attempt to disarm the target, causing it to drop its weapon to the ground
                # moves.Takedown(user): 500  # instead of a normal parry, this will throw your attacker to the ground,
                # stunning them
                # moves.Callous(user): 250  # while unarmed, glancing blows cause half their normal damage to the player
                # moves.Footwork(user): 500  # while unarmed, 15% increased chance for an incoming hit to be
                # a glancing blow
                # moves.Attentive(user): 250  # while using an unarmed attack, you have a 20% chance to
                # follow it up with an immediate Jab
                # moves.Spinkick(user): 350  # hit all enemies within 5 distance, knocking them back and
                # causing light damage
            },
            "Scythe": {
                moves.PommelStrike(user): 125,  # quick close-range pommel attack
                moves.Reap(user): 250,  # frontal arc hitting all enemies in range
                moves.ReapersMark(user): 400,  # mark target for +25% damage on next hit
                moves.DeathsHarvest(user): 650,  # draining strike; heals 30% of damage dealt
                moves.GrimPersistence(user): 300,  # passive: bonus damage vs targets below 35% HP
                moves.HauntingPresence(user): 350,  # passive: unsettling aura
            },
            "Axe": {
                moves.Slash(user): 50,
                moves.Parry(user): 100,
                moves.BullCharge(
                    user
                ): 350,  # HV-1: Charge with momentum — axe is lighter than bludgeon, charge flows naturally
                moves.WhirlAttack(
                    user
                ): 650,  # HV-1: Spin strike hitting nearby enemies
                moves.VertigoSpin(
                    user
                ): 750,  # HV-1: Attack with knockback and rotation
                moves.QuickSwap(
                    user
                ): 520,  # HV-1 Tier 2: Swap with ally (defensive formation)
                moves.CleaveInstinct(user): 350,  # passive: reduced prep after a kill
            },
            "Bludgeon": {
                moves.Parry(user): 150,  # harder to parry with a heavy weapon than with an axe or sword
                moves.PowerStrike(user): 1,
                moves.BullCharge(
                    user
                ): 400,  # HV-1: Charge with momentum — managing inertia costs more than with a lighter axe
                moves.VertigoSpin(user): 700,  # HV-1: Knockback-heavy positioning move
                moves.WhirlAttack(user): 750,  # HV-1: Spin strike — most expensive of the three types (heaviest weapon)
                moves.QuickSwap(
                    user
                ): 550,  # HV-1 Tier 2: Swap with ally (heavy tank coordination)
                moves.HeavyHanded(user): 350,  # passive: increased stagger on bludgeon hits
            },
            "Sword": {
                moves.Slash(user): 50,  # basic slashing attack (viable() already covers Sword)
                moves.Parry(user): 50,  # foundational to the duelist — cheaper than Axe or Bludgeon
                moves.Thrust(user): 250,  # fast piercing attack, lower power, quicker prep
                moves.DisarmingSlash(user): 350,  # rattles target; applies Disoriented on hit
                moves.Riposte(user): 550,  # counter while Parrying — heat-boosted
                moves.BladeMastery(user): 300,  # passive: reduced fatigue on sword attacks
                moves.CounterGuard(user): 450,  # passive: reduced fatigue for parrying
            },
            "Spear": {
                moves.Thrust(user): 50,  # fast piercing thrust (longer range on Spear by weapon stats)
                moves.PommelStrike(user): 150,  # close-range fallback
                moves.KeepAway(user): 400,  # minor damage + push target back
                moves.Lunge(user): 300,  # step-forward + pierce, closes short gaps
                moves.Impale(user): 650,  # penetrating thrust ignoring 60% of protection
                moves.SentinelsVigil(user): 500,  # passive: range-denial discipline
            },
            "Pick": {
                moves.PommelStrike(user): 125,  # versatile quick attack
                moves.ArmorPierce(user): 250,  # zeroes all protection — powerful enough to cost more than a basic attack
                moves.ChipAway(user): 350,  # 3 independent light strikes
                moves.ExploitWeakness(user): 450,  # hit + Disoriented state
                moves.Stupefy(user): 600,  # heavy pommel; always Disorients on hit
                moves.WorkTheGap(user): 350,  # passive: signature pick ability — stacking protection reduction
            },
            "Crossbow": {
                moves.ShootCrossbow(user): 50,  # base ranged attack, longer reload than bow
                moves.BroadheadBolt(user): 400,  # heavy bolt, +25 base power
                moves.AimedShot(user): 500,  # 25-beat aim, +50% power, +15 accuracy
                moves.PinningBolt(user): 600,  # damage + Disoriented on hit
                moves.QuickReload(user): 400,  # passive: faster reload — addresses the crossbow's primary weakness, worth the investment
                moves.MarksmanEye(user): 250,  # passive: accuracy at range
            },
            "Polearm": {
                moves.OverheadSmash(user): 250,  # heavy vertical strike, high recoil — stronger opener, priced above basic area attacks
                moves.Sweep(user): 300,  # horizontal arc, all enemies in frontal range
                moves.BullCharge(user): 350,  # aggressive charge
                moves.BracePosition(user): 500,  # defensive polearm stance (Parrying state)
                moves.HalberdSpin(user): 700,  # full 360° spin at polearm range
                moves.ReachMastery(user): 300,  # passive: range extension
            },
        }
