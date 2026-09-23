# Stuck Recovery and Pacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Jev looping forever on one button by pacing turns in real game time and removing buttons that haven't produced progress from Jev's choices.

**Architecture:** A pure `ProgressTracker` decides progress from a tilemap hash and keeps the excluded-button set. `DecisionClient.decide` takes that set and leaves those buttons out of the `button` Choice. The emulator holds directions for whole tiles and ticks settle frames after every press. `main.run` wires it together and adds `--max-turns` and `--speed`.

**Tech Stack:** Python 3.12, PyBoy 2.7, typesafe-sdk 0.7.1, pytest.

**Spec:** `docs/superpowers/specs/2026-09-22-stuck-recovery-design.md`

## Global Constraints

- Only Jev chooses buttons. The harness never presses a button Jev didn't pick. `WAIT` stays harness-only (API-failure fallback).
- Jev's state dict does not change. `turns_since_progress` and exclusion data go in the log only.
- `SETTLE_FRAMES = 20`, `FRAMES_PER_TILE = 16`, `BUTTON_PRESS_FRAMES = 4`, `PROGRESS_WINDOW = 50`, `EXCLUSION_STRETCH = 10`.
- `length` Choice: `ONE` / `FEW` / `MANY` = 1 / 3 / 6 tiles.
- No new dependencies.
- Run tests from the worktree root with the main checkout's venv:
  `PYTHONPATH=src /home/ross/code/github/R055LE/jev-plays-pokemon/.venv/bin/python -m pytest -q`
  (shorthand below: `$PYTEST`).
- Commit messages: short imperative subject, no prefix tags.

## Review Focus

- WAIT turns during a stuck stretch: they count toward `turns_since_progress` but add nothing to the excluded set. Pinned in Task 1.
- A screen seen more than 50 turns ago counts as progress again (walking back into a room later is progress). Pinned in Task 1.
- The very first turn is progress (nothing seen yet), so exclusion can't start on turn 1. Pinned in Task 1.
- All 8 buttons excluded resets to empty rather than sending Jev an empty Choice. Pinned in Task 1.
- `--max-turns` stops the loop even when every turn is a WAIT fallback (API down), which is the case where a runaway costs nothing but still never ends. Pinned in Task 4.

---

### Task 1: ProgressTracker

**Files:**
- Create: `src/jev_plays_pokemon/progress.py`
- Test: `tests/test_progress.py`

**Interfaces:**
- Produces:
  - `BUTTONS: tuple[str, ...]` = `("UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT")`
  - `class ProgressTracker(window: int = 50, stretch: int = 10)`
    - `record(screen_hash: int, button: str) -> None`, called once per turn after the press
    - `turns_since_progress: int`
    - `excluded: frozenset[str]`

- [ ] **Step 1: Write the failing tests**

`tests/test_progress.py`:

