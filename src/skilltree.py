import moves

class Skilltree:
    def __init__(self, user):
        '''
        List all learnable skills. When the player gains exp from a specific action, like attacking with a weapon, that exp goes into a pool.
        When the player has earned enough exp to learn a skill, he may "buy" the skill from the skill menu.
        Skills are represented in this format: "Skill_name": exp_required
        '''
        self.subtypes = {
            "Basic": {  # Basic class skills always gain exp along with the player and don't need to be called out in an ability
                moves.Dodge(user): 100,
                moves.TacticalPositioning(user): 1000
            },
            "Dagger": {
                moves.Slash(user): 150
            },
            "Bow": {
                #moves.Hawkeye(user): 100,  # Focus on surroundings; increases base accuracy for a duration (adds a status)
                moves.TacticalPositioning(user): 400
            }
        }
