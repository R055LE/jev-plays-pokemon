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

    def system_one(self, state, questions):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise RuntimeError("simulated API failure")
        return self._response


def test_decide_returns_action_from_jev_response():
    response = FakeResponse({
        "button": FakeChoiceAnswer(choice="A", confidence=0.92),
        "hold": FakeChoiceAnswer(choice="TAP", confidence=0.8),
    })
    client = DecisionClient(client=FakeClient(response=response), retry_backoff_seconds=0)

    action = client.decide(make_state())

    assert action == Action(button="A", hold_frames=2, confidence=0.92)


def test_decide_succeeds_after_one_retry():
    response = FakeResponse({
        "button": FakeChoiceAnswer(choice="UP", confidence=0.7),
        "hold": FakeChoiceAnswer(choice="HOLD", confidence=0.6),
    })
    client = DecisionClient(client=FakeClient(response=response, fail_times=1), retry_backoff_seconds=0)

    action = client.decide(make_state())

    assert action == Action(button="UP", hold_frames=8, confidence=0.7)


def test_decide_falls_back_to_wait_after_retry_exhausted():
    client = DecisionClient(client=FakeClient(fail_times=99), retry_backoff_seconds=0)

    action = client.decide(make_state())

    assert action == Action(button="WAIT", hold_frames=0, confidence=0.0)