```python
from jev_plays_pokemon.progress import BUTTONS, ProgressTracker


def test_first_turn_is_progress():
    tracker = ProgressTracker()
    tracker.record(1, "A")
    assert tracker.turns_since_progress == 0
    assert tracker.excluded == frozenset()


def test_repeat_screen_inside_window_is_not_progress():
    tracker = ProgressTracker()
    tracker.record(1, "A")
    tracker.record(2, "A")
    tracker.record(1, "A")
    assert tracker.turns_since_progress == 1


def test_screen_older_than_window_counts_as_progress_again():
    tracker = ProgressTracker(window=3)
    for screen in (1, 2, 3, 4):
        tracker.record(screen, "A")
    tracker.record(1, "A")
    assert tracker.turns_since_progress == 0


def test_buttons_pressed_in_stretch_are_excluded_after_stretch():
    tracker = ProgressTracker(stretch=10)
    tracker.record(1, "A")
    for _ in range(9):
        tracker.record(1, "A")
    assert tracker.excluded == frozenset()
    tracker.record(1, "B")
    assert tracker.turns_since_progress == 10
    assert tracker.excluded == frozenset({"A", "B"})


def test_each_further_stretch_adds_its_buttons():
    tracker = ProgressTracker(stretch=10)
    tracker.record(1, "A")
    for _ in range(10):
        tracker.record(1, "A")
    for _ in range(10):
        tracker.record(1, "UP")
    assert tracker.excluded == frozenset({"A", "UP"})


def test_progress_clears_exclusions():
    tracker = ProgressTracker(stretch=10)
    tracker.record(1, "A")
    for _ in range(10):
        tracker.record(1, "A")
    tracker.record(2, "UP")
    assert tracker.turns_since_progress == 0
    assert tracker.excluded == frozenset()


def test_wait_counts_as_no_progress_but_excludes_nothing():
    tracker = ProgressTracker(stretch=10)
    tracker.record(1, "A")
    for _ in range(10):
        tracker.record(1, "WAIT")
    assert tracker.turns_since_progress == 10
    assert tracker.excluded == frozenset()


def test_excluding_every_button_resets_to_empty():
    tracker = ProgressTracker(stretch=1)
    tracker.record(1, "A")
    for button in BUTTONS[:-1]:
        tracker.record(1, button)
    assert tracker.excluded == frozenset(BUTTONS[:-1])
    tracker.record(1, BUTTONS[-1])
    assert tracker.excluded == frozenset()
```

- [ ] **Step 2: Run to verify they fail**

Run: `$PYTEST tests/test_progress.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'jev_plays_pokemon.progress'`

- [ ] **Step 3: Implement**

`src/jev_plays_pokemon/progress.py`:

```python
from collections import deque

BUTTONS = ("UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT")


class ProgressTracker:
    """Progress means a screen (tilemap hash) not seen in the last `window` turns.

    Jev is deterministic, so the same state gets the same button forever. After
    each `stretch` turns without progress, the buttons pressed in that stretch
    are excluded from Jev's next choices until something changes.
    """

    def __init__(self, window: int = 50, stretch: int = 10) -> None:
        self._seen = deque(maxlen=window)
        self._stretch = stretch
        self._stretch_buttons: set[str] = set()
        self.turns_since_progress = 0
        self.excluded: frozenset[str] = frozenset()

    def record(self, screen_hash: int, button: str) -> None:
        progressed = screen_hash not in self._seen
        self._seen.append(screen_hash)
        if progressed:
            self.turns_since_progress = 0
            self._stretch_buttons.clear()
            self.excluded = frozenset()
            return

        self.turns_since_progress += 1
        if button in BUTTONS:
            self._stretch_buttons.add(button)
        if self.turns_since_progress % self._stretch == 0:
            excluded = self.excluded | self._stretch_buttons
            self._stretch_buttons.clear()
            self.excluded = frozenset() if len(excluded) == len(BUTTONS) else frozenset(excluded)
```

- [ ] **Step 4: Run to verify they pass**

