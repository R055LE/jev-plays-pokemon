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
        self.last_questions = None

    def system_one(self, state, questions):
        self.calls += 1
        self.last_questions = questions
        if self.calls <= self._fail_times:
            raise RuntimeError("simulated API failure")
        return self._response


def response(button, length, confidence=0.9):
    return FakeResponse({
        "button": FakeChoiceAnswer(choice=button, confidence=confidence),
        "length": FakeChoiceAnswer(choice=length, confidence=0.5),
    })


def test_direction_gets_tiles_from_length():
    client = DecisionClient(client=FakeClient(response=response("UP", "FEW", 0.7)), retry_backoff_seconds=0)

    assert client.decide(make_state()) == Action(button="UP", tiles=3, confidence=0.7)


def test_non_direction_ignores_length():
    client = DecisionClient(client=FakeClient(response=response("A", "MANY", 0.92)), retry_backoff_seconds=0)

    assert client.decide(make_state()) == Action(button="A", tiles=None, confidence=0.92)


def test_excluded_buttons_are_not_offered_to_jev():
    fake = FakeClient(response=response("B", "ONE"))
    client = DecisionClient(client=fake, retry_backoff_seconds=0)

    client.decide(make_state(), excluded=frozenset({"A", "START"}))

    offered = set(fake.last_questions["button"].criteria)
    assert offered == {"UP", "DOWN", "LEFT", "RIGHT", "B", "SELECT"}


def test_no_exclusions_offers_every_button():
    fake = FakeClient(response=response("A", "ONE"))
    client = DecisionClient(client=fake, retry_backoff_seconds=0)

    client.decide(make_state())

    assert len(fake.last_questions["button"].criteria) == 8


def test_decide_succeeds_after_one_retry():
    client = DecisionClient(client=FakeClient(response=response("LEFT", "ONE", 0.7), fail_times=1), retry_backoff_seconds=0)

    assert client.decide(make_state()) == Action(button="LEFT", tiles=1, confidence=0.7)


def test_decide_falls_back_to_wait_after_retry_exhausted():
    client = DecisionClient(client=FakeClient(fail_times=99), retry_backoff_seconds=0)

    assert client.decide(make_state()) == Action(button="WAIT", tiles=None, confidence=0.0)
