"""htop-tycoon v3.0 — annual ceremony + game show. Spec §2.4.

Wave 3 engine: two player-triggered (or yearly cron) actions:

- :func:`run_year_end_ceremony` — once per game-year, distribute the spec §2.4
  prize ladder to the top-3 eligible releases and apply the trash penalty
  to any release that underperformed.
- :func:`run_game_show` — player spends cash for an immediate +50 % fan
  boost (Wave 3 simplification; Wave 4 will track the timed 180-day
  effect via ``GameProject.fan_boost``).

NOTE on magic numbers (AGENTS.md §5.4 invariant): the prize amounts and
eligibility thresholds below mirror ``data/balance.yaml::awards.{year_end.*,
eligibility.*, game_show.*}``. The Wave 4 data-loader will replace these
with proper YAML reads.
"""
from __future__ import annotations

from htop_tycoon.domain import Event, GameProject, GameState


def run_year_end_ceremony(state: GameState) -> tuple[GameState, list[Event]]:
    """Apply the §2.4 yearly prize ladder.

    Eligibility (spec §2.4 + balance.yaml::awards.eligibility.year_end_min_score):
    a released project with ``current_quality_avg`` >= 5.0 is eligible.
    Trash (balance.yaml::awards.eligibility.trash_max_score): a released
    project with ``current_quality_avg`` < 4.0 incurs the trash penalty.

    Prize ladder (balance.yaml::awards.year_end):
      - first place:   +200,000
      - second place:  +100,000
      - third place:    +50,000
      - trash penalty: -100,000 (applied at most once)

    Wave 3 simplification: applied to ALL released projects, not filtered by
    release-year (the engine doesn't yet track release year per project).
    Wave 4 will narrow the scope to projects released in the current year.

    Returns the new state and an empty event list. Future Wave 4 will emit
    per-winner ``"award"`` events with payload ``{"project_id", "place"}``.
    """
    eligible: tuple[GameProject, ...] = tuple(
        p for p in state.released_projects() if p.current_quality_avg >= 5.0
    )
    trash: tuple[GameProject, ...] = tuple(
        p for p in state.released_projects() if p.current_quality_avg < 4.0
    )

    delta = 0
    if len(eligible) >= 1:
        delta += 200_000  # balance.yaml::awards.year_end.first_prize
    if len(eligible) >= 2:
        delta += 100_000  # balance.yaml::awards.year_end.second_prize
    if len(eligible) >= 3:
        delta += 50_000  # balance.yaml::awards.year_end.third_prize
    if trash:
        delta -= 100_000  # balance.yaml::awards.year_end.trash_penalty

    new_state = state.replace(cash=state.cash + delta)
    return new_state, []


def run_game_show(state: GameState) -> tuple[GameState, list[Event]]:
    """Apply the §2.4 game-show fan boost.

    Costs ``participation_cost`` (20,000; balance.yaml::awards.game_show).
    On success, fans are immediately increased by ``fan_boost_pct`` (0.50).

    Wave 3 simplification: the boost is applied immediately rather than as a
    timed 180-day multiplier. Wave 4 will track the timed effect via
    ``GameProject.fan_boost`` and tick it down in ``engine.tick``.

    Returns the new state and an empty event list. If the player can't
    afford the entry fee, the state is unchanged.
    """
    cost = 20_000  # balance.yaml::awards.game_show.participation_cost
    if state.cash < cost:
        return state, []
    new_state = state.replace(
        cash=state.cash - cost,
        fans=int(state.fans * (1.0 + 0.50)),  # balance.yaml::awards.game_show.fan_boost_pct
    )
    return new_state, []


__all__ = ["run_game_show", "run_year_end_ceremony"]