Run: `$PYTEST tests/test_progress.py`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/jev_plays_pokemon/progress.py tests/test_progress.py
git commit -m "Add progress tracker for stuck detection and button exclusion"
```

---

### Task 2: Decision client takes exclusions and asks for tiles

**Files:**
- Modify: `src/jev_plays_pokemon/decision.py` (whole file)
- Modify: `tests/test_decision.py` (whole file)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `DIRECTIONS: frozenset[str]` = `{"UP", "DOWN", "LEFT", "RIGHT"}`
  - `@dataclass Action(button: str, tiles: int | None, confidence: float)`. `tiles` is set only for direction buttons, `None` otherwise and for WAIT.
  - `DecisionClient.decide(state, excluded: frozenset[str] = frozenset()) -> Action`

- [ ] **Step 1: Rewrite the tests**

`tests/test_decision.py`:

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
    def __init__(self, answers):
        self.answers = answers


class FakeClient:
    def __init__(self, response=None, fail_times=0):
        self._response = response
        self._fail_times = fail_times
        self.calls = 0
        self.last_questions = None

    def system_one(self, state, questions):
        self.calls += 1
        self.last_questions = questions
        if self.calls <= self._fail_times:
            raise RuntimeError("simulated API failure")
        return self._response


def response(button, length, confidence=0.9):
    return FakeResponse({
        "button": FakeChoiceAnswer(choice=button, confidence=confidence),
        "length": FakeChoiceAnswer(choice=length, confidence=0.5),
    })


def test_direction_gets_tiles_from_length():
    client = DecisionClient(client=FakeClient(response=response("UP", "FEW", 0.7)), retry_backoff_seconds=0)

    assert client.decide(make_state()) == Action(button="UP", tiles=3, confidence=0.7)


def test_non_direction_ignores_length():
    client = DecisionClient(client=FakeClient(response=response("A", "MANY", 0.92)), retry_backoff_seconds=0)

    assert client.decide(make_state()) == Action(button="A", tiles=None, confidence=0.92)


def test_excluded_buttons_are_not_offered_to_jev():
    fake = FakeClient(response=response("B", "ONE"))
    client = DecisionClient(client=fake, retry_backoff_seconds=0)

    client.decide(make_state(), excluded=frozenset({"A", "START"}))

    offered = set(fake.last_questions["button"].criteria)
    assert offered == {"UP", "DOWN", "LEFT", "RIGHT", "B", "SELECT"}


def test_no_exclusions_offers_every_button():
    fake = FakeClient(response=response("A", "ONE"))
    client = DecisionClient(client=fake, retry_backoff_seconds=0)

    client.decide(make_state())

    assert len(fake.last_questions["button"].criteria) == 8


def test_decide_succeeds_after_one_retry():
    client = DecisionClient(client=FakeClient(response=response("LEFT", "ONE", 0.7), fail_times=1), retry_backoff_seconds=0)

    assert client.decide(make_state()) == Action(button="LEFT", tiles=1, confidence=0.7)


def test_decide_falls_back_to_wait_after_retry_exhausted():
    client = DecisionClient(client=FakeClient(fail_times=99), retry_backoff_seconds=0)

    assert client.decide(make_state()) == Action(button="WAIT", tiles=None, confidence=0.0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `$PYTEST tests/test_decision.py`
Expected: FAIL (`TypeError` on `Action(... tiles=...)` / `decide()` unexpected keyword `excluded`)

- [ ] **Step 3: Implement**

`src/jev_plays_pokemon/decision.py`:

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

_LENGTH_CRITERIA = {
    "ONE": "One tile, or one step of a menu cursor. Use this in menus and dialogue",
    "FEW": "About three tiles in that direction",
    "MANY": "About six tiles in that direction, e.g. crossing most of a room",
}

_LENGTH_TILES = {"ONE": 1, "FEW": 3, "MANY": 6}

DIRECTIONS = frozenset({"UP", "DOWN", "LEFT", "RIGHT"})


@dataclass
class Action:
    button: str
    tiles: int | None
    confidence: float


class DecisionClient:
    def __init__(self, client=None, retry_backoff_seconds: float = 1.0) -> None:
        self._client = client or TypeSafeClient()
        self._retry_backoff_seconds = retry_backoff_seconds

    def decide(self, state, excluded: frozenset[str] = frozenset()) -> Action:
        for attempt in range(2):
            try:
                return self._ask_jev(state, excluded)
            except Exception:
                if attempt == 0:
                    time.sleep(self._retry_backoff_seconds)
        return Action(button="WAIT", tiles=None, confidence=0.0)

    def _ask_jev(self, state, excluded: frozenset[str]) -> Action:
        result = self._client.system_one(
            state.to_dict(),
            {
                "button": Choice(
                    instructions="Which single Game Boy button should be pressed next, given the current game state?",
                    criteria={b: text for b, text in _BUTTON_CRITERIA.items() if b not in excluded},
                ),
                "length": Choice(
                    instructions="If the button is a direction, how far should the player move? Ignored for A, B, START and SELECT.",
                    criteria=_LENGTH_CRITERIA,
                ),
            },
        )
        button_answer = result.answers["button"]
        button = button_answer.choice
        tiles = _LENGTH_TILES[result.answers["length"].choice] if button in DIRECTIONS else None
        return Action(button=button, tiles=tiles, confidence=button_answer.confidence)
```

