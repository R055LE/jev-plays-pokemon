import json

import pytest

from jev_plays_pokemon.decision import Action
from jev_plays_pokemon.main import main, run


class FakeEmulator:
    def __init__(self):
        self.presses = []
        self.waits = 0
        self.stopped = False

    def read_byte(self, address):
        return 0

    def dialogue_active(self):
        return False

    def press(self, button, tiles):
        self.presses.append((button, tiles))

    def wait(self):
        self.waits += 1

    def tilemap_hash(self):
        return 42  # never changes: stuck from turn 2 on

    def stop(self):
        self.stopped = True


class FakeDecisionClient:
    def __init__(self, action):
        self._action = action
        self.excluded_seen = []

    def decide(self, state, excluded=frozenset()):
        self.excluded_seen.append(excluded)
        return self._action


def read_log(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_max_turns_stops_the_loop(tmp_path):
    emulator = FakeEmulator()
    log = tmp_path / "turns.jsonl"

    run("rom.gb", str(log), max_turns=3, emulator=emulator,
        decision_client=FakeDecisionClient(Action("A", None, 0.9)))

    assert len(read_log(log)) == 3
    assert emulator.presses == [("A", None)] * 3
    assert emulator.stopped


def test_max_turns_stops_a_loop_of_wait_fallbacks(tmp_path):
    emulator = FakeEmulator()
    log = tmp_path / "turns.jsonl"

    run("rom.gb", str(log), max_turns=5, emulator=emulator,
        decision_client=FakeDecisionClient(Action("WAIT", None, 0.0)))

    assert emulator.waits == 5
    assert emulator.presses == []


def test_stuck_button_is_excluded_from_the_next_decision(tmp_path):
    decisions = FakeDecisionClient(Action("A", None, 0.9))
    log = tmp_path / "turns.jsonl"

    run("rom.gb", str(log), max_turns=12, emulator=FakeEmulator(), decision_client=decisions)

    # Turn 1 is progress, turns 2-11 are the first no-progress stretch.
    assert decisions.excluded_seen[10] == frozenset()
    assert decisions.excluded_seen[11] == frozenset({"A"})
    last = read_log(log)[-1]
    assert last["turns_since_progress"] == 11
    assert last["excluded_buttons"] == ["A"]
    assert last["action"] == {"button": "A", "tiles": None, "confidence": 0.9}
    assert "stuck" not in last


def test_speed_must_be_a_whole_number(monkeypatch):
    # PyBoy stores emulation speed as an int, so 0.5 would silently mean uncapped.
    monkeypatch.setattr("sys.argv", ["main", "--rom", "rom.gb", "--speed", "0.5"])
    with pytest.raises(SystemExit):
        main()
