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
