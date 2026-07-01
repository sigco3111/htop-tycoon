"""htop-tycoon v3.0 — Pilot test scenarios (spec §7.4).

Five required scenarios:
  1. startup_render         — app boots, main screen renders
  2. strategy_picker        — press 's' -> StrategyPickerScreen shows 4 options
  3. hire_action            — press 'H' (Shift+h) -> dept picker -> employee added
  4. start_game_action      — press 'n' -> genre+direction pick -> game starts
  5. save_load_roundtrip    — press 'S' -> save -> restart -> load -> identical state

Wave 6 first pass: only the ``startup_render`` scenario is enabled.
The others arrive as their screens are added (Wave 6+ follow-ups).
"""
