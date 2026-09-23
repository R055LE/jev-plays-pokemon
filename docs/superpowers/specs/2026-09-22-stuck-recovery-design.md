# Stuck Recovery and Pacing: Design

Follows the v1 design (`2026-09-21-jev-plays-pokemon-design.md`), which left
stuck recovery out of scope.

## Why

The first live run did 7,355 turns. From turn 369 on, every action was `A`
held for 2 frames, at map 38 (3,6), the bedroom the game starts in.
`dialogue_active` flipped every ~17 turns, so Jev was talking to the same
object over and over. The position-based `stuck` flag was true for 7,255
turns and did nothing, as designed.

Two problems showed up in that log:

- **Each decision barely advanced the game.** A TAP is 2 frames, about 33ms
  of game time. The run was ~21 minutes of wall clock (mostly Jev latency,
  ~0.16s per call) but only ~4 minutes of game time. A Gen 1 tile step is
  about 16 frames, and a short direction tap only turns the player, so a TAP
  on a direction couldn't have moved anyone. Jev also usually saw a screen
  that hadn't caught up with its last press.
- **Jev is deterministic.** The same state gives the same answer, so an
  unchanging state is an infinite loop.

A probe against the real API (12 calls, the stuck bedroom state) showed that
adding `turns_since_progress` and `recent_buttons: [A, A, A, A, A]` to the
state made Jev more confident in A (0.41 up to 0.80). Only a plain-English
"A isn't working, try something else" note changed its pick, and it picked B.
Jev pattern-matches its input. Showing it history doesn't help it get
unstuck.

## Principle

Only Jev presses buttons. The harness shapes what Jev is allowed to choose
from, the same way a Tetris harness lists legal placements, but it never
picks a button itself.

## Pacing

- Jev still answers two `Choice` questions per call: `button` and `length`.
- `length` is `ONE` / `FEW` / `MANY`, meaning 1 / 3 / 6 tiles.
  - Direction buttons are held for `16 × tiles` frames.
  - A, B, START and SELECT ignore `length` and are a fixed 4-frame press.
  - Both questions go in the same call, so `length` can't depend on the
    chosen button. The `length` criteria text says it only applies to
    directions, and that ONE is right for menus.
- After the button is released, the emulator ticks `SETTLE_FRAMES = 20`
  before the next state read, so Jev sees the result of its press.
- Known rough edge: FEW/MANY in a menu moves the cursor several rows. The
  harness can't tell a menu from the overworld, so this is accepted.
- A turn now covers roughly 24–116 frames (0.4–2s of game time) instead of
  2–20.

## Stuck recovery

### Progress detection

Harness-only; Jev never sees any of this.

- After each turn, hash the background and window tilemaps plus the scroll
  registers (SCX/SCY), since the overworld scrolls one tilemap buffer.
- A turn is progress if that hash hasn't appeared in the last 50 turns
  (`PROGRESS_WINDOW = 50`).
- Walking, new dialogue text and opening a menu all produce new tilemaps.
  A loop between a few screens (like the bedroom) doesn't.
- Tile animations (water, flowers) change tile graphics, not tilemap
  indices, and sprites aren't in the tilemap, so neither should count as
  progress. This is an assumption until the live acceptance run confirms it.

Position alone isn't used, because a lot of real progress happens in place
(Oak's intro, signs, menus).

### Exclusion

- Once `turns_since_progress` reaches `EXCLUSION_STRETCH = 10`, every button
  pressed during the no-progress stretch is removed from the `button`
  Choice.
- Each further 10 turns without progress adds whatever was pressed in that
  stretch to the excluded set.
- Any progress clears the excluded set.
- If 7 or 8 buttons would be excluded, the set resets to empty. A one-option
  Choice would be the harness choosing for Jev. Worst case is about 70 turns
  to cycle every button.

In the first run this would have excluded A at turn ~379.

### What Jev sees

No change to the state dict. `turns_since_progress` and recent buttons are
not added, per the probe. They go in the log only.

## CLI

- `--max-turns N`: exit cleanly after N turns. Default unlimited. Live tests
  should always set it, because a stop signal doesn't reach the Python
  process through secrets-broker's sudo chain (the first run made ~700 calls
  after it was killed).
- `--speed X`: whole number passed to `pyboy.set_emulation_speed(X)` (PyBoy
  stores it as an int). Default 1 (real time), 0 is uncapped. PyBoy only
  frame-limits once per `tick()` call, so the emulator ticks one frame at a
  time.

## Components

- `progress.py` (new): `ProgressTracker`. Each turn it takes the tilemap hash
  and the button pressed, and returns `turns_since_progress` and the current
  excluded set. Pure logic, no PyBoy.
- `emulator.py`: `tilemap_hash()`; `press()` takes the button and a tile
  count, computes hold frames, then ticks the settle frames.
- `decision.py`: `decide(state, excluded)` builds the `button` criteria
  without the excluded buttons; `length` replaces `hold`.
- `main.py`: wires the tracker in, adds `--max-turns` and `--speed`, logs the
  new fields. Drops the position-based `stuck` flag and `_STUCK_THRESHOLD`.

The v1 fallback stays: on a failed Jev call, retry once, then `WAIT`. A WAIT
turn still goes through the tracker (it pressed nothing, so it adds nothing
to the excluded set).

## Log record

Each turn record gains `turns_since_progress` and `excluded_buttons`, and
loses `stuck`. `action` carries `tiles` for direction presses.

## Testing

Unit tests with the existing fakes:

- Tracker: a new hash is progress; a repeat inside the window isn't; the
  excluded set grows after each 10-turn stretch; progress clears it; it
  resets when all 8 would be excluded.
- Decision: excluded buttons are absent from the criteria sent to the fake
  client.
- Press length: directions hold `16 × tiles` frames, other buttons 4, and
  every press is followed by the settle frames.
- Loop: `--max-turns` stops it.

Live acceptance: a capped run (1,000 turns, `--speed 0`) through
secrets-broker. Success is leaving map 38. The run also checks the
tilemap-animation assumption by looking for false progress in the log.
