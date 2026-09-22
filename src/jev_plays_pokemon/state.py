from dataclasses import asdict, dataclass

_MAP_ID_ADDRESS = 0xD35E
_PLAYER_Y_ADDRESS = 0xD361
_PLAYER_X_ADDRESS = 0xD362
_BADGES_ADDRESS = 0xD356

_BADGE_NAMES = [
    "Boulder", "Cascade", "Thunder", "Rainbow",
    "Soul", "Marsh", "Volcano", "Earth",
]


@dataclass
class PartyMember:
    species: str
    level: int
    hp: int
    max_hp: int
    status: str


@dataclass
class GameState:
    map_id: int
    player_x: int
    player_y: int
    party: list[PartyMember]
    badges: list[str]
    money: int
    dialogue_active: bool

    def to_dict(self) -> dict:
        return asdict(self)


def read_game_state(emulator) -> GameState:
    badge_byte = emulator.read_byte(_BADGES_ADDRESS)
    badges = [name for i, name in enumerate(_BADGE_NAMES) if badge_byte & (1 << i)]

    party = [
        PartyMember(
            species=member["species"],
            level=member["level"],
            hp=member["hp"],
            max_hp=member["max_hp"],
            status=member["status"],
        )
        for member in emulator.party()
    ]

    return GameState(
        map_id=emulator.read_byte(_MAP_ID_ADDRESS),
        player_x=emulator.read_byte(_PLAYER_X_ADDRESS),
        player_y=emulator.read_byte(_PLAYER_Y_ADDRESS),
        party=party,
        badges=badges,
        money=emulator.money(),
        dialogue_active=emulator.dialogue_active(),
    )
