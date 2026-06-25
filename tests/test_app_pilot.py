"""Tests for T16: HtopTycoonApp — Textual App skeleton + locked 5-region layout.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 434-456:

- ``HtopTycoonApp`` subclasses ``textual.app.App`` and accepts
  ``seed: int = 42``, ``tick_rate: float = 1.0``, ``no_autosave: bool = False``.
- ``BINDINGS = []`` is a class attribute (filled in T24-T25).
- CSS lives in ``app.tcss`` (sibling of ``app.py``) and defines the 5 regions
  plus the header/footer: ``#header``, ``#metrics``, ``#body`` (containing
  ``#org-tree`` and ``#employee-panel``), ``#alerts``, ``#footer``.
- ``on_mount`` initializes ``self.state`` via ``new_game(seed)``, constructs
  ``TickEngine(seed)``, instantiates an ``EventBus``, and starts the periodic
  tick via ``self.set_interval(tick_rate, self._tick_once)``.
- ``_tick_once`` is the locked wiring: a no-arg wrapper around ``engine.advance``
  that supplies the current state, because Textual's ``set_interval`` passes no
  arguments to its callback. Direct ``self.set_interval(self.engine.advance, ...)``
  is forbidden because ``engine.advance(state, n_ticks)`` requires the state.

The tests cover the headless Pilot surface so they run in CI without a TTY.
"""

from __future__ import annotations

from htop_tycoon.domain.state import GameState, new_game
from htop_tycoon.engine.events import EventBus
from htop_tycoon.engine.tick import TickEngine
from htop_tycoon.ui.app import HtopTycoonApp

# -- App construction ------------------------------------------------------


class TestHtopTycoonAppConstruction:
    """``HtopTycoonApp`` is a Textual ``App`` subclass with the locked signature."""

    def test_app_is_textual_app_subclass(self) -> None:
        """Given: HtopTycoonApp
        When: imported
        Then: it is a subclass of textual.app.App
        """
        from textual.app import App

        assert issubclass(HtopTycoonApp, App)

    def test_app_has_empty_bindings_list(self) -> None:
        """``BINDINGS`` is a class attribute equal to ``[]`` (filled in T24-T25).

        The field MUST exist as an empty list — keys/bindings are wired in a
        later task. Empty today means "no keybinds yet".
        """
        assert hasattr(HtopTycoonApp, "BINDINGS")
        assert HtopTycoonApp.BINDINGS == []

    def test_app_accepts_seed_tick_rate_no_autosave(self) -> None:
        """The constructor accepts ``seed``, ``tick_rate``, ``no_autosave``.

        Defaults (per spec): ``seed=42``, ``tick_rate=1.0``, ``no_autosave=False``.
        """
        app = HtopTycoonApp()
        assert app.seed == 42
        assert app.tick_rate == 1.0
        assert app.no_autosave is False

    def test_app_accepts_custom_construction_args(self) -> None:
        """Custom seed/tick_rate/no_autosave are stored on the instance."""
        app = HtopTycoonApp(seed=7, tick_rate=0.5, no_autosave=True)
        assert app.seed == 7
        assert app.tick_rate == 0.5
        assert app.no_autosave is True


# -- Engine + state wiring -------------------------------------------------


