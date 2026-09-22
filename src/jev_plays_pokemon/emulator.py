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

    def dialogue_active(self) -> bool:
        return self._pyboy.tilemap_window[_DIALOGUE_TILE_X, _DIALOGUE_TILE_Y] == _DIALOGUE_ARROW_TILE_ID

    def stop(self) -> None:
        self._pyboy.stop()
