"""htop-tycoon v3.0 — key-binding registry. Spec §4.1 + §6.

Single source of truth for the keyboard map: F-keys and single-char
aliases per spec §4.1. The registry is registered at app boot; if two
entries collide on the same key the boot fails (spec §6: 'Key binding
collision: bindings.registry raises at app boot — fail fast').

Adding a new binding: ``BINDINGS.append(Binding(key="X", action="hire"))``.
The action name maps to a function in the app (see ``ui.app.HtopTycoonApp``).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Binding:
    """Spec §4.1: a single key -> action mapping."""

    key: str  # e.g., "F2", "h", "H", "1", "0"
    action: str  # action name; resolved in ui.app.HtopTycoonApp.ACTION_DISPATCH
    description: str = ""  # Korean label for the footer hint


# Spec §4.1: 20 default bindings (F-keys + aliases + speed).
# Single source of truth — the footer widget renders from BINDINGS.
BINDINGS: list[Binding] = [
    # Help / save / search / filter / tree / sort cycle (F1-F6)
    Binding("F1", "help", "도움말"),
    Binding("F2", "save", "저장"),
    Binding("F3", "search_employee", "직원 검색"),
    Binding("F4", "filter", "필터"),
    Binding("F5", "toggle_dept_tree", "부서 트리"),
    Binding("F6", "sort_cycle", "정렬 사이클"),
    # Promote / demote / fire / quit (F7-F10)
    Binding("F7", "promote", "승진"),
    Binding("F8", "demote", "감봉"),
    Binding("F9", "fire", "해고"),
    Binding("F10", "quit_or_sell", "종료/매각"),
    # Single-char aliases (htop convention: lowercase = primary, Shift = alt)
    Binding("h", "help", ""),                # h = help
    Binding("S", "save", ""),                # S = save (Shift+s)
    Binding("/", "search_employee", ""),     # / = search
    Binding("\\", "filter", ""),            # \ = filter
    Binding("t", "toggle_dept_tree", ""),    # t = tree
    Binding("<", "sort_cycle", ""),         # < = sort prev
    Binding(">", "sort_cycle", ""),         # > = sort next
    Binding("]", "promote", ""),            # ] = promote
    Binding("[", "demote", ""),             # [ = demote
    Binding("k", "fire", ""),               # k = kill (fire)
    Binding("q", "quit_or_sell", ""),        # q = quit
    # Action triggers (Shift+ variants)
    Binding("H", "hire", "직원 고용"),        # H = hire (Shift+h)
    Binding("n", "start_game", "새 게임"),  # n = new game
    Binding("g", "view_project", "진행 보기"),
    Binding("s", "strategy_picker", "전략 선택"),
    Binding("d", "toggle_auto", "Auto 모드"),
    Binding("a", "awards", "시상식"),
    Binding("c", "console_mgmt", "콘솔 관리"),
    Binding(" ", "tag_employee", "태그"),
    # Movement / selection
    Binding("up", "cursor_up", ""),
    Binding("down", "cursor_down", ""),
    Binding("enter", "select", ""),
    Binding("escape", "close_modal", ""),
    # Speed control (0=정지, 1-4=1x-4x)
    Binding("0", "speed_0", "정지"),
    Binding("1", "speed_1", "1x"),
    Binding("2", "speed_2", "2x"),
    Binding("3", "speed_3", "3x"),
    Binding("4", "speed_4", "4x (QA)"),
    # Pause toggle (spec §4.1)
    Binding("p", "toggle_pause", "일시정지"),
]


def validate_bindings(bindings: list[Binding]) -> None:
    """Spec §6: 'Key binding collision: bindings.registry raises at app boot — fail fast'."""
    seen: dict[str, str] = {}
    for b in bindings:
        if b.key in seen:
            raise ValueError(
                f"key binding collision: {b.key!r} already mapped to "
                f"{seen[b.key]!r}, cannot also map to {b.action!r}"
            )
        seen[b.key] = b.action


# Run at import time so any collision is caught at the earliest possible
# moment (before the app boots).
validate_bindings(BINDINGS)


__all__ = ["BINDINGS", "Binding", "validate_bindings"]
