# Jev Plays Pokemon Blue — Design

## Goal

Get TypeSafe AI's Jev model playing Pokemon Blue via a Python harness, for
fun. Not aiming to beat the game or speedrun on day one — success is the
play loop working end to end and being fun to watch/tinker with. A
"cliff notes" style narrator that turns the raw decision log into
readable commentary is an explicitly deferred stretch goal (phase 2), not
part of this build.

## Out of scope (v1)

- Narrator / commentary generation.
- Streaming or any remote-viewer web UI.
- Save/resume between runs. Each run starts from the beginning of the
  game; if the process stops, you start it again.
- Automatic stuck-state recovery (see Error Handling). Designed later in
  `2026-09-22-stuck-recovery-design.md`.
- Any action space beyond single button presses (no macros like "walk to
  the Pokemon Center").

## Runtime

Runs interactively on a machine with a desktop (e.g. barnabas), with
PyBoy opening a real window so the game is watchable live. No headless
mode, no screenshot polling, no web viewer — that's the simplest option
given early runs are expected to be rough and this isn't meant to be a
stream.

The ROM file is supplied locally by the user (a legally-owned Pokemon
Blue ROM), referenced by a config value / environment variable, and is
never committed to the repo.

## Components

Four modules, each independently understandable and testable:

- **`emulator.py`** — Wraps PyBoy. Responsibilities: load the ROM, advance
  N frames, press/release a given button, expose the underlying memory
  interface for reads. Nothing here knows what any memory address means.
- **`state.py`** — Reads a fixed set of WRAM addresses (from the public
  pokered/DataCrystal RAM map — Red and Blue share the engine) and
  returns a typed `GameState` snapshot: map ID, player X/Y/facing, party
  (species, level, HP/maxHP, status), badges, money, and whether a
  dialogue box or menu is currently active. Nothing here knows about
  PyBoy internals beyond calling into `emulator.py`'s memory reads.
- **`decision.py`** — Takes a `GameState`, calls the Jev API with the
  action schema (below), and returns a typed `Action`. Nothing here
  knows about the emulator at all — it's a pure state-in, action-out
  client.
- **`main.py`** — The loop: read state → get decision → apply to
  emulator → log the turn → repeat until interrupted (Ctrl-C). Contains
  no game-logic or API-shape knowledge of its own; it only wires the
  other three modules together.

## Data flow

One "turn":

1. `state.py` reads the current `GameState` from the emulator.
2. `decision.py` sends that state to Jev and gets back an `Action`.
3. `main.py` applies the action via `emulator.py` (press the button, hold
   for the given frame count, advance the emulator).
4. `main.py` logs `{turn, timestamp, state, action, jev_confidence}`.
5. Repeat.

There's no special-casing for menus or dialogue in the loop itself —
those are just fields on `GameState` (e.g. `dialogue_active: bool`), and
it's Jev's job to decide to press A to advance text. This keeps
`main.py` free of game-specific logic.

## Action schema (the Jev contract)

Jev is a typed-output model — it returns typed values with confidence
scores, not prose. The action space for v1:

```
button: enum[UP, DOWN, LEFT, RIGHT, A, B, START, SELECT]
hold_frames: int (1-30)
```

Plus whatever native confidence score Jev returns alongside the typed
value — logged but not currently acted on.

No compound or macro actions. Jev decides one button press at a time.

## Error handling

- **Jev API call fails or times out** — retry once with backoff, then
  fall back to a no-op `WAIT` action for that turn rather than crashing
  the loop.
- **Game appears stuck** (same map/position for 50 consecutive turns, a
  tunable constant) — logged as a flag on the turn record. No
  auto-recovery in v1; this is a known limitation.
- **PyBoy crashes** — the loop exits and logs the failure. No
  auto-restart, since there's no save/resume; rerun manually.

## Testing

This is an integration-heavy, watch-it-run project, so testing is
deliberately light:

- `state.py`: unit tests against a couple of captured PyBoy save-state
  fixtures (known game states → expected `GameState` values).
- `decision.py`: unit tests against a mocked Jev client, verifying the
  action schema round-trips correctly.
- `main.py` and overall play quality: verified by running it and
  watching, not by automated tests.

## Repo

New repo: `R055LE/jev-plays-pokemon`. GitHub remote creation and
visibility (public/private) are a separate decision from this spec.
