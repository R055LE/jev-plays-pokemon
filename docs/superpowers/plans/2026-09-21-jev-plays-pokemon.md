# Jev Plays Pokemon Blue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get Jev (TypeSafe AI's System One model) playing Pokemon Blue end to end — read game state from RAM, ask Jev what button to press, apply it, log the turn — watchable live via a PyBoy window.

**Architecture:** Four independently-testable modules (`emulator.py`, `state.py`, `decision.py`, `main.py`) as specified in the design doc. `state.py` and `decision.py` are pure state-in/value-out and unit tested with fakes; `emulator.py` and `main.py` touch real PyBoy/the network and are verified by manual run, not automated tests.

**Tech Stack:** Python 3.10+, PyBoy (Game Boy emulator), `typesafe-sdk` (Jev API client), pytest.

**Spec:** `docs/superpowers/specs/2026-09-21-jev-plays-pokemon-design.md`

## Global Constraints

- Out of scope for v1: narrator/commentary, streaming/web viewer, save/resume between runs, automatic stuck-state recovery, macro/compound actions.
- ROM file and `TYPESAFE_API_KEY` are supplied by the user via a local file / environment variable, never committed. `.gitignore` already covers `*.gb`, `*.gbc`, `*.sav`, `*.state`, `.env`.
- `GameState` does **not** include player facing direction — no v1 source independently verified that address, so it's cut rather than guessed (see spec deviation note below).
- Jev's action schema is two `Choice` questions per turn, batched into one `system_one()` call: `button` (UP/DOWN/LEFT/RIGHT/A/B/START/SELECT) and `hold` (TAP/HOLD/LONG, mapped to 2/8/20 frames respectively) — not a raw `hold_frames` int, since `Choice` is the SDK primitive with a confirmed contract.
- Stuck detection: flag when `(map_id, player_x, player_y)` is unchanged for 50 consecutive turns (tunable constant), logged only — no auto-recovery.
- Jev API failure handling: one retry, then fall back to a `WAIT` action (`button="WAIT"`, `hold_frames=0`) that advances the emulator one frame without pressing anything. `WAIT` is never offered to Jev as a choice — it's the harness's own fallback.

