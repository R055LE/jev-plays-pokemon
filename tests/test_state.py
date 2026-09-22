import json

from jev_plays_pokemon.state import GameState, PartyMember, read_game_state


class FakeEmulator:
    def __init__(self, memory, party_data, money_value, dialogue):
        self._memory = memory
        self._party_data = party_data
        self._money = money_value
        self._dialogue = dialogue

    def read_byte(self, address):
        return self._memory[address]

    def party(self):
        return self._party_data

    def money(self):
        return self._money

    def dialogue_active(self):
        return self._dialogue


def test_read_game_state_parses_position_map_and_badges():
    emulator = FakeEmulator(
        memory={0xD35E: 12, 0xD361: 5, 0xD362: 9, 0xD356: 0b00000101},
        party_data=[{"species": "CHARMANDER", "level": 8, "hp": 19, "max_hp": 19, "status": "OK"}],
        money_value=1500,
        dialogue=False,
    )

    state = read_game_state(emulator)

    assert state.map_id == 12
    assert state.player_x == 9
    assert state.player_y == 5
    assert state.badges == ["Boulder", "Thunder"]
    assert state.money == 1500
    assert state.dialogue_active is False
    assert state.party == [PartyMember(species="CHARMANDER", level=8, hp=19, max_hp=19, status="OK")]


def test_read_game_state_with_no_badges_and_dialogue_active():
    emulator = FakeEmulator(
        memory={0xD35E: 1, 0xD361: 0, 0xD362: 0, 0xD356: 0},
        party_data=[],
        money_value=0,
        dialogue=True,
    )

    state = read_game_state(emulator)

    assert state.badges == []
    assert state.party == []
    assert state.dialogue_active is True


def test_game_state_to_dict_is_json_serializable():
    state = GameState(
        map_id=1,
        player_x=2,
        player_y=3,
        party=[PartyMember(species="PIKACHU", level=5, hp=10, max_hp=12, status="OK")],
        badges=[],
        money=0,
        dialogue_active=True,
    )

    payload = state.to_dict()
    json.dumps(payload)  # must not raise

    assert payload["map_id"] == 1
    assert payload["party"][0]["species"] == "PIKACHU"
