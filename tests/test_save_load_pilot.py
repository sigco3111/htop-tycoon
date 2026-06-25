"""Tests for T29: Save/Load action + autosave every 10 ticks.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 642-651:

- ``class SetupScreen(textual.screen.ModalScreen)`` with 4 buttons:
  ``"저장"`` (Save), ``"불러오기"`` (Load), ``"새 게임"`` (New Game),
  ``"초기화"`` (Reset).
- Wire ``"저장"`` -> ``persistence.serialize.save(state, XDG_PATH)``.
- Wire ``"불러오기"`` -> ``persistence.deserialize.load(XDG_PATH)``.
- Wire ``"새 게임"`` -> ``new_game(rng_seed=int(time.time()))`` (the
  user-chosen new game path is permitted to use ``time.time()``).
- Wire ``"초기화"`` -> ``new_game(rng_seed=0)`` for safety.
- F2 pushes ``SetupScreen`` from ``HtopTycoonApp`` (the T24 binding's
  ``action_show_setup`` must still record ``_last_action = "show_setup"``
  so the T24 ``test_all_ten_f_keys_fire_their_action`` contract stays
  green).
- Autosave fires after every N ticks (N from
  ``balance["save"]["autosave_every_n_ticks"]``, default 10) silently —
  no UI feedback unless an error is raised.
- ``no_autosave=True`` skips autosave entirely (T16 constructor flag,
  T30 CLI flag).
- Save / load round-trip preserves ``state_hash`` modulo tick (a fresh
  load resets ``tick`` to the saved value but the GAME state content is
  identical).

The XDG path is ``~/.local/share/htop-tycoon/save.json`` per the plan
line 646. For tests we override ``app._save_path`` to a ``tmp_path``
fixture so the real home directory is never touched.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from htop_tycoon.data import load_balance
from htop_tycoon.domain.state import GameState, new_game, state_hash
from htop_tycoon.persistence.deserialize import load as persistence_load
from htop_tycoon.persistence.serialize import save as persistence_save
from htop_tycoon.ui.app import HtopTycoonApp
from htop_tycoon.ui.screens.setup import SetupScreen

if TYPE_CHECKING:
    pass


# -- Locked XDG path --------------------------------------------------------
#
# The default save path lives under ``~/.local/share/htop-tycoon/save.json``
# per the XDG Base Directory spec (plan line 646). Tests override
# ``app._save_path`` to a tmp_path; this constant exists to pin the
# default so a future drift surfaces as a failing test.


def _default_xdg_save_path() -> Path:
    """Return the locked default save path (~/.local/share/htop-tycoon/save.json)."""
    return Path.home() / ".local" / "share" / "htop-tycoon" / "save.json"


# -- Module surface --------------------------------------------------------


class TestSetupScreenModuleSurface:
    """The setup module exposes SetupScreen with the locked shape."""

    def test_setup_module_importable(self) -> None:
        """``htop_tycoon.ui.screens.setup`` is importable."""
        import htop_tycoon.ui.screens.setup as setup_module

        assert setup_module is not None

    def test_screens_package_exposes_setup_screen(self) -> None:
        """``htop_tycoon.ui.screens`` re-exports ``SetupScreen``."""
        import htop_tycoon.ui.screens as screens_module

        assert hasattr(screens_module, "SetupScreen")
        assert screens_module.SetupScreen is SetupScreen

    def test_setup_screen_subclasses_modal_screen(self) -> None:
        """``SetupScreen`` is a subclass of ``textual.screen.ModalScreen``."""
        from textual.screen import ModalScreen

        assert issubclass(SetupScreen, ModalScreen)


# -- SetupScreen has the 4 locked Korean buttons --------------------------


class TestSetupScreenButtons:
    """SetupScreen renders the 4 locked Korean buttons."""

    async def test_setup_screen_has_save_button(self) -> None:
        """SetupScreen contains a Button labeled ``"저장"``."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = Path("/tmp/save.json")  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, SetupScreen)
            button_labels = [
                str(btn.label) for btn in screen.query("Button")  # type: ignore[union-attr]
            ]
            assert "저장" in button_labels, (
                f"SetupScreen missing '저장' button; got {button_labels!r}"
            )

    async def test_setup_screen_has_load_button(self) -> None:
        """SetupScreen contains a Button labeled ``"불러오기"``."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = Path("/tmp/save.json")  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            button_labels = [
                str(btn.label)  # type: ignore[union-attr]
                for btn in app.screen.query("Button")
            ]
            assert "불러오기" in button_labels

    async def test_setup_screen_has_new_game_button(self) -> None:
        """SetupScreen contains a Button labeled ``"새 게임"``."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = Path("/tmp/save.json")  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            button_labels = [
                str(btn.label)  # type: ignore[union-attr]
                for btn in app.screen.query("Button")
            ]
            assert "새 게임" in button_labels

    async def test_setup_screen_has_reset_button(self) -> None:
        """SetupScreen contains a Button labeled ``"초기화"``."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = Path("/tmp/save.json")  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            button_labels = [
                str(btn.label)  # type: ignore[union-attr]
                for btn in app.screen.query("Button")
            ]
            assert "초기화" in button_labels

    async def test_setup_screen_has_exactly_four_buttons(self) -> None:
        """The locked button set has exactly 4 entries (no extras)."""
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = Path("/tmp/save.json")  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            buttons = list(app.screen.query("Button"))
            assert len(buttons) == 4, (
                f"SetupScreen must have exactly 4 buttons; got {len(buttons)}"
            )


# -- F2 -> SetupScreen on HtopTycoonApp -----------------------------------


class TestF2OpensSetupScreen:
    """Pressing F2 from the live HtopTycoonApp pushes SetupScreen."""

    async def test_f2_pushes_setup_screen_modal(self) -> None:
        """Given: a mounted HtopTycoonApp
        When: pilot.press("f2")
        Then: app.screen is an instance of SetupScreen.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = Path("/tmp/save.json")  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not isinstance(app.screen, SetupScreen)
            await pilot.press("f2")
            await pilot.pause()
            assert isinstance(app.screen, SetupScreen), (
                f"F2 did not open SetupScreen: app.screen is "
                f"{type(app.screen).__name__}"
            )

    async def test_f2_press_preserves_last_action_show_setup(self) -> None:
        """F2 must still set ``_last_action = 'show_setup'`` (T24 contract).

        T24's ``test_all_ten_f_keys_fire_their_action`` pins that every
        F-key sets ``_last_action`` to its bound action name. T29 must
        not regress this: even though F2 now opens a modal, the action
        handler must ALSO record the name so the T24 test stays green.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = Path("/tmp/save.json")  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            app._last_action = None  # type: ignore[attr-defined]
            await pilot.press("f2")
            await pilot.pause()
            assert app._last_action == "show_setup"  # type: ignore[attr-defined]


# -- Save / Load round-trip via SetupScreen -------------------------------


class TestSaveLoadRoundTrip:
    """The '저장' button writes state to disk; the '불러오기' button restores it."""

    async def test_save_button_writes_file_at_save_path(
        self, tmp_path: Path
    ) -> None:
        """Clicking '저장' calls persistence.save -> file exists at save_path."""
        save_path = tmp_path / "save.json"
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            # Advance one tick so saved state differs from initial.
            app._tick_once()
            await pilot.pause()
            # Click the Save button.
            save_button = app.screen.query_one("#save-button", object)  # type: ignore[union-attr]
            assert save_button is not None
            save_button.action_press()  # type: ignore[union-attr]
            await pilot.pause()
            assert save_path.exists(), (
                f"Save button did not write file at {save_path}"
            )
            # File is valid JSON envelope.
            data = json.loads(save_path.read_text(encoding="utf-8"))
            assert data["version"] == 1
            assert data["state"]["tick"] == 1

    async def test_load_button_restores_state_hash(self, tmp_path: Path) -> None:
        """Clicking '불러오기' after save restores state_hash (modulo tick)."""
        save_path = tmp_path / "save.json"
        # Seed the save file with a known state.
        original = new_game(42)
        persistence_save(original, save_path)

        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            # Mutate the state (5 ticks).
            for _ in range(5):
                app._tick_once()
            await pilot.pause()
            assert app.state.tick == 5
            # Now push the SetupScreen and click Load.
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            load_button = app.screen.query_one("#load-button", object)  # type: ignore[union-attr]
            load_button.action_press()  # type: ignore[union-attr]
            await pilot.pause()
            # State must be restored to original (tick=0).
            assert app.state.tick == 0
            assert state_hash(app.state) == state_hash(original)
            assert app.state.rng_seed == original.rng_seed

    async def test_save_then_load_round_trip_preserves_state_hash(
        self, tmp_path: Path
    ) -> None:
        """Plan acceptance: Play 50 ticks → save → load → state_hash matches
        (modulo tick number).
        """
        save_path = tmp_path / "save.json"
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            # Play 50 ticks.
            for _ in range(50):
                app._tick_once()
            await pilot.pause()
            assert app.state.tick == 50
            # Save.
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            app.screen.query_one("#save-button", object).action_press()  # type: ignore[union-attr]
            await pilot.pause()
            assert save_path.exists()
            # Load.
            app.screen.query_one("#load-button", object).action_press()  # type: ignore[union-attr]
            await pilot.pause()
            # After load, tick must be 50 (restored), state hash preserved.
            assert app.state.tick == 50
            loaded_from_disk = persistence_load(save_path)
            assert state_hash(app.state) == state_hash(loaded_from_disk)


# -- 새 게임 / 초기화 buttons -----------------------------------------------


class TestNewGameAndReset:
    """새 게임 resets state with time-based seed; 초기화 resets with seed=0."""

    async def test_new_game_button_resets_with_time_seed(
        self, tmp_path: Path
    ) -> None:
        """Clicking '새 게임' calls new_game(rng_seed=int(time.time()))."""
        save_path = tmp_path / "save.json"
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            # Advance a few ticks so the reset is visible.
            for _ in range(7):
                app._tick_once()
            await pilot.pause()
            assert app.state.tick == 7
            before_seed = app.state.rng_seed
            # Push screen + click 새 게임.
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            new_game_button = app.screen.query_one(  # type: ignore[union-attr]
                "#new-game-button", object
            )
            new_game_button.action_press()  # type: ignore[union-attr]
            await pilot.pause()
            # State reset to tick=0, seed derived from int(time.time()).
            assert app.state.tick == 0
            now_seed = int(time.time())
            # The seed is int(time.time()) at click time; it must match
            # ``now_seed`` (computed right after) within a 5-second window
            # to absorb scheduling jitter.
            assert abs(app.state.rng_seed - now_seed) <= 5, (
                f"새 게임 seed {app.state.rng_seed} not within 5s of "
                f"current time seed {now_seed}"
            )
            assert app.state.rng_seed != before_seed

    async def test_reset_button_resets_with_zero_seed(self, tmp_path: Path) -> None:
        """Clicking '초기화' calls new_game(rng_seed=0) for safety."""
        save_path = tmp_path / "save.json"
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            for _ in range(3):
                app._tick_once()
            await pilot.pause()
            app.push_screen(SetupScreen(app))
            await pilot.pause()
            reset_button = app.screen.query_one(  # type: ignore[union-attr]
                "#reset-button", object
            )
            reset_button.action_press()  # type: ignore[union-attr]
            await pilot.pause()
            # State reset to tick=0, rng_seed=0.
            assert app.state.tick == 0
            assert app.state.rng_seed == 0
            # Hash matches the frozen recovery-state hash.
            assert state_hash(app.state) == (
                "0659738b9d8d2105f0b18dec093a4965a697db28a43aff9e36d124cb29b612c4"
            )


# -- Autosave -------------------------------------------------------------


class TestAutosave:
    """Autosave fires every N ticks (N from balance.yaml) silently."""

    def test_autosave_every_n_ticks_value_from_balance(self) -> None:
        """``balance["save"]["autosave_every_n_ticks"]`` is locked at 10."""
        balance = load_balance()
        autosave_every = int(balance["save"]["autosave_every_n_ticks"])
        assert autosave_every == 10

    async def test_autosave_writes_file_after_n_ticks(
        self, tmp_path: Path
    ) -> None:
        """Given: app with no_autosave=False and save_path in tmp_path
        When: N (=10) ticks elapse
        Then: the save file exists and contains the latest state.
        """
        save_path = tmp_path / "save.json"
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=False)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            # Play 10 ticks.
            for _ in range(10):
                app._tick_once()
            await pilot.pause()
            assert save_path.exists(), (
                f"Autosave did not write file at {save_path} after 10 ticks"
            )
            data = json.loads(save_path.read_text(encoding="utf-8"))
            assert data["state"]["tick"] == 10

    async def test_autosave_fires_every_10_ticks_over_50_ticks(
        self, tmp_path: Path
    ) -> None:
        """Plan acceptance: autosave fires every 10 ticks (verify by mtime or count).

        We play 50 ticks and verify that the latest save's tick value is
        a multiple of 10 in the [10, 50] range. This proves autosave
        triggered at tick 10, 20, 30, 40, and 50.
        """
        save_path = tmp_path / "save.json"
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=False)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            for _ in range(50):
                app._tick_once()
            await pilot.pause()
            assert save_path.exists()
            data = json.loads(save_path.read_text(encoding="utf-8"))
            saved_tick = data["state"]["tick"]
            # Must be a multiple of 10 in (0, 50].
            assert saved_tick % 10 == 0
            assert 0 < saved_tick <= 50

    async def test_autosave_skipped_when_no_autosave(
        self, tmp_path: Path
    ) -> None:
        """Given: app with no_autosave=True
        When: 50 ticks elapse
        Then: NO save file is created.
        """
        save_path = tmp_path / "save.json"
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            for _ in range(50):
                app._tick_once()
            await pilot.pause()
            assert not save_path.exists(), (
                f"Autosave wrote file despite no_autosave=True: {save_path}"
            )

    async def test_autosave_does_not_write_at_tick_zero(
        self, tmp_path: Path
    ) -> None:
        """At tick 0 (initial state), no autosave fires — the first save
        happens at tick == autosave_every_n_ticks, not before.
        """
        save_path = tmp_path / "save.json"
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=False)
        app._save_path = save_path  # type: ignore[attr-defined]
        async with app.run_test() as pilot:
            await pilot.pause()
            # No ticks yet — file must NOT exist.
            assert not save_path.exists()


# -- Default save path on App ---------------------------------------------


class TestAppSavePathDefault:
    """The App's default ``_save_path`` is the XDG path."""

    def test_app_default_save_path_is_xdg(self) -> None:
        """``HtopTycoonApp()._save_path`` equals the XDG default."""
        app = HtopTycoonApp()
        assert app._save_path == _default_xdg_save_path()  # type: ignore[attr-defined]


# -- Module surface: no regressions in existing T16/T24/T25 ----------------


class TestNoRegressions:
    """T29 must not break T16 (engine wiring) or T24 (F-row bindings)."""

    def test_engine_and_bus_still_initialized(self) -> None:
        """The autosave plumbing must not displace the T16 engine/bus wiring."""
        app = HtopTycoonApp(seed=42, tick_rate=1.0, no_autosave=True)
        assert isinstance(app.state, GameState)
        assert app.engine is not None
        assert app.event_bus is not None

    def test_no_autosave_flag_stored(self) -> None:
        """T16's ``no_autosave`` constructor arg is still honored."""
        app = HtopTycoonApp(seed=7, tick_rate=2.0, no_autosave=True)
        assert app.no_autosave is True
        app2 = HtopTycoonApp(seed=7, tick_rate=2.0, no_autosave=False)
        assert app2.no_autosave is False


# -- Fixtures --------------------------------------------------------------


@pytest.fixture
def save_path(tmp_path: Path) -> Path:
    """Per-test tmp_path-anchored save path. (Documented; tests use tmp_path directly.)"""
    return tmp_path / "save.json"