- [ ] **Step 4: Run to verify they pass**

Run: `$PYTEST tests/test_decision.py`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/jev_plays_pokemon/decision.py tests/test_decision.py
git commit -m "Ask Jev for tiles instead of hold time and honor excluded buttons"
```

---

### Task 3: Emulator pacing, tilemap hash, speed

**Files:**
- Modify: `src/jev_plays_pokemon/emulator.py` (whole file)
- Create: `tests/test_emulator.py`

**Interfaces:**
- Consumes: `DIRECTIONS` from `jev_plays_pokemon.decision` (Task 2).
- Produces:
  - `hold_frames(button: str, tiles: int | None) -> int`
  - `Emulator(rom_path: str, speed: float = 1, pyboy=None)`. `pyboy` is for tests; when `None`, construct `PyBoy(rom_path, window="SDL2")`.
  - `Emulator.press(button: str, tiles: int | None) -> None`: press, hold, then settle.
  - `Emulator.wait() -> None`: tick `SETTLE_FRAMES` with no input.
  - `Emulator.tilemap_hash() -> int`
  - `read_byte`, `dialogue_active`, `stop` unchanged.

PyBoy facts (checked against the installed 2.7.0): `button(name, delay=frames)` presses and auto-releases after `delay` frames; `tick(count, render)`; `set_emulation_speed(target_speed)` with 0 = uncapped; `tilemap_background[:, :]` and `tilemap_window[:, :]` return a 32×32 list of lists of tile ids.

- [ ] **Step 1: Write the failing tests**

`tests/test_emulator.py`:

```python
from jev_plays_pokemon.emulator import SETTLE_FRAMES, Emulator, hold_frames


class FakeTileMap:
    def __init__(self, rows):
        self._rows = rows

    def __getitem__(self, xy):
        return [list(r) for r in self._rows]


class FakePyBoy:
    def __init__(self):
        self.calls = []
        self.speed = None
        self.tilemap_background = FakeTileMap([[1, 2], [3, 4]])
        self.tilemap_window = FakeTileMap([[0, 0], [0, 0]])

    def set_emulation_speed(self, speed):
        self.speed = speed

    def button(self, name, delay):
        self.calls.append(("button", name, delay))

    def tick(self, count, render):
        self.calls.append(("tick", count))


def test_direction_holds_sixteen_frames_per_tile():
    assert hold_frames("UP", 1) == 16
    assert hold_frames("LEFT", 6) == 96


def test_non_direction_is_a_short_fixed_press():
    assert hold_frames("A", None) == 4
    assert hold_frames("START", None) == 4


def test_press_holds_then_settles():
    pyboy = FakePyBoy()
    emulator = Emulator("rom.gb", pyboy=pyboy)

    emulator.press("DOWN", 3)

    assert pyboy.calls == [("button", "down", 48), ("tick", 48), ("tick", SETTLE_FRAMES)]


def test_wait_only_settles():
    pyboy = FakePyBoy()
    Emulator("rom.gb", pyboy=pyboy).wait()

    assert pyboy.calls == [("tick", SETTLE_FRAMES)]


def test_speed_is_passed_to_pyboy():
    pyboy = FakePyBoy()
    Emulator("rom.gb", speed=0, pyboy=pyboy)

    assert pyboy.speed == 0