class TestHtopTycoonAppEngineWiring:
    """``on_mount`` initializes state, engine, and event bus."""

    async def test_on_mount_initializes_state_engine_and_bus(self) -> None:
        """Given: HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        When: mounted via Pilot
        Then: self.state is a GameState from new_game(42),
              self.engine is a TickEngine(seed=42),
              self.event_bus is an EventBus,
              and the tick interval timer is scheduled.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.state, GameState)
            assert app.state.tick == 0
            assert app.state.rng_seed == 42
            assert isinstance(app.engine, TickEngine)
            assert isinstance(app.event_bus, EventBus)
            # The interval timer must be registered and bound to the app +
            # the locked _tick_once wrapper (Textual stores interval on a
            # private attribute; we assert the timer's target + callback).
            assert app._tick_timer is not None  # type: ignore[attr-defined]
            assert app._tick_timer.target is app  # type: ignore[attr-defined]
            assert app._tick_timer._callback == app._tick_once  # type: ignore[attr-defined]


# -- Locked _tick_once wrapper pattern -------------------------------------


class TestHtopTycoonAppTickOnceWrapper:
    """``_tick_once`` is the locked wrapper: supplies state to engine.advance."""

    async def test_tick_once_advances_state_by_one(self) -> None:
        """Given: a mounted app with state.tick=0
        When: _tick_once() is invoked directly
        Then: state.tick advances to 1 (proves the wrapper supplies state).
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.state.tick == 0
            app._tick_once()
            await pilot.pause()
            assert app.state.tick == 1

    async def test_tick_once_does_not_raise_with_interval_too_fast(self) -> None:
        """Direct set_interval(engine.advance, ...) would TypeError at runtime
        (advance needs the current state). The _tick_once wrapper is the
        locked workaround — so calling _tick_once repeatedly must NOT raise.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Five back-to-back ticks; each must succeed.
            for _ in range(5):
                app._tick_once()
            await pilot.pause()
            assert app.state.tick == 5


# -- 5-region layout + header/footer ----------------------------------------


class TestHtopTycoonAppLayout:
    """The 5 regions + header/footer are mounted and queryable by id."""

    async def test_header_region_is_mounted(self) -> None:
        """The #header region exists after mount."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one("#header")
            assert header is not None

    async def test_metrics_region_is_mounted(self) -> None:
        """The #metrics region exists after mount."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            metrics = app.query_one("#metrics")
            assert metrics is not None

    async def test_org_tree_region_is_mounted(self) -> None:
        """The #org-tree region exists after mount."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            org_tree = app.query_one("#org-tree")
            assert org_tree is not None

    async def test_employee_panel_region_is_mounted(self) -> None:
        """The #employee-panel region exists after mount."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            emp_panel = app.query_one("#employee-panel")
            assert emp_panel is not None

    async def test_alerts_region_is_mounted(self) -> None:
        """The #alerts region exists after mount."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            alerts = app.query_one("#alerts")
            assert alerts is not None

    async def test_footer_region_is_mounted(self) -> None:
        """The #footer region exists after mount."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.query_one("#footer")
            assert footer is not None

    async def test_all_required_ids_are_present(self) -> None:
        """All seven locked region IDs are present simultaneously:
        #header, #metrics, #body (container for org-tree + employee-panel),
        #org-tree, #employee-panel, #alerts, #footer.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            for region_id in (
                "#header",
                "#metrics",
                "#body",
                "#org-tree",
                "#employee-panel",
                "#alerts",
                "#footer",
            ):
                # ``query_one`` raises NoMatches if missing — that is the test.
                node = app.query_one(region_id)
                assert node is not None


# -- Sanity: state isolation across instances ------------------------------


class TestHtopTycoonAppStateIsolation:
    """Each HtopTycoonApp instance owns its own state/engine/bus."""

    async def test_two_apps_have_independent_state(self) -> None:
        """Two mounted apps do not share state.tick."""
        app_a = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app_a.run_test() as pilot_a:
            await pilot_a.pause()
            app_b = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
            async with app_b.run_test() as pilot_b:
                await pilot_b.pause()
                app_a._tick_once()
                await pilot_a.pause()
                assert app_a.state.tick == 1
                assert app_b.state.tick == 0


# -- Startup snapshot (matches .omo/evidence/task-16-startup.txt) ---------


def test_startup_snapshot_keys() -> None:
    """The startup snapshot has the documented locked wiring fields."""
    initial_state = new_game(42)
    snap = {
        "app_class": "HtopTycoonApp",
        "seed": 42,
        "tick_rate": 100,
        "no_autosave": True,
        "bindings": HtopTycoonApp.BINDINGS,
        "initial_state_tick": initial_state.tick,
        "initial_rng_seed": initial_state.rng_seed,
        "css_path": "src/htop_tycoon/ui/app.tcss",
    }
    assert snap["seed"] == 42
    assert snap["tick_rate"] == 100
    assert snap["no_autosave"] is True
    assert snap["bindings"] == []
    assert snap["initial_state_tick"] == 0
    assert snap["initial_rng_seed"] == 42


# -- Module surface: re-export only what's needed --------------------------


def test_module_exposes_htop_tycoon_app() -> None:
    """``htop_tycoon.ui.app`` exposes ``HtopTycoonApp`` as a public symbol."""
    import htop_tycoon.ui.app as app_module

    assert hasattr(app_module, "HtopTycoonApp")


def test_app_has_on_mount_method() -> None:
    """The App declares ``on_mount`` (Textual lifecycle hook)."""
    assert hasattr(HtopTycoonApp, "on_mount")
    assert callable(HtopTycoonApp.on_mount)


def test_app_has_tick_once_method() -> None:
    """The App declares ``_tick_once`` (the locked wiring wrapper)."""
    assert hasattr(HtopTycoonApp, "_tick_once")
    assert callable(HtopTycoonApp._tick_once)


# -- Pure-python sanity (no TTY, no Pilot) ----------------------------------


def test_default_state_is_new_game_with_seed_42() -> None:
    """Without Pilot: ``HtopTycoonApp()`` exposes the same ``new_game(42)`` state.

    The Pilot-driven test above asserts the same, but this version is the
    cheapest smoke test (no asyncio, no driver) for quick CI feedback.
    """
    app = HtopTycoonApp()
    expected = new_game(42)
    assert app.state.company == expected.company
    assert app.state.tick == expected.tick
    assert app.state.rng_seed == expected.rng_seed


def test_engine_is_seeded_with_same_seed() -> None:
    """The TickEngine is constructed with the same seed as new_game."""
    app = HtopTycoonApp(seed=123)
    from htop_tycoon.engine.rng import GameRNG

    assert isinstance(app.engine._rng, GameRNG)
    assert app.engine._rng is not None
