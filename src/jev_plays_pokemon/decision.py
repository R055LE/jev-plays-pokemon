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
