from dataclasses import asdict, dataclass

from .species import species_name

_MAP_ID_ADDRESS = 0xD35E
_PLAYER_Y_ADDRESS = 0xD361
_PLAYER_X_ADDRESS = 0xD362
_BADGES_ADDRESS = 0xD356
_MONEY_ADDRESS = 0xD347  # 3 bytes, packed BCD, most-significant byte first

_BADGE_NAMES = [
    "Boulder", "Cascade", "Thunder", "Rainbow",
    "Soul", "Marsh", "Volcano", "Earth",
]

# Party Pokemon are a fixed-size struct starting at 0xD16B (pokered's
# wPartyMon1..wPartyMon6), one struct per party slot.
_PARTY_COUNT_ADDRESS = 0xD163
_PARTY_MON_BASE_ADDRESS = 0xD16B
_PARTY_MON_STRUCT_SIZE = 0x2C  # 44 bytes
_MON_OFFSET_SPECIES = 0
_MON_OFFSET_HP = 1  # 2 bytes, big-endian
_MON_OFFSET_STATUS = 4
_MON_OFFSET_LEVEL = 33
_MON_OFFSET_MAX_HP = 34  # 2 bytes, big-endian

# Gen 1 non-volatile status bitmask, per pokered's constants/battle_constants.asm.
_STATUS_SLEEP_MASK = 0b0000_0111
_STATUS_POISONED_BIT = 1 << 3
_STATUS_BURNED_BIT = 1 << 4
_STATUS_FROZEN_BIT = 1 << 5
_STATUS_PARALYZED_BIT = 1 << 6


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


def _decode_status(status_byte: int) -> str:
    if status_byte & _STATUS_SLEEP_MASK:
        return "ASLEEP"
    if status_byte & _STATUS_POISONED_BIT:
        return "POISONED"
    if status_byte & _STATUS_BURNED_BIT:
        return "BURNED"
    if status_byte & _STATUS_FROZEN_BIT:
        return "FROZEN"
    if status_byte & _STATUS_PARALYZED_BIT:
        return "PARALYZED"
    return "OK"


def _read_party(emulator) -> list[PartyMember]:
    count = emulator.read_byte(_PARTY_COUNT_ADDRESS)
    party = []
    for slot in range(count):
        base = _PARTY_MON_BASE_ADDRESS + slot * _PARTY_MON_STRUCT_SIZE
        species_id = emulator.read_byte(base + _MON_OFFSET_SPECIES)
        hp = (
            emulator.read_byte(base + _MON_OFFSET_HP) << 8
            | emulator.read_byte(base + _MON_OFFSET_HP + 1)
        )
        max_hp = (
            emulator.read_byte(base + _MON_OFFSET_MAX_HP) << 8
            | emulator.read_byte(base + _MON_OFFSET_MAX_HP + 1)
        )
        party.append(
            PartyMember(
                species=species_name(species_id),
                level=emulator.read_byte(base + _MON_OFFSET_LEVEL),
                hp=hp,
                max_hp=max_hp,
                status=_decode_status(emulator.read_byte(base + _MON_OFFSET_STATUS)),
            )
        )
    return party


def _read_money(emulator) -> int:
    b0 = emulator.read_byte(_MONEY_ADDRESS)
    b1 = emulator.read_byte(_MONEY_ADDRESS + 1)
    b2 = emulator.read_byte(_MONEY_ADDRESS + 2)
    return (
        (b0 >> 4) * 100000 + (b0 & 0xF) * 10000
        + (b1 >> 4) * 1000 + (b1 & 0xF) * 100
        + (b2 >> 4) * 10 + (b2 & 0xF)
    )


def read_game_state(emulator) -> GameState:
    badge_byte = emulator.read_byte(_BADGES_ADDRESS)
    badges = [name for i, name in enumerate(_BADGE_NAMES) if badge_byte & (1 << i)]

    return GameState(
        map_id=emulator.read_byte(_MAP_ID_ADDRESS),
        player_x=emulator.read_byte(_PLAYER_X_ADDRESS),
        player_y=emulator.read_byte(_PLAYER_Y_ADDRESS),
        party=_read_party(emulator),
        badges=badges,
        money=_read_money(emulator),
        dialogue_active=emulator.dialogue_active(),
    )
