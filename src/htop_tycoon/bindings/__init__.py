"""htop_tycoon.bindings — key-binding registry for the App.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 537-561 (T24):

- ``register_f_bindings()`` returns the 10 locked F1..F10 ``Binding`` objects.
- Key names use Textual's lowercase format (``f1`` not ``F1``).
- Each ``Binding`` carries the locked Korean description (``도움말``, etc.).
- Single-key bindings (``t``, ``u``, ``M``, ``P``, ``T``, arrows, ``Space``)
  land in T25; this package is F-row only for now.
"""
