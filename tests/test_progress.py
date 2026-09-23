from jev_plays_pokemon.progress import BUTTONS, ProgressTracker


def test_first_turn_is_progress():
    tracker = ProgressTracker()
    tracker.record(1, "A")
    assert tracker.turns_since_progress == 0
    assert tracker.excluded == frozenset()


def test_repeat_screen_inside_window_is_not_progress():
    tracker = ProgressTracker()
    tracker.record(1, "A")
    tracker.record(2, "A")
    tracker.record(1, "A")
    assert tracker.turns_since_progress == 1


def test_screen_older_than_window_counts_as_progress_again():
    tracker = ProgressTracker(window=3)
    for screen in (1, 2, 3, 4):
        tracker.record(screen, "A")
    tracker.record(1, "A")
    assert tracker.turns_since_progress == 0


def test_buttons_pressed_in_stretch_are_excluded_after_stretch():
    tracker = ProgressTracker(stretch=10)
    tracker.record(1, "A")
    for _ in range(9):
        tracker.record(1, "A")
    assert tracker.excluded == frozenset()
    tracker.record(1, "B")
    assert tracker.turns_since_progress == 10
    assert tracker.excluded == frozenset({"A", "B"})


def test_each_further_stretch_adds_its_buttons():
    tracker = ProgressTracker(stretch=10)
    tracker.record(1, "A")
    for _ in range(10):
        tracker.record(1, "A")
    for _ in range(10):
        tracker.record(1, "UP")
    assert tracker.excluded == frozenset({"A", "UP"})


def test_progress_clears_exclusions():
    tracker = ProgressTracker(stretch=10)
    tracker.record(1, "A")
    for _ in range(10):
        tracker.record(1, "A")
    tracker.record(2, "UP")
    assert tracker.turns_since_progress == 0
    assert tracker.excluded == frozenset()


def test_wait_counts_as_no_progress_but_excludes_nothing():
    tracker = ProgressTracker(stretch=10)
    tracker.record(1, "A")
    for _ in range(10):
        tracker.record(1, "WAIT")
    assert tracker.turns_since_progress == 10
    assert tracker.excluded == frozenset()


def test_leaving_jev_one_button_resets_to_empty():
    # A one-option Choice isn't Jev choosing, so reset before it gets there.
    tracker = ProgressTracker(stretch=1)
    tracker.record(1, "A")
    for button in BUTTONS[:6]:
        tracker.record(1, button)
    assert tracker.excluded == frozenset(BUTTONS[:6])
    tracker.record(1, BUTTONS[6])
    assert tracker.excluded == frozenset()
