"""Tests for bind_en_ko / ko_key_for — Korean IME support."""

from __future__ import annotations

from htop_tycoon.ui.i18n import KO_KEY_MAP, bind_en_ko, ko_key_for


def test_ko_key_for_letters():
    assert ko_key_for("h") == "ㅗ"
    assert ko_key_for("n") == "ㅜ"
    assert ko_key_for("s") == "ㄴ"
    assert ko_key_for("q") == "ㅂ"
    assert ko_key_for("x") == "ㅌ"


def test_ko_key_for_non_letters_returns_none():
    assert ko_key_for("0") is None
    assert ko_key_for("1") is None
    assert ko_key_for("f1") is None
    assert ko_key_for("escape") is None
    assert ko_key_for("space") is None


def test_bind_en_ko_returns_one_or_two_bindings():
    from textual.binding import Binding

    single = bind_en_ko("f1", "show_help", "도움말")
    assert len(single) == 1
    assert single[0].key == "f1"

    pair = bind_en_ko("h", "open_hire_screen", "고용")
    assert len(pair) == 2
    assert pair[0].key == "h"
    assert pair[1].key == "ㅗ"
    assert pair[0].action == pair[1].action == "open_hire_screen"


def test_bind_en_ko_korean_char_uses_2set_map():
    from textual.binding import Binding

    binding_q, binding_q_ko = bind_en_ko("q", "quit_app", "Quit")
    assert binding_q.key == "q"
    assert binding_q_ko.key == "ㅂ"
    assert binding_q_ko.show is False
    assert binding_q.show is True
