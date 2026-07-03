"""KoreanIME marker mixin.

Textual 8.x does not expose an is_compositing() method on key events,
so we cannot intercept IME composition from inside the app. Instead
we rely on registering both the English key and its Korean 2-set
equivalent in BINDINGS (see bind_en_ko in src/htop_tycoon/ui/i18n.py).
A first key press then matches the binding immediately, regardless
of IME state.

This mixin exists as a marker so future Textual versions with proper
IME events have an obvious integration point.
"""

from __future__ import annotations


class KoreanIMEMixin:
    """Marker mixin for ModalScreen subclasses."""
