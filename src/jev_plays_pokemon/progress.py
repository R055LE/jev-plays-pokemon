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
            # Leaving Jev a single option would be the harness choosing for it.
            self.excluded = frozenset() if len(excluded) >= len(BUTTONS) - 1 else frozenset(excluded)
