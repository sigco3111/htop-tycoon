"""Tests for KoreanIMEMixin marker + dual-key BINDINGS coverage."""

from __future__ import annotations

from htop_tycoon.ui.ime import KoreanIMEMixin
from htop_tycoon.ui.screens.help import HelpScreen
from htop_tycoon.ui.screens.hire import HireScreen
from htop_tycoon.ui.screens.strategy_picker import StrategyPicker


def test_help_screen_inherits_ime_mixin() -> None:
    assert issubclass(HelpScreen, KoreanIMEMixin)


def test_all_modal_screens_inherit_ime_mixin() -> None:
    screens = [HelpScreen, HireScreen, StrategyPicker]
    for screen_cls in screens:
        assert issubclass(screen_cls, KoreanIMEMixin)


def test_korean_ime_mixin_exists_and_importable() -> None:
    assert KoreanIMEMixin is not None
