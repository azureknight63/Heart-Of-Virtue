import moves

class Skilltree:
    def __init__(self, user):
        '''
        List all learnable skills. When the player gains exp from a specific action, like attacking with a weapon, iterate over these objects to see if a
        skill falls within an acceptable category. If so, add exp to that skill. If a skill's gained exp exceeds the requirement, learn the skill.
        Skills are represented in this format: "Skill_name": [exp_required, exp_earned]
        '''
        self.subtypes = {
            "Basic": {  # Basic class skills always gain exp along with the player and don't need to be called out in an ability
                moves.Dodge(user): [100, 0],
                moves.TacticalPositioning(user): [1000, 0]
            },
            "Dagger": {
                moves.Slash(user): [150,0]
            }
        }
