"""htop_tycoon.ui.screens.ending_screen — 5-endings review modal (T21).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 504-513:

- ``class EndingScreen(textual.screen.ModalScreen)`` accepts an
  ``EndingType`` and the run's ``GameState`` to render summary stats.
- Renders centered text containing the Korean ending title
  (from ``endings.yaml``), Korean flavor summary, and 4 summary stats
  (final cash, market cap, weeks played, employee count).
- A "Press Q to restart" footer instructs the user on dismissal.
- Korean flavor text is loaded via :func:`htop_tycoon.data.load_endings`;
  the source-of-truth YAML MUST stay authoritative. This module MUST NOT
  hardcode the Korean strings.
- Pressing ``Q`` dismisses the modal; the underlying App continues to
  run in a "game over" state — the App is NOT closed.

The 4 summary stats are intentionally fixed (cash / market cap / weeks /
employees) so the player always sees the same dashboard across endings.
Per-ending narrative labels live in ``endings.yaml`` ``stats_labels``;
those are reserved for future "ending-specific" expansions (T33+).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.binding import Binding, BindingType
from textual.screen import ModalScreen
from textual.widgets import Static

from htop_tycoon.data import load_endings
from htop_tycoon.domain.ending import EndingType
from htop_tycoon.domain.state import GameState

if TYPE_CHECKING:
    from textual.app import ComposeResult

__all__ = ["EndingScreen"]


# ---------------------------------------------------------------------------
# Locked Korean labels for the 4 fixed summary stats.
#
# These are intentionally stable across all 5 endings so the review modal
# reads as a uniform dashboard. Per-ending narrative labels (e.g. "상장까지"
# for IPO) are available in ``endings.yaml`` ``stats_labels`` for future
# ending-specific narrative expansions; the modal does not consume them today.
# ---------------------------------------------------------------------------

_LABEL_WEEKS: str = "생존 기간"
_LABEL_CASH: str = "최종 자금"
_LABEL_MARKET_CAP: str = "최종 시가총액"
_LABEL_EMPLOYEES: str = "최종 직원 수"
_UNIT_WEEKS: str = "주"
_UNIT_EMPLOYEES: str = "명"

# Locked footer copy. The English "Press Q to restart" is the literal from
# the plan ("Press Q to restart footer"); keeping it English here makes the
# spec verification unambiguous and matches the htop-style footer contract.
_FOOTER_TEXT: str = "Press Q to restart"

# Visual rule length for the underline beneath the Korean title. The
# minimum keeps short titles (e.g. "파산") from looking under-decorated;
# the multiplier pads longer titles (e.g. "상장 성공") to a similar width.
_RULE_MIN_LEN: int = 10
_RULE_MULTIPLIER: int = 2


class EndingScreen(ModalScreen[None]):
    """Modal that displays the Korean ending title + summary + final stats.

    Construction:

    - ``ending_type``: which of the 5 locked ``EndingType`` values to render.
    - ``state``: the final ``GameState`` for the run; used to read cash,
      market cap, tick (= weeks played), and employee count.

    The modal emits no result on dismiss (``ModalScreen[None]``); the host
    App simply resumes its "game over" state. Pressing ``Q`` triggers
    :meth:`action_dismiss_screen`, which calls :meth:`ModalScreen.dismiss`.

    The widget is purely presentational: it reads state but does NOT
    mutate it. AGENTS.md "State boundary" invariant is preserved.
    """

    DEFAULT_CSS: ClassVar[str] = """
    EndingScreen {
        align: center middle;
    }
    #ending-content {
        content-align: center middle;
        width: 60;
        height: auto;
        padding: 1 2;
        border: thick $accent;
        background: $background;
    }
    """

    # Q dismisses the modal. ModalScreen bindings take precedence over the
    # App's BINDINGS, so this Q is local to the modal and does NOT leak to
    # the underlying App. (T24 will add the App's BINDINGS for the live game.)
    # Match the parent's declared BINDINGS type so mypy accepts the override.
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "dismiss_screen", "Q: 닫기", show=True),
    ]

    def __init__(self, ending_type: EndingType, state: GameState) -> None:
        """Store the ending type + final state for render-time lookup.

        Given: ``ending_type`` (one of the 5 ``EndingType`` members),
               ``state`` (the final ``GameState`` to summarize)
        When: ``EndingScreen(ending_type, state)`` is constructed
        Then: ``self._ending_type`` and ``self._state`` are stored; the
              screen is not yet mounted (compose() does the actual
              render).
        """
        super().__init__()
        self._ending_type: EndingType = ending_type
        self._state: GameState = state
        # Body is built eagerly so self.renderable is valid before mount.
        self._body: Text = self._build_text()

    @property
    def renderable(self) -> Text:
        """Expose the modal body for tests and external introspection.

        Screens in Textual do not have a canonical ``renderable``
        attribute (that name belongs to ``Static``). This property
        exists so the Pilot tests can assert on the modal's text
        content via ``str(screen.renderable)`` without having to
        descend into the inner ``Static`` via ``query_one``.
        """
        return self._body

    def compose(self) -> ComposeResult:
        """Yield a single ``Static`` whose renderable is the modal body.

        The body is a :class:`rich.text.Text` built from
        :func:`load_endings` (title_ko + summary_ko) plus the 4 fixed
        summary stats read from ``self._state``. Centering is handled
        by ``DEFAULT_CSS`` (``align: center middle`` on the screen,
        ``content-align: center middle`` on the Static).
        """
        yield Static(self._body, id="ending-content")

    # ------------------------------------------------------------------ actions

    def action_dismiss_screen(self) -> None:
        """Dismiss the modal in response to the Q binding.

        Calls :meth:`ModalScreen.dismiss` with no result. The host App's
        screen stack pops this modal; the App itself is NOT closed
        (the "Press Q to restart" footer is a misnomer: Q dismisses the
        review modal; restarting the run is a separate App-level action
        not yet wired in T21).
        """
        self.dismiss(None)

    # ------------------------------------------------------------------ internals

    def _build_text(self) -> Text:
        """Build the Rich ``Text`` renderable for the modal body.

        Sections (top to bottom):

        1. Korean title (``endings.yaml`` ``title_ko``)
        2. Visual underline rule
        3. Korean summary (``endings.yaml`` ``summary_ko``)
        4. Blank line
        5. 4 fixed summary stats: weeks / cash / market_cap / employees
        6. Blank line
        7. ``Press Q to restart`` footer

        All text is plain (no Rich markup); the colors come from the
        screen's CSS theme (``$accent`` border, ``$background`` fill).
        """
        endings = load_endings()
        entry = endings[self._ending_type.value]
        title = str(entry["title_ko"])
        summary = str(entry["summary_ko"])

        rule = "=" * max(_RULE_MIN_LEN, len(title) * _RULE_MULTIPLIER)

        state = self._state
        weeks_line = f"{_LABEL_WEEKS}: {state.tick}{_UNIT_WEEKS}"
        cash_line = f"{_LABEL_CASH}: {state.company.cash}"
        market_cap_line = f"{_LABEL_MARKET_CAP}: {state.company.market_cap}"
        employees_line = f"{_LABEL_EMPLOYEES}: {len(state.employees)}{_UNIT_EMPLOYEES}"

        body = "\n".join(
            [
                title,
                rule,
                summary,
                "",
                weeks_line,
                cash_line,
                market_cap_line,
                employees_line,
                "",
                _FOOTER_TEXT,
            ]
        )
        return Text(body)
