from jev_plays_pokemon.emulator import SETTLE_FRAMES, Emulator, hold_frames


class FakeTileMap:
    def __init__(self, rows):
        self._rows = rows

    def __getitem__(self, xy):
        return [list(r) for r in self._rows]


class FakePyBoy:
    def __init__(self):
        self.calls = []
        self.speed = None
        self.tilemap_background = FakeTileMap([[1, 2], [3, 4]])
        self.tilemap_window = FakeTileMap([[0, 0], [0, 0]])
        self.memory = {0xFF42: 0, 0xFF43: 0}

    def set_emulation_speed(self, speed):
        self.speed = speed

    def button(self, name, delay):
        self.calls.append(("button", name, delay))

    def tick(self, count, render):
        self.calls.append(("tick", count))


def test_direction_holds_sixteen_frames_per_tile():
    assert hold_frames("UP", 1) == 16
    assert hold_frames("LEFT", 6) == 96


def test_non_direction_is_a_short_fixed_press():
    assert hold_frames("A", None) == 4
    assert hold_frames("START", None) == 4


def test_press_holds_then_settles():
    pyboy = FakePyBoy()
    emulator = Emulator("rom.gb", pyboy=pyboy)

    emulator.press("DOWN", 3)

    # One tick per frame: PyBoy only frame-limits once per tick() call.
    assert pyboy.calls == [("button", "down", 48)] + [("tick", 1)] * (48 + SETTLE_FRAMES)


def test_wait_only_settles():
    pyboy = FakePyBoy()
    Emulator("rom.gb", pyboy=pyboy).wait()

    assert pyboy.calls == [("tick", 1)] * SETTLE_FRAMES


def test_speed_is_passed_to_pyboy():
    pyboy = FakePyBoy()
    Emulator("rom.gb", speed=0, pyboy=pyboy)

    assert pyboy.speed == 0


def test_tilemap_hash_changes_with_tilemap_contents():
    pyboy = FakePyBoy()
    emulator = Emulator("rom.gb", pyboy=pyboy)
    before = emulator.tilemap_hash()

    assert emulator.tilemap_hash() == before
    pyboy.tilemap_window = FakeTileMap([[0, 9], [0, 0]])
    assert emulator.tilemap_hash() != before


def test_tilemap_hash_changes_with_scroll():
    pyboy = FakePyBoy()
    emulator = Emulator("rom.gb", pyboy=pyboy)
    before = emulator.tilemap_hash()

    pyboy.memory[0xFF43] = 16
    assert emulator.tilemap_hash() != before
