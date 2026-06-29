"""htop_tycoon.ui.widgets.header — GameHeader top-line meta strip (T22).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 515-524:

- ``GameHeader`` subclasses ``textual.widgets.Static`` and renders the
  top-line meta strip::

      tick: 42  |  2026년 1분기 12주차  |  Engineering·5명  |  SaaS

  The four pipe-separated sections are:
    1. ``tick: N`` — current engine tick.
    2. ``YYYY년 Q분기 W주차`` — game time (year + quarter + week).
    3. ``<DeptType>·N명`` — first department (insertion order) and its
       employee count.
    4. ``<ProductType>`` — first product (insertion order); falls back to
       ``"제품 없음"`` when no products exist.

- The header subscribes to ``EventBus`` (passed in via the constructor) and
  re-renders on every ``StateUpdated`` event. The bus is the public surface;
  if ``None`` is passed the header starts empty (useful for tests).

- ``update_from_state(state)`` is the explicit mutator, used by the bus
  callback but also callable directly by tests that want to push a state
  without going through the bus.

Anti-patterns avoided:

- No direct mutation of engine state. The widget reads ``state`` and
  renders; the engine remains the sole writer.
- No ``event_bus.publish`` calls in this module — the header is a
  downstream consumer, not a producer.
- No bare ``random.*`` — no RNG flows here.
- No hardcoded magic numbers; the format string is the locked contract.
- No emoji.

Defensive notes:

- Empty ``state.departments`` or ``state.products`` does NOT crash; the
  header shows a non-empty placeholder instead. The locked top-line is
  defined for the non-empty case; the QA failure scenarios exercise
  empty inputs.
"""

from __future__ import annotations

from typing import Any

from textual.widgets import Static

from htop_tycoon.domain.dept import Department
from htop_tycoon.domain.product import Product
from htop_tycoon.domain.state import GameState
from htop_tycoon.engine.events import Event, EventBus, StateUpdated

__all__ = ["GameHeader"]


# Locked top-line format. Two-space padding around every ``|`` separator
# matches the plan's example output exactly. The five substitution slots
# are pause prefix, tick, time string, dept label, product label; the
# pause prefix is the empty string when running and "⏸ 일시정지 | " when
# paused (Wave 7 — the header is the second user-visible cue alongside
# the #pause-button label).
_HEADER_FORMAT: str = "{pause_prefix}tick: {tick}  |  {time_str}  |  {dept_str}  |  {prod_str}"

_PAUSE_PREFIX: str = "⏸ 일시정지  |  "

# Placeholders for the empty-departments and empty-products cases. Kept
# short and Korean per the UI convention; the test suite asserts the
# *absence* of the dept/product label rather than the *presence* of these
# placeholders, so swapping them is safe as long as they remain non-empty
# and recognizable.
_EMPTY_DEPT_LABEL: str = "부서 없음"
_EMPTY_PROD_LABEL: str = "제품 없음"