def test_tilemap_hash_changes_with_tilemap_contents():
    pyboy = FakePyBoy()
    emulator = Emulator("rom.gb", pyboy=pyboy)
    before = emulator.tilemap_hash()

    assert emulator.tilemap_hash() == before
    pyboy.tilemap_window = FakeTileMap([[0, 9], [0, 0]])
    assert emulator.tilemap_hash() != before
```

- [ ] **Step 2: Run to verify they fail**

Run: `$PYTEST tests/test_emulator.py`
Expected: FAIL, `ImportError: cannot import name 'SETTLE_FRAMES'`

- [ ] **Step 3: Implement**

`src/jev_plays_pokemon/emulator.py`:

```python
from pyboy import PyBoy

from .decision import DIRECTIONS

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

# A Gen 1 overworld step is about 16 frames. Settle frames let the game react
# before the next state read, so Jev sees the result of its last press.
FRAMES_PER_TILE = 16
BUTTON_PRESS_FRAMES = 4
SETTLE_FRAMES = 20


def hold_frames(button: str, tiles: int | None) -> int:
    if button in DIRECTIONS:
        return FRAMES_PER_TILE * tiles
    return BUTTON_PRESS_FRAMES


class Emulator:
    def __init__(self, rom_path: str, speed: float = 1, pyboy=None) -> None:
        self._pyboy = pyboy or PyBoy(rom_path, window="SDL2")
        self._pyboy.set_emulation_speed(speed)

    def press(self, button: str, tiles: int | None) -> None:
        frames = hold_frames(button, tiles)
        self._pyboy.button(_BUTTON_TO_PYBOY_NAME[button], delay=frames)
        self._pyboy.tick(frames, True)
        self._pyboy.tick(SETTLE_FRAMES, True)

    def wait(self) -> None:
        self._pyboy.tick(SETTLE_FRAMES, True)

    def tilemap_hash(self) -> int:
        # Tilemaps hold tile ids, not tile graphics or sprites, so animated
        # water and walking NPCs shouldn't change this.
        background = tuple(map(tuple, self._pyboy.tilemap_background[:, :]))
        window = tuple(map(tuple, self._pyboy.tilemap_window[:, :]))
        return hash((background, window))

    def read_byte(self, address: int) -> int:
        return self._pyboy.memory[address]

    def dialogue_active(self) -> bool:
        return self._pyboy.tilemap_window[_DIALOGUE_TILE_X, _DIALOGUE_TILE_Y] == _DIALOGUE_ARROW_TILE_ID

    def stop(self) -> None:
        self._pyboy.stop()
```

- [ ] **Step 4: Run to verify they pass**

Run: `$PYTEST tests/test_emulator.py`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/jev_plays_pokemon/emulator.py tests/test_emulator.py
git commit -m "Hold directions per tile, settle after presses, hash tilemaps"
```

---

### Task 4: Wire the loop, add --max-turns and --speed

**Files:**
- Modify: `src/jev_plays_pokemon/main.py` (whole file)
- Create: `tests/test_main.py`
- Modify: `README.md` (Running section)

**Interfaces:**
- Consumes: `ProgressTracker` (Task 1), `DecisionClient.decide(state, excluded)` and `Action(button, tiles, confidence)` (Task 2), `Emulator(rom_path, speed)`, `.press(button, tiles)`, `.wait()`, `.tilemap_hash()` (Task 3).
- Produces: `run(rom_path, log_path, max_turns=None, speed=1, emulator=None, decision_client=None) -> None`. The last two are for tests.

- [ ] **Step 1: Write the failing tests**

`tests/test_main.py`:

```python
import json

from jev_plays_pokemon.decision import Action
from jev_plays_pokemon.main import run


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `$PYTEST tests/test_main.py`
Expected: FAIL, `TypeError: run() got an unexpected keyword argument 'max_turns'`

- [ ] **Step 3: Implement**

`src/jev_plays_pokemon/main.py`:

```python
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from .decision import DecisionClient
from .emulator import Emulator
from .progress import ProgressTracker
from .state import read_game_state


