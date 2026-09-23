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

# Background scroll registers. The overworld scrolls the same tilemap buffer
# as the player walks, so the tilemap alone can miss a step.
_SCY_ADDRESS = 0xFF42
_SCX_ADDRESS = 0xFF43

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
    def __init__(self, rom_path: str, speed: int = 1, pyboy=None) -> None:
        self._pyboy = pyboy or PyBoy(rom_path, window="SDL2")
        self._pyboy.set_emulation_speed(speed)

    def press(self, button: str, tiles: int | None) -> None:
        frames = hold_frames(button, tiles)
        self._pyboy.button(_BUTTON_TO_PYBOY_NAME[button], delay=frames)
        self._tick(frames + SETTLE_FRAMES)

    def wait(self) -> None:
        self._tick(SETTLE_FRAMES)

    def _tick(self, frames: int) -> None:
        # PyBoy frame-limits once per tick() call, so one call per frame keeps
        # --speed honest and renders every frame to the window.
        for _ in range(frames):
            self._pyboy.tick(1, True)

    def tilemap_hash(self) -> int:
        # Tilemaps hold tile ids, not tile graphics or sprites, so animated
        # water and walking NPCs shouldn't change this.
        background = tuple(map(tuple, self._pyboy.tilemap_background[:, :]))
        window = tuple(map(tuple, self._pyboy.tilemap_window[:, :]))
        scroll = (self._pyboy.memory[_SCY_ADDRESS], self._pyboy.memory[_SCX_ADDRESS])
        return hash((background, window, scroll))

    def read_byte(self, address: int) -> int:
        return self._pyboy.memory[address]

    def dialogue_active(self) -> bool:
        return self._pyboy.tilemap_window[_DIALOGUE_TILE_X, _DIALOGUE_TILE_Y] == _DIALOGUE_ARROW_TILE_ID

    def stop(self) -> None:
        self._pyboy.stop()
