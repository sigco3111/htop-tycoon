"""KoreanIME on_key remap — force event.key to English when IME produced a 2-set char.

Textual 8.x does not expose an is_compositing() method on key events.
We work around this by intercepting on_key and rewriting event.key
to the English equivalent (per the KO_KEY_MAP in src/htop_tycoon/ui/i18n.py)
so the first key press in a Korean-IME session hits the English binding
instead of waiting for the second key or a composition-confirming
keystroke.

The remap is a no-op for non-Korean events and for Korean chars that
are not in the 2-set map.
"""

from __future__ import annotations

from textual.screen import ModalScreen

from htop_tycoon.ui.i18n import ko_key_for


def _remap_korean_key(event) -> None:
    """If the event key is a Korean 2-set consonant, rewrite it to its
    English equivalent so BINDINGS dispatch works on the first key press.
    Uses object.__setattr__ because Textual's Key is a slotted/frozen
    event with no public setter.
    """
    if not event.is_printable:
        return
    current = getattr(event, "character", None) or getattr(event, "key", "")
    en = ko_key_for(current) if current else None
    if en is None or en == current:
        return
    try:
        object.__setattr__(event, "key", en)
    except Exception:
        pass
    try:
        object.__setattr__(event, "character", en)
    except Exception:
        pass


class KoreanIMEMixin:
    """Mixin for ModalScreen subclasses — instant key dispatch under Korean IME.

    on_key remaps Korean 2-set consonants to their English equivalents.
    Textual's own key handling continues to dispatch BINDINGS using the
    remapped event.key, so the first key press in a Korean-IME session
    hits the English binding immediately.
    """

    def on_key(self, event) -> None:
        _remap_korean_key(event)