def run(rom_path: str, log_path: str, max_turns: int | None = None, speed: float = 1,
        emulator=None, decision_client=None) -> None:
    emulator = emulator or Emulator(rom_path, speed=speed)
    decision_client = decision_client or DecisionClient()
    tracker = ProgressTracker()
    turn = 0
    log_file = Path(log_path).open("a")
    try:
        while max_turns is None or turn < max_turns:
            turn += 1
            state = read_game_state(emulator)
            excluded = tracker.excluded

            action = decision_client.decide(state, excluded)

            if action.button == "WAIT":
                emulator.wait()
            else:
                emulator.press(action.button, action.tiles)

            tracker.record(emulator.tilemap_hash(), action.button)

            record = {
                "turn": turn,
                "timestamp": time.time(),
                "state": state.to_dict(),
                "action": asdict(action),
                "excluded_buttons": sorted(excluded),
                "turns_since_progress": tracker.turns_since_progress,
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
    parser.add_argument("--max-turns", type=int, default=None, help="Stop after this many turns (default: run until Ctrl-C)")
    parser.add_argument("--speed", type=float, default=1, help="Emulation speed multiplier, 0 for uncapped (default: 1)")
    args = parser.parse_args()
    run(args.rom, args.log, max_turns=args.max_turns, speed=args.speed)


if __name__ == "__main__":
    main()
```

`excluded_buttons` is the set in force when Jev decided this turn. `turns_since_progress` is after this turn's press.

- [ ] **Step 4: Run the whole suite**

Run: `$PYTEST`
Expected: all pass (3 species + state tests unchanged, 8 progress, 6 decision, 6 emulator, 3 main)

- [ ] **Step 5: Update README Running section**

Replace the Running section's body in `README.md` with:

```markdown
    python -m jev_plays_pokemon.main --rom /path/to/pokemon_blue.gb --log turns.jsonl --max-turns 1000 --speed 2

`--max-turns` stops the run cleanly; leave it off to run until Ctrl-C. Set it
for anything launched through secrets-broker, since Ctrl-C there doesn't reach
the Python process. `--speed` is an emulation speed multiplier, 0 for uncapped.
Each run starts from the beginning of the game; there's no save/resume.
```

- [ ] **Step 6: Commit**

```bash
git add src/jev_plays_pokemon/main.py tests/test_main.py README.md
git commit -m "Wire progress tracking into the loop, add --max-turns and --speed"
```

---

### Task 5: Live acceptance (coordinator only, needs the user)

No code. Not for a subagent: it needs the real ROM, the real API and a root-only allowlist change.

- [ ] **Step 1:** Push the branch, open the PR, don't merge yet.
- [ ] **Step 2:** Ask the user to allowlist the exact argv (the ROM path and log path are the same ones used for the first run; copy them from that entry):

```
sudo secrets-broker-admin projects allowlist add jev-plays-pokemon -- .venv/bin/python -m jev_plays_pokemon.main --rom <same ROM path> --log /tmp/jev-plays-pokemon-turns-2.jsonl --max-turns 1000 --speed 0
```

The run executes from the main checkout, so it needs the branch checked out there or merged first. Decide with the user which.
- [ ] **Step 3:** `--dry-run` it, then run it.
- [ ] **Step 4:** Check the log:
  - Did the player leave map 38? (success criterion)
  - How many turns hit `excluded_buttons` non-empty, and did exclusion precede each escape?
  - False progress: stretches where position and dialogue stay fixed but `turns_since_progress` keeps resetting to 0. If present, the tilemap-animation assumption is wrong; report it before changing anything.
- [ ] **Step 5:** Report results to the user with the rows behind any claim. Cost is provisional until TypeSafe billing catches up.