**Spec deviations (discovered during planning, not scope changes):**
- `state.py` uses PyBoy's built-in Pokemon Gen 1 `game_wrapper` for party/money instead of hand-parsing WRAM party structs — PyBoy ships this parsing already; hand-rolling it would just be a worse copy of code that already exists in our own dependency.
- Automated tests for `state.py`/`decision.py` use hand-written fake objects instead of captured PyBoy save-state fixtures, since a save-state fixture requires a ROM this repo will never contain (ROMs aren't distributed with the project). Fakes make the tests portable and require no ROM to run.

---

### Task 1: Project scaffolding + `emulator.py`

**Files:**
- Create: `pyproject.toml`
- Create: `src/jev_plays_pokemon/__init__.py`
- Create: `src/jev_plays_pokemon/emulator.py`

**Interfaces:**
- Produces: `class Emulator` with methods `__init__(self, rom_path: str) -> None`, `press(self, button: str, hold_frames: int) -> None`, `wait(self, frames: int = 1) -> None`, `read_byte(self, address: int) -> int`, `party(self) -> list[dict]`, `money(self) -> int`, `dialogue_active(self) -> bool`, `stop(self) -> None`. `button` is one of `"UP"`, `"DOWN"`, `"LEFT"`, `"RIGHT"`, `"A"`, `"B"`, `"START"`, `"SELECT"`.

This module has no logic of its own to unit test without a real ROM — it's a thin pass-through to PyBoy. It's verified manually in Task 4's end-to-end check, not by automated tests here.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "jev-plays-pokemon"
version = "0.1.0"
description = "Jev (TypeSafe AI's System One model) plays Pokemon Blue"
requires-python = ">=3.10"
dependencies = [
    "pyboy>=2.0.0",
    "typesafe-sdk",
]

[project.optional-dependencies]
dev = ["pytest"]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create the package skeleton**

```bash
mkdir -p src/jev_plays_pokemon
touch src/jev_plays_pokemon/__init__.py
```

- [ ] **Step 3: Install the project in editable mode**

Run: `pip install -e ".[dev]"`
Expected: installs cleanly, `pyboy` and `typesafe-sdk` resolve (network access to PyPI required).

- [ ] **Step 4: Write `emulator.py`**

```python
from pyboy import PyBoy

_BUTTON_TO_PYBOY_NAME = {
    "UP": "up",
    "DOWN": "down",
    "LEFT": "left",
    "RIGHT": "right",
    "A": "a",
    "B": "b",
    "START": "start",
    "SELECT": "select",
}

_DIALOGUE_TILE_X = 18
_DIALOGUE_TILE_Y = 16
_DIALOGUE_ARROW_TILE_ID = 238


class Emulator:
    def __init__(self, rom_path: str) -> None:
        self._pyboy = PyBoy(rom_path, window="SDL2")

    def press(self, button: str, hold_frames: int) -> None:
        self._pyboy.button(_BUTTON_TO_PYBOY_NAME[button], delay=hold_frames)
        self._pyboy.tick(hold_frames, True)

    def wait(self, frames: int = 1) -> None:
        self._pyboy.tick(frames, True)

    def read_byte(self, address: int) -> int:
        return self._pyboy.memory[address]

    def party(self) -> list[dict]:
        return self._pyboy.game_wrapper.party

    def money(self) -> int:
        return self._pyboy.game_wrapper.money

    def dialogue_active(self) -> bool:
        return self._pyboy.tilemap_window[_DIALOGUE_TILE_X, _DIALOGUE_TILE_Y] == _DIALOGUE_ARROW_TILE_ID

    def stop(self) -> None:
        self._pyboy.stop()
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/jev_plays_pokemon/__init__.py src/jev_plays_pokemon/emulator.py
git commit -m "Add project scaffolding and PyBoy emulator wrapper"
```

---

### Task 2: `state.py`

**Files:**
- Create: `src/jev_plays_pokemon/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: an object matching `Emulator`'s duck-typed interface from Task 1 — `read_byte(address: int) -> int`, `party() -> list[dict]` (each dict has keys `species: str`, `level: int`, `hp: int`, `max_hp: int`, `status: str`), `money() -> int`, `dialogue_active() -> bool`.
- Produces: `@dataclass PartyMember(species: str, level: int, hp: int, max_hp: int, status: str)`, `@dataclass GameState(map_id: int, player_x: int, player_y: int, party: list[PartyMember], badges: list[str], money: int, dialogue_active: bool)` with method `to_dict(self) -> dict`, and function `read_game_state(emulator) -> GameState`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_state.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jev_plays_pokemon.state'`

- [ ] **Step 3: Write `state.py`**

```python
from dataclasses import asdict, dataclass

_MAP_ID_ADDRESS = 0xD35E
_PLAYER_Y_ADDRESS = 0xD361
_PLAYER_X_ADDRESS = 0xD362
_BADGES_ADDRESS = 0xD356

_BADGE_NAMES = [
    "Boulder", "Cascade", "Thunder", "Rainbow",
    "Soul", "Marsh", "Volcano", "Earth",
]


@dataclass
class PartyMember:
    species: str
    level: int
    hp: int
    max_hp: int
    status: str


@dataclass
class GameState:
    map_id: int
    player_x: int
    player_y: int
    party: list[PartyMember]
    badges: list[str]
    money: int
    dialogue_active: bool

    def to_dict(self) -> dict:
        return asdict(self)


def read_game_state(emulator) -> GameState:
    badge_byte = emulator.read_byte(_BADGES_ADDRESS)
    badges = [name for i, name in enumerate(_BADGE_NAMES) if badge_byte & (1 << i)]

    party = [
        PartyMember(
            species=member["species"],
            level=member["level"],
            hp=member["hp"],
            max_hp=member["max_hp"],
            status=member["status"],
        )
        for member in emulator.party()
    ]

    return GameState(
        map_id=emulator.read_byte(_MAP_ID_ADDRESS),
        player_x=emulator.read_byte(_PLAYER_X_ADDRESS),
        player_y=emulator.read_byte(_PLAYER_Y_ADDRESS),
        party=party,
        badges=badges,
        money=emulator.money(),
        dialogue_active=emulator.dialogue_active(),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/jev_plays_pokemon/state.py tests/test_state.py
git commit -m "Add GameState parsing from emulator RAM/wrapper reads"
```

---

### Task 3: `decision.py`

**Files:**
- Create: `src/jev_plays_pokemon/decision.py`
- Test: `tests/test_decision.py`

**Interfaces:**
- Consumes: `GameState` from Task 2 (specifically its `to_dict()` method); a duck-typed client object with `system_one(state: dict, questions: dict) -> object`, where the returned object has `.choices: dict[str, object]` and each choice object has `.choice: str` and `.confidence: float`. The real client is `typesafe_sdk.TypeSafeClient` and questions use `typesafe_sdk.Choice(instructions: str, criteria: dict[str, str])`.
- Produces: `@dataclass Action(button: str, hold_frames: int, confidence: float)` and `class DecisionClient` with `__init__(self, client=None, retry_backoff_seconds: float = 1.0)` and `decide(self, state: GameState) -> Action`. `button` is one of the eight game buttons from Task 1, or `"WAIT"` on API failure.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_decision.py`:

```python
from dataclasses import dataclass

from jev_plays_pokemon.decision import Action, DecisionClient
from jev_plays_pokemon.state import GameState


def make_state() -> GameState:
    return GameState(
        map_id=1, player_x=1, player_y=1,
        party=[], badges=[], money=0, dialogue_active=False,
    )


@dataclass
class FakeChoiceAnswer:
    choice: str
    confidence: float


class FakeResponse:
    def __init__(self, choices):
        self.choices = choices


class FakeClient:
    def __init__(self, response=None, fail_times=0):
        self._response = response
        self._fail_times = fail_times
        self.calls = 0

    def system_one(self, state, questions):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise RuntimeError("simulated API failure")
        return self._response


def test_decide_returns_action_from_jev_response():
    response = FakeResponse({
        "button": FakeChoiceAnswer(choice="A", confidence=0.92),
        "hold": FakeChoiceAnswer(choice="TAP", confidence=0.8),
    })
    client = DecisionClient(client=FakeClient(response=response), retry_backoff_seconds=0)

    action = client.decide(make_state())

    assert action == Action(button="A", hold_frames=2, confidence=0.92)


def test_decide_succeeds_after_one_retry():
    response = FakeResponse({
        "button": FakeChoiceAnswer(choice="UP", confidence=0.7),
        "hold": FakeChoiceAnswer(choice="HOLD", confidence=0.6),
    })
    client = DecisionClient(client=FakeClient(response=response, fail_times=1), retry_backoff_seconds=0)

    action = client.decide(make_state())

    assert action == Action(button="UP", hold_frames=8, confidence=0.7)


def test_decide_falls_back_to_wait_after_retry_exhausted():
    client = DecisionClient(client=FakeClient(fail_times=99), retry_backoff_seconds=0)

    action = client.decide(make_state())

    assert action == Action(button="WAIT", hold_frames=0, confidence=0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_decision.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jev_plays_pokemon.decision'`

- [ ] **Step 3: Write `decision.py`**

```python
import time
from dataclasses import dataclass

from typesafe_sdk import Choice, TypeSafeClient

_BUTTON_CRITERIA = {
    "UP": "Move the player or menu cursor up",
    "DOWN": "Move the player or menu cursor down",
    "LEFT": "Move the player or menu cursor left",
    "RIGHT": "Move the player or menu cursor right",
    "A": "Confirm the highlighted option, advance dialogue, or interact with what's in front of the player",
    "B": "Cancel or back out of a menu, or speed up dialogue",
    "START": "Open the pause menu",
    "SELECT": "Open the select-item shortcut menu",
}

_HOLD_CRITERIA = {
    "TAP": "A quick single press, e.g. advancing one line of dialogue or moving one step",
    "HOLD": "A medium hold, e.g. taking several steps in one direction",
    "LONG": "A long hold, e.g. crossing most of a room in one direction",
}

_HOLD_FRAMES = {"TAP": 2, "HOLD": 8, "LONG": 20}


@dataclass
class Action:
    button: str
    hold_frames: int
    confidence: float


class DecisionClient:
    def __init__(self, client=None, retry_backoff_seconds: float = 1.0) -> None:
        self._client = client or TypeSafeClient()
        self._retry_backoff_seconds = retry_backoff_seconds

    def decide(self, state) -> Action:
        for attempt in range(2):
            try:
                return self._ask_jev(state)
            except Exception:
                if attempt == 0:
                    time.sleep(self._retry_backoff_seconds)
        return Action(button="WAIT", hold_frames=0, confidence=0.0)

    def _ask_jev(self, state) -> Action:
        result = self._client.system_one(
            state.to_dict(),
            {
                "button": Choice(
                    instructions="Which single Game Boy button should be pressed next, given the current game state?",
                    criteria=_BUTTON_CRITERIA,
                ),
                "hold": Choice(
                    instructions="How long should the button be held?",
                    criteria=_HOLD_CRITERIA,
                ),
            },
        )
        button_answer = result.choices["button"]
        hold_answer = result.choices["hold"]
        return Action(
            button=button_answer.choice,
            hold_frames=_HOLD_FRAMES[hold_answer.choice],
            confidence=button_answer.confidence,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_decision.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/jev_plays_pokemon/decision.py tests/test_decision.py
git commit -m "Add Jev decision client with retry-then-WAIT fallback"
```

---

### Task 4: `main.py`, README, and env template

**Files:**
- Create: `src/jev_plays_pokemon/main.py`
- Create: `README.md`
- Create: `.env.example`

**Interfaces:**
- Consumes: `Emulator` (Task 1), `read_game_state` (Task 2), `DecisionClient`/`Action` (Task 3).
- Produces: `run(rom_path: str, log_path: str) -> None` and a `main()` CLI entry point.

No automated test for this task — it's the real PyBoy + real Jev API loop, verified manually per Step 4 below.

- [ ] **Step 1: Write `main.py`**

```python
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from .decision import DecisionClient
from .emulator import Emulator
from .state import read_game_state

_STUCK_THRESHOLD = 50


def run(rom_path: str, log_path: str) -> None:
    emulator = Emulator(rom_path)
    decision_client = DecisionClient()
    last_position = None
    stuck_count = 0
    turn = 0
    log_file = Path(log_path).open("a")
    try:
        while True:
            turn += 1
            state = read_game_state(emulator)
            position = (state.map_id, state.player_x, state.player_y)
            stuck_count = stuck_count + 1 if position == last_position else 0
            last_position = position

            action = decision_client.decide(state)

            if action.button == "WAIT":
                emulator.wait(max(action.hold_frames, 1))
            else:
                emulator.press(action.button, action.hold_frames)

            record = {
                "turn": turn,
                "timestamp": time.time(),
                "state": state.to_dict(),
                "action": asdict(action),
                "stuck": stuck_count >= _STUCK_THRESHOLD,
            }
            log_file.write(json.dumps(record) + "\n")
            log_file.flush()
    except KeyboardInterrupt:
        pass
    finally:
        log_file.close()
        emulator.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Jev plays Pokemon Blue")
    parser.add_argument("--rom", required=True, help="Path to a legally-owned Pokemon Blue ROM file")
    parser.add_argument("--log", default="turns.jsonl", help="Path to the turn-by-turn JSON lines log")
    args = parser.parse_args()
    run(args.rom, args.log)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `.env.example`**

```
TYPESAFE_API_KEY=
```

- [ ] **Step 3: Write `README.md`**

```markdown
# Jev Plays Pokemon Blue

Jev (TypeSafe AI's System One model) plays Pokemon Blue through a
PyBoy-driven harness. See `docs/superpowers/specs/2026-09-21-jev-plays-pokemon-design.md`
for the design and `docs/superpowers/plans/2026-09-21-jev-plays-pokemon.md`
for the implementation plan.

## Setup

1. `pip install -e ".[dev]"`
2. Set `TYPESAFE_API_KEY` in your environment (or a local `.env`, gitignored).
3. Supply your own legally-owned Pokemon Blue ROM file. It is never
   committed to this repo.

## Running

    python -m jev_plays_pokemon.main --rom /path/to/pokemon_blue.gb --log turns.jsonl

Runs until you Ctrl-C it. Each run starts from the beginning of the game —
there's no save/resume in v1.

## Testing

    pytest
```

- [ ] **Step 4: Manual end-to-end verification**

Run: `python -m jev_plays_pokemon.main --rom /path/to/your/pokemon_blue.gb --log turns.jsonl`

Expected, watching the PyBoy window on barnabas's desktop:
- A window opens showing Pokemon Blue booting.
- Within a few turns, `turns.jsonl` has one JSON line per turn with `turn`, `timestamp`, `state`, `action`, `stuck` keys.
- Pressing Ctrl-C in the terminal stops the loop cleanly (no traceback) and closes the window.

- [ ] **Step 5: Commit**

```bash
git add src/jev_plays_pokemon/main.py README.md .env.example
git commit -m "Add main play loop, README, and env template"
```
