"""Tests for T24: F1~F10 BINDINGS registration.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 537-561:

- ``htop_tycoon.bindings.registry`` exposes ``register_f_bindings()`` returning
  exactly 10 ``textual.binding.Binding`` objects keyed F1..F10.
- Each binding's key uses Textual's lowercase format (``f1`` not ``F1``).
- ``HtopTycoonApp.BINDINGS`` extends the previously-empty list with these 10
  bindings (T16 left it empty as a placeholder).
- Each ``action_*`` method exists on the App and is a STUB — pressing F1
  triggers ``action_show_help`` (logged/notified), pressing F9 triggers
  ``action_fire_selected``. Real implementations land in T25.
- Pressing an unbound key (F11) is a no-op: no crash, no action fires.

The Pilot tests use ``asyncio.sleep`` and ``pilot.press`` to drive Textual
headlessly. Each action stub records its name on ``self._last_action`` so
the test can assert the action fired without coupling to notify internals.
"""

from __future__ import annotations

from textual.binding import Binding

from htop_tycoon.bindings.registry import register_f_bindings
from htop_tycoon.ui.app import HtopTycoonApp

# -- Locked binding table ---------------------------------------------------
# Plan line 542-553: the exact (key, action, description) tuples.
LOCKED_BINDINGS: tuple[tuple[str, str, str], ...] = (
    ("f1", "show_help", "도움말"),
    ("f2", "show_setup", "설정/저장"),
    ("f3", "search", "검색"),
    ("f4", "filter", "필터"),
    ("f5", "toggle_tree", "트리"),
    ("f6", "cycle_sort", "정렬"),
    ("f7", "promote_selected", "승진"),
    ("f8", "demote_selected", "감봉"),
    ("f9", "fire_selected", "해고"),
    ("f10", "quit_or_sell", "종료/매각"),
)


# -- Module surface ---------------------------------------------------------


def test_bindings_package_is_importable() -> None:
    """``htop_tycoon.bindings`` is a Python package."""
    import htop_tycoon.bindings as pkg

    assert pkg.__file__ is not None


def test_registry_module_exposes_register_f_bindings() -> None:
    """``registry`` module exposes ``register_f_bindings`` as a callable."""
    import htop_tycoon.bindings.registry as reg

    assert hasattr(reg, "register_f_bindings")
    assert callable(reg.register_f_bindings)


# -- Registry: return shape -------------------------------------------------


class TestRegistryReturnShape:
    """``register_f_bindings()`` returns a list of exactly 10 ``Binding``s."""

    def test_returns_list_of_ten_bindings(self) -> None:
        """The registry returns a list of exactly ten Binding objects."""
        result = register_f_bindings()
        assert isinstance(result, list)
        assert len(result) == 10
        for binding in result:
            assert isinstance(binding, Binding)

    def test_returns_fresh_list_each_call(self) -> None:
        """Two calls return independent list instances (no shared mutable state)."""
        first = register_f_bindings()
        second = register_f_bindings()
        assert first is not second


# -- Registry: each binding matches the locked spec ------------------------


class TestRegistryBindingsExact:
    """Each binding matches the locked (key, action, description) tuple."""

    def test_each_binding_matches_locked_tuple(self) -> None:
        """Every binding's (key, action, description) matches the spec."""
        result = register_f_bindings()
        for binding, expected in zip(result, LOCKED_BINDINGS, strict=True):
            exp_key, exp_action, exp_desc = expected
            assert binding.key == exp_key, (
                f"key mismatch: got {binding.key!r}, expected {exp_key!r}"
            )
            assert binding.action == exp_action, (
                f"action mismatch: got {binding.action!r}, "
                f"expected {exp_action!r}"
            )
            assert binding.description == exp_desc, (
                f"description mismatch: got {binding.description!r}, "
                f"expected {exp_desc!r}"
            )

    def test_keys_use_textual_lowercase_format(self) -> None:
        """All keys are lowercase (``f1``, not ``F1``) per Textual Binding API."""
        result = register_f_bindings()
        for binding in result:
            assert binding.key == binding.key.lower(), (
                f"key {binding.key!r} must be lowercase per Textual's Binding API"
            )
            assert binding.key.startswith("f"), (
                f"key {binding.key!r} must start with 'f'"
            )

    def test_no_lowercase_q_binding_present(self) -> None:
        """Must NOT bind lowercase ``q`` for quit (conflicts with text input).

        Plan MUST-NOT-DO: 'Do NOT bind to lowercase `q` for quit (conflict
        with future text input).' None of the 10 bindings uses ``q``.
        """
        result = register_f_bindings()
        for binding in result:
            assert binding.key != "q", (
                f"forbidden: lowercase 'q' binding for quit conflicts "
                f"with future text input (got {binding!r})"
            )


# -- App: BINDINGS class attribute -----------------------------------------


