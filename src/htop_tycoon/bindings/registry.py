"""htop_tycoon.bindings.registry — Single-key + F1-F10 binding table for the App.

Locks the contracts from ``.omo/plans/htop-tycoon.md``:

- T24 (line 537-561): ``register_f_bindings()`` returns 10 ``Binding`` objects
  keyed F1..F10 in lowercase Textual format with Korean footer descriptions.
- T25 (line 565-585): ``register_single_key_bindings()`` returns 8 ``Binding``
  objects for the htop-style single-key shortcuts (t, u, m, p, T, up, down,
  space) with ``show=False`` so they stay out of the footer.

Both functions return a fresh list each call so callers can extend the
output without affecting other call sites. ``HtopTycoonApp.BINDINGS`` invokes
both at class-body evaluation time; tests may invoke either any number of
times without state bleed-through.

Anti-patterns explicitly rejected here:
- Hardcoding ``Binding(\"F1\", ...)`` — Textual's Binding API normalizes keys
  to lowercase, but using the locked lowercase form ``f1`` makes the spec
  and the implementation match exactly without runtime normalization.
- Mutating a shared default list — would couple unrelated callers.
- Inlining the action methods on the App — the registry only owns the
  binding-table shape; the action handlers live in ``ui/action_handlers.py``
  so the engine/UI boundary stays clean.
"""

from __future__ import annotations

from textual.binding import Binding

__all__ = ["register_f_bindings", "register_single_key_bindings"]


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


def register_single_key_bindings() -> list[Binding]:
    """Return the locked single-key binding list (htop-style shortcuts).

    Given: nothing (pure function; no parameters)
    When:  called (any number of times)
    Then:  returns a fresh ``list[Binding]`` of length 8, in the order
           documented in the plan (line 567-575):

            1. ``t``     → ``toggle_tree``
            2. ``u``     → ``filter_by_dept``
            3. ``m``     → ``sort_by_satisfaction``
            4. ``p``     → ``sort_by_salary``
            5. ``T``     → ``sort_by_time``
            6. ``up``    → ``cursor_up``
            7. ``down``  → ``cursor_down``
            8. ``space`` → ``tag_selected``

           Every binding has ``show=False`` (per the plan: "Textual Binding
           show=False means the binding is hidden from the footer but still
           active"). Korean descriptions on the t/u keys mirror the F-row
           hint strings; the other keys have no footer label because they
           are pure navigation / marker actions.

    Implementation note on key casing:
        The spec writes the keys in their htop form (``T`` for shift+t).
        Textual's ``Binding`` class stores the key as given — uppercase
        ``T`` is preserved so the keypress-detection layer can match
        shift+t correctly. Single-character lowercase keys match their
        lowercase characters.
    """
    return [
        Binding("t", "toggle_tree", "트리 토글", show=False),
        Binding("u", "filter_by_dept", "부서 필터", show=False),
        Binding("m", "sort_by_satisfaction", show=False),
        Binding("p", "sort_by_salary", show=False),
        Binding("T", "sort_by_time", show=False),
        Binding("up", "cursor_up", show=False),
        Binding("down", "cursor_down", show=False),
        Binding("space", "tag_selected", show=False),
    ]
