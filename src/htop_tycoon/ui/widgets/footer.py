"""htop-tycoon v3.0 — HtopFooter widget (spec §4.1).

Footer renders F-key hints in Korean + speed control (0=정지, 1-4=1x-4x)
+ Auto mode indicator. Renders from ``bindings.registry.BINDINGS``.

Layout: two lines, each kept short enough to fit a default 80-column
terminal without horizontal truncation.

  Line 1: action keys (H/n/g/s/d/a/c) + [0]정지 + Auto:ON/OFF
  Line 2: Speed legend (1-4) + F-key legend
"""
from __future__ import annotations

from textual.widget import Widget

from htop_tycoon.bindings.registry import BINDINGS


class HtopFooter(Widget):
    """Spec §4.1: 'Footer bar: F-key hints (Korean) + Auto mode indicator'."""

    DEFAULT_CSS = """
    HtopFooter {
        dock: bottom;
        height: 2;
        background: $surface;
        color: $secondary;
        padding: 0 1;
    }
    """

    _COMPACT: dict[str, str] = {
        "직원 고용": "고용",
        "새 게임": "새게임",
        "진행 보기": "진행",
        "전략 선택": "전략",
        "Auto 모드": "Auto",
        "시상식": "시상",
        "콘솔 관리": "콘솔",
    }

    _FKEY_COMPACT: dict[str, str] = {
        "도움말": "도움",
        "저장": "저장",
        "직원 검색": "검색",
        "필터": "필터",
        "부서 트리": "트리",
        "정렬 사이클": "정렬",
        "승진": "승진",
        "감봉": "감봉",
        "해고": "해고",
        "종료/매각": "종료",
    }

    def render(self) -> str:
        from htop_tycoon.ui.app import _BINDING_KEY_PREFIXES

        action_keys = [
            b
            for b in BINDINGS
            if b.description
            and not b.key.startswith("F")
            and b.key not in {"0", "1", "2", "3", "4", "p"}
            and b.key in _BINDING_KEY_PREFIXES
        ]
        a_parts = [
            f"[{b.key}]{self._COMPACT.get(b.description, b.description)}"
            for b in action_keys
        ]
        auto_on = getattr(self.app, "auto_mode", False)
        line1 = f"{' '.join(a_parts)} [Auto:{'ON' if auto_on else 'OFF'}]"

        speed = "[0]정지 [1]1x [2]2x [3]3x [4]4x"
        fkeys = [b for b in BINDINGS if b.key.startswith("F") and b.description]
        f_parts = [
            f"[{b.key}]{self._FKEY_COMPACT.get(b.description, b.description)}"
            for b in fkeys
        ]
        line2 = f"{speed}  {' '.join(f_parts)}"

        return f"{line1}\n{line2}"


__all__ = ["HtopFooter"]
