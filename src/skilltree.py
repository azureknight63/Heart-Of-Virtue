import moves

class Skilltree:
    def __init__(self, user):
        '''
        List all learnable skills. When the player gains exp from a specific action, like attacking with a weapon, that exp goes into a pool.
        When the player has earned enough exp to learn a skill, he may "buy" the skill from the skill menu.
        Skills are represented in this format: "Skill_name": exp_required
        '''
        self.subtypes = {  # todo add more skills
            "Basic": {  # Basic class skills always gain exp along with the player and don't need to be called out in an ability
                moves.Dodge(user): 100,
                moves.TacticalPositioning(user): 1000
                #moves.AggressiveStance(user): 150  # Shift to an aggressive fighting stance; ++str, spd; -fin, end
                #moves.DefensiveStance(user): 150  # ++fin, end, -str, fth, cha
            },
            "Dagger": {
                moves.Slash(user): 15,  # 150
                moves.QuietMovement(user): 350
            },
            "Bow": {
                #moves.Hawkeye(user): 100,  # Focus on surroundings; increases base accuracy for a duration (adds a status)
                moves.TacticalPositioning(user): 400
            },
            "Unarmed": {
                #moves.Jab(user): 100  # quick unarmed attack that causes little damage but has a very low fatigue cost and zero cooldown
                #moves.Kick(user): 150  # quick leg attack; more damaging than a jab with a higher fatigue cost and small cooldown
                #moves.Haymaker(user): 250  # strong unarmed attack that causes significant damage but has a high fatigue and cooldown cost, slower cast
                #moves.Trip(user): 250  # sweeping leg attack with a 25% chance to trip humanoid opponents, stunning them
                #moves.Throw(user): 250  # unarmed; attempt to toss an opponent, causing moderate damage and increasing their distance from the player
                #moves.Combo(user): 250  # arrange a succession of unarmed attacks against a target. Each successful hit boosts Heat. A miss or parry breaks the combo.
                #moves.Disarm(user): 500  # attempt to disarm the target, causing it to drop its weapon to the ground
                #moves.Takedown(user): 500  # instead of a normal parry, this will throw your attacker to the ground, stunning them
                #moves.Callous(user): 250  # while unarmed, glancing blows cause half their normal damage to the player
                #moves.Footwork(user): 500  # while unarmed, 15% increased chance for an incoming hit to be a glancing blow
                #moves.Attentive(user): 250  # while using an unarmed attack, you have a 20% chance to follow it up with an immediate Jab
                #moves.Spinkick(user): 350  # hit all enemies within 5 distance, knocking them back and causing light damage
            },
            "Scythe": {
                #moves.PommelStrike(user): 125  # Quick strike using the pommel of the weapon
                #moves.Reap(user): 250  # sweeping poewr attack that hits multiple enemies at slightly greater than normal range and with a long windup and cooldown

            }
        }
