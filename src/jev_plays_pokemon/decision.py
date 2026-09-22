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
        button_answer = result.answers["button"]
        hold_answer = result.answers["hold"]
        return Action(
            button=button_answer.choice,
            hold_frames=_HOLD_FRAMES[hold_answer.choice],
            confidence=button_answer.confidence,
        )
