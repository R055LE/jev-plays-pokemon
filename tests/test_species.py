from jev_plays_pokemon.species import species_name


def test_species_name_resolves_known_ids():
    assert species_name(0xB0) == "CHARMANDER"
    assert species_name(0x99) == "BULBASAUR"
    assert species_name(0x01) == "RHYDON"


def test_species_name_flags_missingno_slots():
    assert species_name(0x1F) == "MISSINGNO."


def test_species_name_handles_unknown_id_without_raising():
    assert species_name(0xFF) == "Unknown Species (255)"
