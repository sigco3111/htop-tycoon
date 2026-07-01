"""htop-tycoon v3.0 — ending checker. Spec §1.4.

Wave 3 engine: priority-ordered resolution of the 5 endings. The check is
called once per game-day by ``engine.tick.run_day``. When an ending fires,
the engine emits an ``"ending"`` event; the UI is responsible for
transitioning to the post-game screen and (for soft endings) recording the
achievement on the :class:`LegacyScore` panel.

NOTE on magic numbers (AGENTS.md §5.4 invariant): thresholds below are
hardcoded for Wave 3 and mirror ``data/balance.yaml::cash.bankruptcy_threshold``
and ``data/balance.yaml::ending.{mega_hit_sales_threshold,
hall_of_fame_min_count, hall_of_fame_min_score}``. The Wave 4 data-loader
will replace these with proper YAML reads.
"""
from __future__ import annotations

from htop_tycoon.domain import EndingKind, Event, GameState


def check_endings(state: GameState) -> Event | None:
    """Return the first ending event met, or ``None``.

    Priority (spec §1.4):
      1. ``BANKRUPTCY`` — forced end; cash < -50,000 (balance.yaml).
      2. ``MEGA_HIT`` — soft; any released project with ``sales_total`` >= 1M.
      3. ``HALL_OF_FAME`` — soft; 5+ released projects with
         ``current_quality_avg`` >= 8.0.
      4. ``SECRET`` — soft; own console released AND megahit on it.
         **Skipped in Wave 3** (needs active market with own-console tracking,
         not yet exposed by ``engine.market``). Re-check in Wave 4.
      5. ``VOLUNTARY_SALE`` — player-triggered only (F10 quit / sell key in
         the UI). The engine never auto-fires it.

    If the game has already ended (``state.ending is not None``), return
    ``None`` so we don't re-emit.
    """
    if state.ending is not None:
        return None  # game already ended; do not re-fire

    # 1. BANKRUPTCY (forced end — highest priority)
    if state.cash < -50_000:  # balance.yaml::cash.bankruptcy_threshold
        return Event(
            kind="ending",
            day=state.day,
            payload={"ending": EndingKind.BANKRUPTCY.name, "cash": state.cash},
        )

    # 2. MEGA_HIT (soft; recorded on LegacyScore)
    for project in state.released_projects():
        if project.sales_total >= 1_000_000:  # balance.yaml::ending.mega_hit_sales_threshold
            return Event(
                kind="ending",
                day=state.day,
                payload={"ending": EndingKind.MEGA_HIT.name},
            )

    # 3. HALL_OF_FAME (soft; recorded on LegacyScore)
    hall_count = sum(
        1
        for project in state.released_projects()
        if project.current_quality_avg >= 8.0  # balance.yaml::ending.hall_of_fame_min_score
    )
    if hall_count >= 5:  # balance.yaml::ending.hall_of_fame_min_count
        return Event(
            kind="ending",
            day=state.day,
            payload={"ending": EndingKind.HALL_OF_FAME.name},
        )

    # 4. SECRET — deferred to Wave 4 (requires own-console + mega-hit on it;
    # see balance.yaml::ending.secret_ending_requires_mega_hit_on_own).
    # 5. VOLUNTARY_SALE — player-triggered; engine does not auto-fire.

    return None


__all__ = ["check_endings"]
