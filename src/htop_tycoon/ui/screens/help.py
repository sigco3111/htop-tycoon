"""htop_tycoon.ui.screens.help — F1 Korean key-reference modal (T26).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 587-612:

- ``class HelpScreen(textual.screen.ModalScreen)`` renders the locked
  2-column key-reference table whose content matches the T22 footer
  labels AND the T24 BINDINGS action labels. The three sources of
  truth (T22 footer, T24 BINDINGS, T26 help screen) must agree
  byte-for-byte on the user-visible Korean labels; a drift surfaces
  as a failing test, not as a silent UI disagreement.

- **NO hardcoded promotion/demotion numbers.** The F7 / F8 lines
  are formatted as ``F7         승진 (+1 tier, 비용: {promotion_cost}₩)``
  where ``{promotion_cost}`` is filled from
  ``balance["employees"]["promotion_cost"]`` at render time via
  :func:`htop_tycoon.data.load_balance`. Same for ``{demotion_savings}``.
  This keeps all numeric game constants in ``balance.yaml`` per the
  AGENTS.md invariant.

- Pressing ``Q`` dismisses the modal; the underlying App is NOT
  closed. The App's screen stack pops the modal off and the host
  remains mounted (matches the EndingScreen T21 dismissal contract).

- The screen renders a single ``Static`` widget whose renderable is
  a :class:`rich.text.Text` body. Tests and Pilot introspection
  access the body via ``screen.renderable``.

- The locked table is defined as a tuple of literal lines plus two
  ``.format()``-able templates for the F7 / F8 lines. Column
  alignment is fixed at 11 characters (see :data:`_KEY_COLUMN_WIDTH`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.binding import Binding, BindingType
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.data import load_balance

if TYPE_CHECKING:
    from textual.app import ComposeResult

__all__ = ["HelpScreen"]


# ---------------------------------------------------------------------------
# Locked table — plan line 589-606. Column alignment is fixed at 11 chars:
# the key column (e.g. "F1", "F5 / t", "M / P / T", "Space", "↑ / ↓")
# is left-padded with spaces so every label starts at column index 11.
# ---------------------------------------------------------------------------

_KEY_COLUMN_WIDTH: int = 11

# F7 and F8 interpolate {promotion_cost} / {demotion_savings} from
# balance.yaml — they are NOT hardcoded per the plan MUST-NOT-DO.
_F7_TEMPLATE: str = "F7         승진 (+1 tier, 비용: {promotion_cost}₩)"
_F8_TEMPLATE: str = "F8         감봉 (-1 tier, 절약: {demotion_savings}₩)"

# The remaining 15 lines are literal — no balance interpolation.
# The blank line at index 8 separates the F-row block from the
# single-key block to match the plan's locked layout.
_TABLE_LINES: tuple[str, ...] = (
    "F1         도움말 (이 화면)",
    "F2         설정 / 게임 저장",
    "F3         직원 검색",
    "F4         필터 (이름/스킬 범위)",
    "F5 / t     조직도 트리 토글",
    "F6         정렬 사이클",
    _F7_TEMPLATE,
    _F8_TEMPLATE,
    "F9         해고 (퇴직금 지급)",
    "F10        종료 / 자발적 매각",
    "",
    "u          부서 필터 선택",
    "M / P / T  만족도 / 급여 / 입사순 정렬",
    "Space      직원 태그 (다중 선택)",
    "↑ / ↓      이동",
    "Enter      선택",
    "Q          모달 닫기 / 게임 종료",
)


class HelpScreen(ModalScreen[None]):
    """Modal that displays the locked Korean F-key + single-key reference.

    Construction:

    - No required arguments. The screen reads balance values via
      :func:`htop_tycoon.data.load_balance` at construction time so
      the renderable is finalized before mount (no async fetch, no
      placeholder state).

    Dismissal:

    - Pressing ``Q`` triggers :meth:`action_dismiss_screen`, which
      calls :meth:`ModalScreen.dismiss` with no result. The host App
      pops this modal off the screen stack; the App itself is NOT
      closed (matches the EndingScreen T21 contract).

    The widget is purely presentational: it reads ``balance`` and
    renders; the engine and event bus are untouched. AGENTS.md
    "State boundary" invariant is preserved.
    """

    DEFAULT_CSS: ClassVar[str] = """
    HelpScreen {
        align: center middle;
    }
    #help-content {
        content-align: left middle;
        width: auto;
        height: auto;
        padding: 1 2;
        border: thick $accent;
        background: $background;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "dismiss_screen", "Q: 닫기", show=True),
    ]

    def __init__(self) -> None:
        """Build the body eagerly so the renderable is valid before mount.

        Given: nothing (the screen is parameterless)
        When:  ``HelpScreen()`` is constructed
        Then:  ``self._body`` is a :class:`rich.text.Text` containing
               the locked table with balance values interpolated. The
               body is finalized in ``__init__`` (not deferred to
               ``compose``) so ``self.renderable`` is meaningful before
               the screen is mounted, which is what the Pilot tests
               rely on for substring assertions.
        """
        super().__init__()
        self._body: Text = self._build_text()

    @property
    def renderable(self) -> Text:
        """Expose the modal body for tests and external introspection.

        Screens in Textual do not have a canonical ``renderable``
        attribute (that name belongs to ``Static``). This property
        exists so the Pilot tests can assert on the modal's text
        content via ``str(screen.renderable)`` without descending
        into the inner ``Static`` via ``query_one``.
        """
        return self._body

    def compose(self) -> ComposeResult:
        """Yield a single ``Static`` whose renderable is the modal body.

        Centering is handled by ``DEFAULT_CSS`` (``align: center
        middle`` on the screen, ``content-align: left middle`` on
        the Static — left-aligned because the table is a 2-column
        key-reference, not a single-line centered title).
        """
        yield Static(self._body, id="help-content")

    # ------------------------------------------------------------------ actions

    def action_dismiss_screen(self) -> None:
        """Dismiss the modal in response to the Q binding.

        Calls :meth:`ModalScreen.dismiss` with no result. The host
        App's screen stack pops this modal; the App itself is NOT
        closed.
        """
        self.dismiss(None)

    # ------------------------------------------------------------------ internals

    def _build_text(self) -> Text:
        """Build the Rich ``Text`` renderable for the modal body.

        Reads ``balance["employees"]["promotion_cost"]`` and
        ``balance["employees"]["demotion_savings"]`` once via
        :func:`htop_tycoon.data.load_balance` and formats the F7 /
        F8 template strings. The remaining 15 lines are literal.

        All text is plain (no Rich markup); the colors come from
        the screen's CSS theme (``$accent`` border, ``$background``
        fill).
        """
        balance = load_balance()
        promotion_cost = int(balance["employees"]["promotion_cost"])
        demotion_savings = int(balance["employees"]["demotion_savings"])
        f7 = _F7_TEMPLATE.format(promotion_cost=promotion_cost)
        f8 = _F8_TEMPLATE.format(demotion_savings=demotion_savings)
        # Assemble: indices 0-5 literal, index 6 f7, index 7 f8,
        # then the remaining literal lines (F9, F10, blank, then
        # the single-key block).
        body = "\n".join(
            (
                _TABLE_LINES[0],  # F1
                _TABLE_LINES[1],  # F2
                _TABLE_LINES[2],  # F3
                _TABLE_LINES[3],  # F4
                _TABLE_LINES[4],  # F5 / t
                _TABLE_LINES[5],  # F6
                f7,  # F7 with promotion_cost
                f8,  # F8 with demotion_savings
                _TABLE_LINES[8],  # F9
                _TABLE_LINES[9],  # F10
                *_TABLE_LINES[10:],  # blank + single-key block
            )
        )
        return Text(body)
