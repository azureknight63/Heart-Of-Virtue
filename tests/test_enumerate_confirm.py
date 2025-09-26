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

    # New behavior: menu appears; select option 2 to take Battleaxe
    responses = ['2']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))

    result = functions.enumerate_for_interactions(subjects, player, args_list, action_input)

    assert result is True
    assert calls == ['Battleaxe']
    assert t1.taken is False and t2.taken is True


def test_enumerate_for_interactions_single_token_menu(monkeypatch):
    calls = []

    class MockThing:
        def __init__(self, name):
            self.name = name
            self.idle_message = ''
            self.description = ''
            self.announce = ''
            self.interactions = ['drop']
            self.keywords = []
            self.hidden = False
            self.dropped = False

        def drop(self, player=None):
            self.dropped = True
            calls.append(self.name)

    player = object()
    a = MockThing('Iron Sword')
    b = MockThing('Iron Shield')
    subjects = [a, b]
    args_list = ['drop']  # single token ambiguous
    action_input = 'drop'

    # Select first item (Iron Sword)
    responses = ['1']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))

    result = functions.enumerate_for_interactions(subjects, player, args_list, action_input)

    assert result is True
    assert calls == ['Iron Sword']
    assert a.dropped is True and b.dropped is False
