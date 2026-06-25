"""htop_tycoon.ui.screens.setup — F2 Setup/Save/Load modal (T29).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 642-651:

- ``class SetupScreen(textual.screen.ModalScreen)`` exposes 4 locked
  Korean buttons arranged vertically:

      [저장]      -> persistence.serialize.save(state, XDG_PATH)
      [불러오기]  -> persistence.deserialize.load(XDG_PATH)
      [새 게임]   -> new_game(rng_seed=int(time.time()))
      [초기화]    -> new_game(rng_seed=0)   (safe; deterministic)

  ``새 게임`` derives the seed from ``time.time()`` because the user
  EXPLICITLY chose to start a fresh game (a user action — distinct from
  the auto-recovery path, which uses the fixed ``CORRUPTION_RECOVERY_SEED``
  per AGENTS.md and T28). ``초기화`` uses seed=0 as a paranoid reset:
  deterministic and reproducible.

- The screen is parameterless from the user's perspective: it captures
  the ``HtopTycoonApp`` instance at construction and reads
  ``app.state`` (for save) and ``app._save_path`` (for the on-disk
  path). Tests override ``app._save_path`` to a ``tmp_path`` so the
  real ``~/.local/share/htop-tycoon/save.json`` is never touched.

- Each button click mutates ``app.state`` (Save persists, Load replaces,
  새 게임 / 초기화 reset). Per AGENTS.md "State boundary" invariant, the
  engine is the only writer — but persistence save/load is the
  documented chokepoint (T27/T28) and reset (새 게임 / 초기화) IS the
  start of a fresh engine run, which the App owns.

- After a state-changing click the modal auto-dismisses so the user
  sees the new game state immediately. Save does NOT dismiss (the user
  may want to keep the screen open while saving multiple times).

- Buttons have stable ``id`` attributes (``#save-button``,
  ``#load-button``, ``#new-game-button``, ``#reset-button``) so Pilot
  tests can target them by ID without coupling to label text.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button

from htop_tycoon.domain.state import new_game
from htop_tycoon.persistence.deserialize import load as persistence_load
from htop_tycoon.persistence.serialize import save as persistence_save

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from htop_tycoon.ui.app import HtopTycoonApp


__all__ = ["SetupScreen"]


# ---------------------------------------------------------------------------
# Locked button labels (Korean, plan line 643). These are the canonical
# strings referenced by tests and the help screen (T26) — keep in sync.
# ---------------------------------------------------------------------------

_LABEL_SAVE: str = "저장"
_LABEL_LOAD: str = "불러오기"
_LABEL_NEW_GAME: str = "새 게임"
_LABEL_RESET: str = "초기화"


# ---------------------------------------------------------------------------
# F-row pass-through bindings.
#
# WHY THIS EXISTS: Textual's ``_modal_binding_chain`` (screen.py line 371-378)
# excludes the App's BINDINGS when a ModalScreen is on top. Without these
# pass-throughs, pressing F3..F10 while SetupScreen is up would be silently
# consumed (never reaching the App). The T24 test
# ``test_all_ten_f_keys_fire_their_action`` iterates F1..F10 in sequence and
# asserts ``_last_action == binding.action`` after each press — T29 must
# not regress that contract, hence the explicit delegation.
# ---------------------------------------------------------------------------

_PASS_THROUGH_ACTIONS: tuple[str, ...] = (
    "show_help",
    "search",
    "filter",
    "toggle_tree",
    "cycle_sort",
    "promote_selected",
    "demote_selected",
    "fire_selected",
    "quit_or_sell",
)


class SetupScreen(ModalScreen[None]):
    """F2 modal: Save / Load / New Game / Reset (4 locked Korean buttons).

    Captures the live ``HtopTycoonApp`` at construction; reads/writes
    ``app.state`` and ``app._save_path``. Q / Escape dismiss; F1/F3..F10
    dismiss-then-delegate to the App so the T24 F-row contract stays
    green. ``app.state`` is mutated directly because persistence
    ``save``/``load`` and ``new_game`` are the documented state
    transitions (engine chokepoint).
    """

    DEFAULT_CSS: ClassVar[str] = """
    SetupScreen {
        align: center middle;
    }
    #setup-content {
        content-align: center middle;
        width: 40;
        height: auto;
        padding: 1 2;
        border: thick $accent;
        background: $background;
    }
    #setup-buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }
    Button {
        width: 100%;
        margin: 0 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "dismiss_screen", "Q: 닫기", show=True),
        Binding("escape", "dismiss_screen", "Esc: 닫기", show=False),
        Binding("f2", "passthrough_show_setup", show=False),
        *(
            Binding(key, f"passthrough_{action}", show=False)
            for key, action in zip(
                ("f1", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10"),
                _PASS_THROUGH_ACTIONS,
                strict=True,
            )
        ),
    ]

    def __init__(self, app: HtopTycoonApp) -> None:
        super().__init__()
        self._app = app

    # ------------------------------------------------------------------ API

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-content"):
            with Vertical(id="setup-buttons"):
                yield Button(_LABEL_SAVE, id="save-button")
                yield Button(_LABEL_LOAD, id="load-button")
                yield Button(_LABEL_NEW_GAME, id="new-game-button")
                yield Button(_LABEL_RESET, id="reset-button")

    # ------------------------------------------------------------------ actions

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "save-button":
            self._handle_save()
        elif button_id == "load-button":
            self._handle_load()
        elif button_id == "new-game-button":
            self._handle_new_game()
        elif button_id == "reset-button":
            self._handle_reset()

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def action_passthrough_show_setup(self) -> None:
        self.dismiss(None)
        self._app.action_show_setup()

    def action_passthrough_show_help(self) -> None:
        self.dismiss(None)
        self._app.action_show_help()

    def action_passthrough_search(self) -> None:
        self.dismiss(None)
        self._app.action_search()

    def action_passthrough_filter(self) -> None:
        self.dismiss(None)
        self._app.action_filter()

    def action_passthrough_toggle_tree(self) -> None:
        self.dismiss(None)
        self._app.action_toggle_tree()

    def action_passthrough_cycle_sort(self) -> None:
        self.dismiss(None)
        self._app.action_cycle_sort()

    def action_passthrough_promote_selected(self) -> None:
        self.dismiss(None)
        self._app.action_promote_selected()

    def action_passthrough_demote_selected(self) -> None:
        self.dismiss(None)
        self._app.action_demote_selected()

    def action_passthrough_fire_selected(self) -> None:
        self.dismiss(None)
        self._app.action_fire_selected()

    def action_passthrough_quit_or_sell(self) -> None:
        self.dismiss(None)
        self._app.action_quit_or_sell()

    # ------------------------------------------------------------------ handlers

    def _handle_save(self) -> None:
        save_path: Path = self._app._save_path
        try:
            persistence_save(self._app.state, save_path)
            self.app.notify(f"저장 완료: {save_path}")
        except OSError as exc:
            self.app.notify(f"저장 실패: {exc}")

    def _handle_load(self) -> None:
        save_path: Path = self._app._save_path
        loaded = persistence_load(save_path)
        self._app.state = loaded
        self.dismiss(None)

    def _handle_new_game(self) -> None:
        new_state = new_game(int(time.time()))
        self._app.state = new_state
        self.dismiss(None)

    def _handle_reset(self) -> None:
        new_state = new_game(0)
        self._app.state = new_state
        self.dismiss(None)
