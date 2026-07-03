"""Tests for KoreanIMEMixin key remap helper."""

from __future__ import annotations

from htop_tycoon.ui.ime import KoreanIMEMixin, _remap_korean_key


def test_mixin_inherits_by_modal_screens() -> None:
    from htop_tycoon.ui.screens.help import HelpScreen
    from htop_tycoon.ui.screens.hire import HireScreen
    from htop_tycoon.ui.screens.promote import PromoteScreen

    assert issubclass(HelpScreen, KoreanIMEMixin)
    assert issubclass(HireScreen, KoreanIMEMixin)
    assert issubclass(PromoteScreen, KoreanIMEMixin)
