import src.functions as functions


def test_enumerate_for_interactions_confirmation(monkeypatch):
    calls = []

    class MockThing:
        def __init__(self, name):
            self.name = name
            self.idle_message = ''
            self.description = ''
            self.announce = ''
            self.interactions = ['take']
            self.keywords = []
            self.hidden = False
            self.taken = False

        def take(self, player=None):
            self.taken = True
            calls.append(self.name)

    player = object()
    t1 = MockThing('Pickaxe')
    t2 = MockThing('Battleaxe')
    subjects = [t1, t2]
    args_list = ['take', 'axe']
    action_input = 'axe'

    # Simulate user input: first 'n' (decline), then 'y' (confirm)
    responses = ['n', 'y']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))

    result = functions.enumerate_for_interactions(subjects, player, args_list, action_input)

    assert result is True
    assert calls == ['Battleaxe']
    assert t1.taken is False and t2.taken is True

