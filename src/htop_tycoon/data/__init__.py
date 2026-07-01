"""htop-tycoon v3.0 — static game data tables (YAML).

The YAMLs in this package are the canonical source of game content:
  - `balance.yaml`      — numeric game economics (salaries, costs, awards, ...)
  - `genres.yaml`       — 12 game genres
  - `themes.yaml`       — 30 game themes / directions
  - `combos.yaml`       — 12+ genre × theme combo bonuses
  - `consoles.yaml`     — 5 platforms with lifecycle curves
  - `achievements.yaml` — 7 Legacy Score achievements

Wave 1 ships the data only; Wave 2+ will add typed loaders (via
`yaml.safe_load`) under `engine/` or `persistence/`. The file format is
the stable contract — editors changing YAMLs MUST preserve the entry
counts (see `docs/superpowers/specs/2026-07-01-htop-tycoon-v3-design.md`
§1.3 scope cap) and the field names documented in each file header.

Korean UI labels live alongside English labels in every entry; downstream
consumers (engine, UI) prefer `name_ko` for display per the project's
default-Korean policy.
"""
