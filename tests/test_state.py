import json

from jev_plays_pokemon.state import GameState, PartyMember, read_game_state


class FakeEmulator:
    def __init__(self, memory, dialogue):
        self._memory = memory
        self._dialogue = dialogue

    def read_byte(self, address):
        return self._memory[address]

    def dialogue_active(self):
        return self._dialogue


def test_read_game_state_parses_position_map_badges_party_and_money():
    emulator = FakeEmulator(
        memory={
            0xD35E: 12, 0xD361: 5, 0xD362: 9, 0xD356: 0b00000101,
            0xD163: 1,  # party count
            0xD16B: 0xB0,  # species: CHARMANDER
            0xD16C: 0, 0xD16D: 19,  # hp = 19
            0xD16F: 0,  # status: OK
            0xD18C: 8,  # level
            0xD18D: 0, 0xD18E: 19,  # max_hp = 19
            0xD347: 0x00, 0xD348: 0x15, 0xD349: 0x00,  # money = 1500 (BCD)
        },
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


def test_read_game_state_with_no_badges_empty_party_and_dialogue_active():
    emulator = FakeEmulator(
        memory={
            0xD35E: 1, 0xD361: 0, 0xD362: 0, 0xD356: 0,
            0xD163: 0,  # party count
            0xD347: 0, 0xD348: 0, 0xD349: 0,  # money = 0
        },
        dialogue=True,
    )

    state = read_game_state(emulator)

    assert state.badges == []
    assert state.party == []
    assert state.money == 0
    assert state.dialogue_active is True


def test_read_game_state_decodes_status_conditions():
    base_memory = {
        0xD35E: 1, 0xD361: 0, 0xD362: 0, 0xD356: 0,
        0xD163: 1,
        0xD16B: 0x99,  # species: BULBASAUR
        0xD16C: 0, 0xD16D: 10,
        0xD18C: 5,
        0xD18D: 0, 0xD18E: 10,
        0xD347: 0, 0xD348: 0, 0xD349: 0,
    }

    poisoned = {**base_memory, 0xD16F: 0b0000_1000}
    state = read_game_state(FakeEmulator(memory=poisoned, dialogue=False))
    assert state.party[0].status == "POISONED"

    asleep = {**base_memory, 0xD16F: 0b0000_0011}
    state = read_game_state(FakeEmulator(memory=asleep, dialogue=False))
    assert state.party[0].status == "ASLEEP"


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
