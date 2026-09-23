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
