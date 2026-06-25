"""htop_tycoon.bindings.registry — F1-F10 binding table for the App.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 537-561 (T24):

- ``register_f_bindings()`` returns a fresh ``list[Binding]`` of length 10.
- Keys are lowercase per Textual's Binding API (``f1`` not ``F1``).
- Actions follow the locked names: ``show_help``, ``show_setup``, ``search``,
  ``filter``, ``toggle_tree``, ``cycle_sort``, ``promote_selected``,
  ``demote_selected``, ``fire_selected``, ``quit_or_sell``.
- Korean descriptions are the user-visible footer labels.

The function returns a fresh list each call so callers can extend it
without affecting other call sites. ``HtopTycoonApp.BINDINGS`` invokes it
once at class-body evaluation time; tests may invoke it any number of
times without state bleed-through.

Anti-patterns explicitly rejected here:
- Hardcoding ``Binding(\"F1\", ...)`` — Textual's Binding API normalizes keys
  to lowercase, but using the locked lowercase form ``f1`` makes the spec
  and the implementation match exactly without runtime normalization.
- Mutating a shared default list — would couple unrelated callers.
"""

from __future__ import annotations

from textual.binding import Binding

__all__ = ["register_f_bindings"]


def register_f_bindings() -> list[Binding]:
    """Return the locked F1-F10 binding list.

    Given: nothing (pure function; no parameters)
    When:  called (any number of times)
    Then:  returns a fresh ``list[Binding]`` of length 10, in the order
           documented in the plan (F1 first, F10 last), with keys in
           lowercase Textual format and Korean descriptions matching
           the F-row labels in ``HtopFooter.F_ROW`` (T22).
    """
    return [
        Binding("f1", "show_help", "도움말"),
        Binding("f2", "show_setup", "설정/저장"),
        Binding("f3", "search", "검색"),
        Binding("f4", "filter", "필터"),
        Binding("f5", "toggle_tree", "트리"),
        Binding("f6", "cycle_sort", "정렬"),
        Binding("f7", "promote_selected", "승진"),
        Binding("f8", "demote_selected", "감봉"),
        Binding("f9", "fire_selected", "해고"),
        Binding("f10", "quit_or_sell", "종료/매각"),
    ]
