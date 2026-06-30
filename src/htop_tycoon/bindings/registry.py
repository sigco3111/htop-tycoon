"""htop_tycoon.bindings.registry — Single-key + F1-F10 binding table for the App.

Locks the contracts from ``.omo/plans/htop-tycoon.md``:

- T24 (line 537-561): ``register_f_bindings()`` returns 10 ``Binding`` objects
  keyed F1..F10 in lowercase Textual format with Korean footer descriptions.
- T25 (line 565-585): ``register_single_key_bindings()`` returns 8 ``Binding``
  objects for the htop-style single-key shortcuts (t, u, m, p, T, up, down,
  space) with ``show=False`` so they stay out of the footer.
- Wave 7: ``register_extra_bindings()`` returns 1 extra single-key binding
  (backtick → toggle_pause) so the time-stop feature has a keyboard
  shortcut without disturbing the locked F1..F10 row.

Both functions return a fresh list each call so callers can extend the
output without affecting other call sites. ``HtopTycoonApp.BINDINGS`` invokes
all three at class-body evaluation time; tests may invoke any of them any
number of times without state bleed-through.

Anti-patterns explicitly rejected here:
- Hardcoding ``Binding(\"F1\", ...)`` — Textual's Binding API normalizes keys
  to lowercase, but using the locked lowercase form ``f1`` makes the spec
  and the implementation match exactly without runtime normalization.
- Mutating a shared default list — would couple unrelated callers.
- Inlining the action methods on the App — the registry only owns the
  binding-table shape; the action handlers live in ``ui/action_handlers.py``
  so the engine/UI boundary stays clean.
- Adding the pause shortcut to the F-row (F11): macOS reserves F11 for
  "Show Desktop" / "Mission Control", which would intercept the keypress
  before our app sees it. Extending the locked 10-F plan to 11 also breaks
  T24's byte-equality contract for the F-row length.
- Using a literal `` ` `` character: Textual stores the key by name, not
  by char, so the binding must use the canonical name ``backtick``.
"""

from __future__ import annotations

from textual.binding import Binding

__all__ = [
    "register_extra_bindings",
    "register_f_bindings",
    "register_single_key_bindings",
]


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

            1. ``t`` → ``toggle_tree``
            2. ``u`` → ``filter_by_dept``
            3. ``m`` → ``sort_by_satisfaction``
            4. ``s`` → ``sort_by_salary`` (mnemonic for s/salary)
            5. ``i`` → ``sort_by_time`` (mnemonic for i/입사 = hired)
            6. ``up``    → ``cursor_up``
            7. ``down``  → ``cursor_down``
            8. ``space`` → ``tag_selected``

           Every binding has ``show=False`` (per the plan: "Textual Binding
           show=False means the binding is hidden from the footer but still
           active"). Korean descriptions on the t/u keys mirror the F-row
           hint strings; the other keys have no footer label because they
           are pure navigation / marker actions.

    Wave 7 — all keys are lowercase:
    - ``s`` replaced ``p`` for sort_by_salary (mnemonic for "salary")
    - ``i`` replaced ``T`` for sort_by_time (mnemonic for "i/psa" =
      hired; ``t`` was already taken by ``toggle_tree``, and
      ``i`` avoids the shift modifier for a common sort action)
    - ``P`` was moved to ``register_extra_bindings`` and is now ``p``
      (lowercase) for the pause/resume shortcut
    - See :func:`register_extra_bindings` for the pause binding.
    """
    return [
        Binding("t", "toggle_tree", "트리 토글", show=False),
        Binding("u", "filter_by_dept", "부서 필터", show=False),
        Binding("m", "sort_by_satisfaction", show=False),
        Binding("s", "sort_by_salary", show=False),
        Binding("up", "cursor_up", show=False),
        Binding("down", "cursor_down", show=False),
        Binding("space", "tag_selected", show=False),
    ]


def register_extra_bindings() -> list[Binding]:
    """Return the extra single-key binding added after the locked F1..F10.

    Wave 7: lowercase ``p`` toggles pause/resume of the per-tick timer
    (locked in ``engine/tick.py`` + ``app._tick_once``). Lives in its
    own function so the original ``register_f_bindings()`` stays at
    exactly 10 entries (preserving the T24 byte-equality contract)
    while the App's total ``BINDINGS`` list grows by one.

    Why ``p`` and not an F-key / other single-key:
    - F11 collides with the macOS "Show Desktop" / "Mission Control"
      system shortcut on macOS hosts.
    - Extending the F-row to 11 breaks the T24 byte-equality contract
      for the locked F1..F10 length.
    - ``p`` was freed up by the Wave-7 reassignment that moved
      ``sort_by_salary`` from ``p`` to ``s`` (mnemonic for "salary"),
      and moved ``sort_by_time`` from ``T`` to ``i`` (mnemonic for
      "i/psa" = hired) — see :func:`register_single_key_bindings`.

    Wave 7 amendment: ``p`` replaced the previous ``P`` (uppercase)
    pairing. The user wanted all shortcuts lowercase, and lowercase
    ``p`` was free after the salary shortcut was moved to ``s``.

    Wave 8: ``d`` → ``toggle_delegate`` was added for the delegation
    feature. The full single-key row is updated separately in T7.
    """
    return [
        Binding("p", "toggle_pause", "일시정지", show=False),
        Binding("d", "toggle_delegate", "위임", show=False),
        # Wave 8 (T43): the focus-picker modal uses the lowercase `i`
        # key as the mnemonic for the per-dept strategic focus. The
        # earlier WIP binding of `i` to `sort_by_time` (T25 mnemonic
        # mismatch) was removed; sort_by_time now lives in the F6 sort
        # cycle (locked in T19) so `i` is free for the focus picker.
        Binding("i", "focus_picker", "전략", show=False),
    ]