class TestAppBindingsAttribute:
    """``HtopTycoonApp.BINDINGS`` contains the 10 locked F1-F10 bindings.

    After T25 the App's BINDINGS also include the 8 single-key bindings
    (t, u, m, p, T, up, down, space). The F-row slice still matches the
    locked T24 tuple; the full list has 18 entries. The tests below
    assert the F-row slice specifically (first 10 entries) so the T24
    contract stays locked.
    """

    def test_app_bindings_has_ten_f_row_entries(self) -> None:
        """After T24, the F-row slice of ``BINDINGS`` has exactly 10 entries.

        T25 extended ``BINDINGS`` with 8 single-key entries for a total of
        18; this test pins the F-row slice (``BINDINGS[:10]``) which is
        the T24 contract.
        """
        assert len(HtopTycoonApp.BINDINGS[:10]) == 10

    def test_app_bindings_match_locked_table(self) -> None:
        """The App's F-row BINDINGS match the locked (key, action, description).

        T25 extended ``BINDINGS`` with 8 single-key entries; the F-row
        contract is locked in the first 10 entries (T24). The full
        single-key extension is pinned by
        ``tests/test_single_key_bindings_pilot.py``.
        """
        for binding, expected in zip(
            HtopTycoonApp.BINDINGS[:10], LOCKED_BINDINGS, strict=True
        ):
            exp_key, exp_action, exp_desc = expected
            assert binding.key == exp_key
            assert binding.action == exp_action
            assert binding.description == exp_desc

    def test_app_bindings_match_registry(self) -> None:
        """App's F-row BINDINGS are byte-identical to ``register_f_bindings()`` output.

        T25 extended ``BINDINGS`` with the single-key registry; this
        test pins the T24 contract on the F-row slice (``BINDINGS[:10]``).
        """
        registry = register_f_bindings()
        assert len(HtopTycoonApp.BINDINGS[:10]) == len(registry)
        for app_binding, reg_binding in zip(
            HtopTycoonApp.BINDINGS[:10], registry, strict=True
        ):
            assert app_binding == reg_binding


# -- App: action_* methods exist -------------------------------------------


class TestAppActionMethods:
    """Every bound action has a corresponding ``action_*`` method on the App."""

    def test_all_ten_action_methods_exist(self) -> None:
        """For each binding.action, the App has a method named action_<action>."""
        for binding in HtopTycoonApp.BINDINGS:
            method_name = f"action_{binding.action}"
            assert hasattr(HtopTycoonApp, method_name), (
                f"missing {method_name} on HtopTycoonApp"
            )
            assert callable(getattr(HtopTycoonApp, method_name))


# -- Pilot: F1 / F9 fire their action stubs -------------------------------


class TestF1F9FireStubs:
    """Pressing F1 / F9 via Pilot triggers the corresponding action stub."""

    async def test_f1_triggers_action_show_help(self) -> None:
        """Given: a mounted HtopTycoonApp
        When: pilot.press('f1') is sent
        Then: action_show_help fires (recorded on self._last_action).
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._last_action = None  # type: ignore[attr-defined]
            await pilot.press("f1")
            await pilot.pause()
            assert app._last_action == "show_help"  # type: ignore[attr-defined]

    async def test_f9_triggers_action_fire_selected(self) -> None:
        """Given: a mounted HtopTycoonApp
        When: pilot.press('f9') is sent
        Then: action_fire_selected fires (recorded on self._last_action).
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._last_action = None  # type: ignore[attr-defined]
            await pilot.press("f9")
            await pilot.pause()
            assert app._last_action == "fire_selected"  # type: ignore[attr-defined]

    async def test_f1_press_emits_a_notify(self) -> None:
        """Each stub calls ``self.notify`` so the user sees feedback.

        We assert against ``app._notifications`` (Textual's internal stack).
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            before = len(app._notifications)
            await pilot.press("f1")
            await pilot.pause()
            after = len(app._notifications)
            assert after > before, (
                "F1 stub should call self.notify to give visible feedback"
            )


# -- Pilot: F11 (out of list) is a no-op ----------------------------------


class TestOutOfListKeys:
    """Keys not in BINDINGS (e.g., F11) must not crash and must not fire."""

    async def test_f11_does_not_crash_and_does_not_fire_any_action(
        self,
    ) -> None:
        """Given: a mounted HtopTycoonApp with no F11 binding
        When: pilot.press('f11') is sent
        Then: no exception is raised and _last_action stays None.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._last_action = None  # type: ignore[attr-defined]
            # No F11 binding exists; press must be a no-op.
            await pilot.press("f11")
            await pilot.pause()
            assert app._last_action is None  # type: ignore[attr-defined]

    async def test_all_ten_f_keys_fire_their_action(self) -> None:
        """Exhaustive: every one of F1..F10 triggers its own action_* stub.

        T25 extended ``BINDINGS`` with the single-key entries; this test
        iterates only the F-row slice so the T24 contract stays locked.
        The full 18-entry behavior (including single-key actions) is
        pinned by ``tests/test_single_key_bindings_pilot.py``.
        """
        app = HtopTycoonApp(seed=42, tick_rate=100, no_autosave=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            for binding in HtopTycoonApp.BINDINGS[:10]:
                app._last_action = None  # type: ignore[attr-defined]
                await pilot.press(binding.key)
                await pilot.pause()
                assert app._last_action == binding.action, (  # type: ignore[attr-defined]
                    f"pressing {binding.key!r} should fire "
                    f"action_{binding.action!r}; got {app._last_action!r}"  # type: ignore[attr-defined]
                )
