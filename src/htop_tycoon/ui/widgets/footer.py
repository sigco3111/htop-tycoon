"""htop_tycoon.ui.widgets.footer — HtopFooter F-key + single-key hints (T22).

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 515-524:

- ``HtopFooter`` subclasses ``textual.widgets.Footer`` and shows F-key
  hints matching T24 BINDINGS EXACTLY. The locked F-row is::

      F1도움말 F2설정 F3검색 F4필터 F5트리 F6정렬 F7승진 F8감봉 F9해고 F10매각

  (single source of truth; T22 + T24 + T26 must agree).

- The single-key row is::

      t:트리 u:부서필터 m:만족도 s:급여 i:입사 ↑↓:이동 Space:태그 p:일시정지 d:위임

- The footer MUST NOT use htop's original English F-key labels
  (F7Nice-, F8Nice+, F9Kill, F10Quit) — those describe real htop behavior
  (process nice values, signal kill, quit), not this game's actions.
- ``show_command_palette=False`` is set in ``__init__`` because the locked
  footer has no command palette binding (T24's F10 binding is for 매각,
  not for a palette shortcut).

The locked strings are exposed as module-level constants
(:data:`F_ROW`, :data:`SINGLE_KEY_ROW`) so T26 (README/도움말) can import
them as the canonical source. A drift between T22 and T26 (or between T22
and T24 BINDINGS) is a contract violation and must surface as a failing
test, not as a silent disagreement.
"""

from __future__ import annotations

from typing import Any

from textual.widgets import Footer, Static

__all__ = ["F_ROW", "HtopFooter", "SINGLE_KEY_ROW"]


# Locked F-row string — plan line 516. This is the single source of truth
# for T22 + T24 + T26. The format is space-separated ``F<n><label>`` tokens
# (no padding between adjacent tokens), matching the plan's example.
F_ROW: str = (
    "F1도움말 F2설정 F3검색 F4필터 F5트리 "
    "F6정렬 F7승진 F8감봉 F9해고 F10매각"
)


# Locked single-key row string — plan line 516. Same format as F_ROW,
# space-separated key-label pairs. The arrows ``↑↓`` are the lock-step
# symbol used throughout the Korean UI.
#
# Wave 7 amendments (all keys are lowercase):
# - ``P:급여`` → ``s:급여`` (mnemonic for "salary").
# - ``T:입사`` → ``i:입사`` (mnemonic for "i/psa" = hired; ``t`` was
#   already taken by ``toggle_tree``).
# - The trailing ``p:일시정지`` is the Wave 7 pause/resume shortcut
#   (lowercase ``p`` → toggle_pause).
# - ``M:만족도`` display → ``m:만족도`` for visual consistency with
#   the lowercase-only convention (the underlying binding was
#   already lowercase).
# - The trailing ``d:위임`` is the Wave 7 delegation shortcut
#   (lowercase ``d`` → delegate selected employee).
SINGLE_KEY_ROW: str = (
    "t:트리 u:부서필터 m:만족도 s:급여 i:입사 ↑↓:이동 Space:태그 p:일시정지 d:위임"
)


class HtopFooter(Footer):
    """htop-styled two-row footer with locked Korean F-key + single-key hints.

    Row 1: the F-row (F1..F10 with game-action labels).
    Row 2: the single-key row (t, u, M, P, T, ↑↓, Space).

    The widget subclasses ``textual.widgets.Footer`` so it inherits the
    standard Footer CSS contract (``dock: bottom``), but it overrides
    ``compose`` to emit the two locked Static rows instead of the
    auto-generated FooterKey widgets. This guarantees the rendered text
    matches the locked source-of-truth strings byte-for-byte, independent
    of the BINDINGS plumbing (which T24 will wire at the App level).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize with ``show_command_palette=False`` and override height.

        Given: standard ``Footer`` constructor kwargs (children, name, id,
               classes, disabled)
        When:  ``HtopFooter(...)`` is constructed
        Then:  ``show_command_palette`` defaults to ``False`` (the locked
               footer has no palette shortcut), and the widget's height is
               overridden to ``2`` to fit both rows even when the global
               CSS rule ``#footer { height: 1 }`` is in effect.
        """
        # Suppress the default ``?`` command-palette hint; this footer
        # is a fixed display, not an interactive palette launcher.
        kwargs.setdefault("show_command_palette", False)
        super().__init__(*args, **kwargs)
        # Override the locked CSS ``#footer { height: 1 }`` so the two
        # rows are fully visible. ``styles.height = 2`` is a programmatic
        # style assignment that takes precedence over the external CSS
        # rule for this widget instance.
        self.styles.height = 2

    def compose(self) -> Any:
        """Yield two Static children: F-row + single-key row.

        Replaces the inherited ``Footer.compose`` (which would otherwise
        auto-generate ``FooterKey`` widgets from app-level BINDINGS).
        Yielding two plain ``Static`` children pins the rendered text to
        the locked source-of-truth strings.
        """
        yield Static(F_ROW)
        yield Static(SINGLE_KEY_ROW)