class GameHeader(Static):
    """htop-style top-line header: ``tick | time | dept | product``.

    Constructed eagerly (in ``__init__``) so the widget is mounted with an
    empty renderable; the first ``StateUpdated`` event populates the text.
    The header re-renders on every subsequent ``StateUpdated``.

    Construction:

    - ``bus``: optional ``EventBus``. If provided, the header registers a
      callback for ``StateUpdated`` during construction. If ``None``, the
      header starts empty and ignores events (useful for isolated tests).
    - All other ``**kwargs`` are forwarded to ``Static`` (id, classes, etc.).
    """

    def __init__(self, bus: EventBus | None = None, **kwargs: Any) -> None:
        """Initialize with an empty renderable; subscribe to ``bus`` if given.

        Given: an optional EventBus and standard Static kwargs
        When:  ``GameHeader(bus)`` is constructed
        Then:  ``self.renderable`` is the empty string; if ``bus`` is not
               ``None``, the header is registered as a ``StateUpdated``
               subscriber (and the bus is stashed on ``self._bus`` for
               potential late-binding uses).
        """
        super().__init__("", **kwargs)
        # Cache the state so tests can read what the widget is showing
        # without re-publishing events. ``None`` means "no state seen yet".
        self._state: GameState | None = None
        # Cache the bus so late-bound test code (and future T31 wiring)
        # can read which bus the header is bound to without poking at
        # private subscription lists.
        self._bus: EventBus | None = bus
        # Wave 7: pause-state flag. Lives on the widget, not on
        # ``GameState``, because the per-tick pipeline stops firing
        # ``StateUpdated`` events while paused — a bus-driven flag would
        # freeze at the last pre-pause value.
        self._paused: bool = False
        if bus is not None:
            bus.subscribe(StateUpdated, self._on_state_updated)

    # ------------------------------------------------------------- event bus

    def _on_state_updated(self, event: Event) -> None:
        """``StateUpdated`` callback — cache the new state and re-render.

        Given: a ``StateUpdated`` event carrying a fresh ``GameState``
        When:  the EventBus dispatches the event
        Then:  ``self._state`` is rebound and the renderable is refreshed.

        The parameter type is ``Event`` (not ``StateUpdated``) to match
        the ``EventBus.subscribe`` signature; the bus dispatches by exact
        event type so a callback registered for ``StateUpdated`` only ever
        receives ``StateUpdated`` instances. The ``cast`` and ``isinstance``
        guard below make the narrowing explicit and type-safe.
        """
        if not isinstance(event, StateUpdated):
            return  # Defensive: bus only sends StateUpdated; reject anything else.
        self._state = event.state
        self.update(self._build_renderable())

    # ------------------------------------------------------------- mutator

    def update_from_state(self, state: GameState) -> None:
        """Explicit mutator — set the displayed state without going through the bus.

        Given: a ``GameState``
        When:  called (e.g. from a test, or by future App-level wiring)
        Then:  ``self._state`` is rebound and the renderable is refreshed.
        """
        self._state = state
        self.update(self._build_renderable())

    # ------------------------------------------------------------- helpers

    def _build_renderable(self) -> str:
        """Build the locked top-line string from ``self._state``.

        Returns the empty string when no state has been received yet. For
        the non-empty case, picks the first department (insertion order)
        and the first product (insertion order); falls back to the
        empty-state placeholders when those collections are empty.
        """
        state = self._state
        if state is None:
            return ""
        time_str = (
            f"{state.game_time.year}년 "
            f"{state.game_time.quarter}분기 "
            f"{state.game_time.week}주차"
        )
        dept_str = _first_dept_label(state)
        prod_str = _first_product_label(state)
        return _HEADER_FORMAT.format(
            pause_prefix=_PAUSE_PREFIX if self._paused else "",
            tick=state.tick,
            time_str=time_str,
            dept_str=dept_str,
            prod_str=prod_str,
        )

    def set_paused(self, paused: bool) -> None:
        """Flip the pause-state indicator and re-render.

        Wave 7: called from :meth:`HtopTycoonApp._update_header_pause_indicator`
        on every click of the ``#pause-button``. Re-renders immediately
        so the user sees the ``⏸ 일시정지`` prefix the moment the clock
        halts; the next ``StateUpdated`` event is not required (and won't
        fire while paused anyway — see the ``_paused`` attribute note in
        :meth:`__init__`).
        """
        if self._paused == paused:
            return
        self._paused = paused
        self.update(self._build_renderable())


def _first_dept_label(state: GameState) -> str:
    """Return the ``<Type>·N명`` label for the first dept in ``state``.

    Defensive: when ``state.departments`` is empty, returns
    :data:`_EMPTY_DEPT_LABEL` so the header does not crash. The empty
    fallback is part of the locked UI behavior.
    """
    if not state.departments:
        return _EMPTY_DEPT_LABEL
    # ``state.departments`` is ``dict[DepartmentId, Any]`` per the locked
    # domain model; narrow to ``Department`` here at the read boundary.
    first_id = next(iter(state.departments))
    first_dept = state.departments[first_id]
    if not isinstance(first_dept, Department):  # pragma: no cover - defensive
        return _EMPTY_DEPT_LABEL
    return f"{first_dept.type.value}·{len(first_dept.employee_ids)}명"


def _first_product_label(state: GameState) -> str:
    """Return the ``<Type>`` label for the first product in ``state``.

    Defensive: when ``state.products`` is empty, returns
    :data:`_EMPTY_PROD_LABEL` so the header does not crash. The empty
    fallback is part of the locked UI behavior.
    """
    if not state.products:
        return _EMPTY_PROD_LABEL
    first_id = next(iter(state.products))
    first_prod = state.products[first_id]
    if not isinstance(first_prod, Product):  # pragma: no cover - defensive
        return _EMPTY_PROD_LABEL
    return first_prod.type.value
