# Jev Plays Pokemon Blue

Jev (TypeSafe AI's System One model) plays Pokemon Blue through a
PyBoy-driven harness. See `docs/superpowers/specs/2026-09-21-jev-plays-pokemon-design.md`
for the design and `docs/superpowers/plans/2026-09-21-jev-plays-pokemon.md`
for the implementation plan.

## Setup

1. `pip install -e ".[dev]"`
2. Set `TYPESAFE_API_KEY` in your environment (or a local `.env`, gitignored).
3. Supply your own legally-owned Pokemon Blue ROM file. It is never
   committed to this repo.

## Running

    python -m jev_plays_pokemon.main --rom /path/to/pokemon_blue.gb --log turns.jsonl --max-turns 1000 --speed 2

`--max-turns` stops the run cleanly; leave it off to run until Ctrl-C. Set it
for anything launched through secrets-broker, since Ctrl-C there doesn't reach
the Python process. `--speed` is a whole-number speed multiplier, 0 for uncapped.
Each run starts from the beginning of the game; there's no save/resume.

## Testing

    pytest
