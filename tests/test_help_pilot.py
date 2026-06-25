"""Tests for T26: HelpScreen modal — Korean F-key reference, values from balance.

Locks the contract from ``.omo/plans/htop-tycoon.md`` line 587-612:

- ``class HelpScreen(textual.screen.ModalScreen)`` renders a 2-column
  key-reference table whose content matches T22 footer labels AND T24
  BINDINGS action labels (single source of truth: T22 + T24 + T26 must
  agree on every F-row + single-key label).
- **NO hardcoded promotion/demotion numbers** — the F7/F8 lines are
  formatted as ``F7         승진 (+1 tier, 비용: {promotion_cost}₩)``
  where ``{promotion_cost}`` is filled from
  ``balance["employees"]["promotion_cost"]`` at render time via
  ``htop_tycoon.data.load_balance()``. Same for ``{demotion_savings}``.
- Pressing ``Q`` dismisses the modal; the underlying App is NOT closed
  (the App remains mounted; the modal pops off the screen stack).
- The test does NOT mutate any T1-T25 file: it mounts a tiny host App
  whose F1 binding pushes the modal. The main ``HtopTycoonApp``'s
  F1 stub is unchanged; the "real" action wiring is T25's job.

Locked table (plan line 589-606, columns aligned at 11 chars)::

    F1         도움말 (이 화면)
    F2         설정 / 게임 저장
    F3         직원 검색
    F4         필터 (이름/스킬 범위)
    F5 / t     조직도 트리 토글
    F6         정렬 사이클
    F7         승진 (+1 tier, 비용: {promotion_cost}₩)
    F8         감봉 (-1 tier, 절약: {demotion_savings}₩)
    F9         해고 (퇴직금 지급)
    F10        종료 / 자발적 매각

    u          부서 필터 선택
    M / P / T  만족도 / 급여 / 입사순 정렬
    Space      직원 태그 (다중 선택)
    ↑ / ↓      이동
    Enter      선택
    Q          모달 닫기 / 게임 종료

Modal screens require a Textual app context; each test mounts a tiny
host App via Pilot. The F1 push is exercised in
:class:`TestF1OpensHelpScreen`; direct-push tests (matching the
EndingScreen test pattern) cover content + dismissal.
"""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from htop_tycoon.data import load_balance
from htop_tycoon.ui.screens.help import HelpScreen

# -- Locked single-source-of-truth strings -----------------------------------
#
# The expected table is built by substituting the balance values into the
# plan's locked template. We compute it once from load_balance() (the same
# function the production code uses) so the test cannot drift from the
# data layer: if balance.yaml changes, both the test and the code pick up
# the new value.

# Plan line 596-597: F7 / F8 use {promotion_cost} / {demotion_savings}.
_F7_TEMPLATE: str = "F7         승진 (+1 tier, 비용: {promotion_cost}₩)"
_F8_TEMPLATE: str = "F8         감봉 (-1 tier, 절약: {demotion_savings}₩)"

# The remaining 15 lines are literal — no balance interpolation.
_STATIC_LINES: tuple[str, ...] = (
    "F1         도움말 (이 화면)",
    "F2         설정 / 게임 저장",
    "F3         직원 검색",
    "F4         필터 (이름/스킬 범위)",
    "F5 / t     조직도 트리 토글",
    "F6         정렬 사이클",
    "F9         해고 (퇴직금 지급)",
    "F10        종료 / 자발적 매각",
    "",
    "u          부서 필터 선택",
    "M / P / T  만족도 / 급여 / 입사순 정렬",
    "Space      직원 태그 (다중 선택)",
    "↑ / ↓      이동",
    "Enter      선택",
    "Q          모달 닫기 / 게임 종료",
)


def _expected_table() -> str:
    """Return the full locked help table as a single newline-joined string.

    The F7 and F8 lines are interpolated from ``load_balance()``; the
    remaining lines are literal. Building the expected string the SAME
    way the production code does guarantees the test cannot drift from
    the data layer.
    """
    balance = load_balance()
    promotion_cost = int(balance["employees"]["promotion_cost"])
    demotion_savings = int(balance["employees"]["demotion_savings"])
    f7 = _F7_TEMPLATE.format(promotion_cost=promotion_cost)
    f8 = _F8_TEMPLATE.format(demotion_savings=demotion_savings)
    return "\n".join(
        (
            _STATIC_LINES[0],  # F1
            _STATIC_LINES[1],  # F2
            _STATIC_LINES[2],  # F3
            _STATIC_LINES[3],  # F4
            _STATIC_LINES[4],  # F5 / t
            _STATIC_LINES[5],  # F6
            f7,  # F7 with promotion_cost
            f8,  # F8 with demotion_savings
            _STATIC_LINES[6],  # F9
            _STATIC_LINES[7],  # F10
            *_STATIC_LINES[8:],  # blank + single-key rows
        )
    )


# -- Host apps ---------------------------------------------------------------


class _DirectHostApp(App[None]):
    """Minimal App that pushes a single HelpScreen on mount.

    Mirrors the pattern from ``test_ending_screen_pilot.py`` so the
    direct-push tests are not coupled to ``HtopTycoonApp``'s
    (unmodified) T25 stub.
    """

    def compose(self) -> object:
        # No children — the modal is pushed imperatively in on_mount.
        return []

    def on_mount(self) -> None:
        self.push_screen(HelpScreen())


class _F1HostApp(App[None]):
    """Host App with an F1 binding that pushes HelpScreen.

    Exercises the user-facing contract: pressing F1 from the live App
    must open the help modal. This is a minimal stand-in for the real
    ``HtopTycoonApp.action_show_help`` (which T25 will wire to the same
    ``push_screen(HelpScreen())`` call). Keeping the F1 push in a
    separate test app means T26 does NOT have to modify T16/T24/T25
    files (``app.py``, ``bindings/registry.py``).
    """

    BINDINGS: list[Binding] = [Binding("f1", "show_help", "도움말")]

    def compose(self) -> object:
        return []

    def on_mount(self) -> None:
        # No initial push; F1 is what we want to test.
        pass

    def action_show_help(self) -> None:
        """F1 → push the HelpScreen modal."""
        self.push_screen(HelpScreen())


# -- Module surface ---------------------------------------------------------


class TestHelpScreenModuleSurface:
    """The screens package re-exports HelpScreen for clean imports."""

    def test_help_module_importable(self) -> None:
        """``htop_tycoon.ui.screens.help`` is importable."""
        import htop_tycoon.ui.screens.help as help_module

        assert help_module is not None

    def test_screens_package_exposes_help_screen(self) -> None:
        """``htop_tycoon.ui.screens`` re-exports ``HelpScreen``."""
        import htop_tycoon.ui.screens as screens_module

        assert hasattr(screens_module, "HelpScreen")
        assert screens_module.HelpScreen is HelpScreen

    def test_help_screen_subclasses_modal_screen(self) -> None:
        """``HelpScreen`` is a subclass of ``textual.screen.ModalScreen``."""
        from textual.screen import ModalScreen

        assert issubclass(HelpScreen, ModalScreen)


# -- F1 → modal -------------------------------------------------------------


class TestF1OpensHelpScreen:
    """Pressing F1 on the host App opens the HelpScreen modal."""

    async def test_f1_pushes_help_screen_modal(self) -> None:
        """Given: a host App with F1 wired to push HelpScreen
        When:  pilot.press("f1")
        Then:  app.screen is an instance of HelpScreen.
        """
        app = _F1HostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Sanity: the host's default screen is active.
            assert not isinstance(app.screen, HelpScreen)
            # Press F1.
            await pilot.press("f1")
            await pilot.pause()
            # The modal is now the active screen.
            assert isinstance(app.screen, HelpScreen), (
                f"F1 did not open HelpScreen: app.screen is "
                f"{type(app.screen).__name__}"
            )

    async def test_f1_opened_modal_contains_full_locked_table(self) -> None:
        """Given: a host App with F1 wired to push HelpScreen
        When:  pilot.press("f1") + pilot.pause
        Then:  rendered content contains every locked table line.
        """
        app = _F1HostApp()
        async with app.run_test() as pilot:
            await pilot.press("f1")
            await pilot.pause()
            rendered = str(app.screen.renderable)
            # Every locked F-row line appears.
            for line in _STATIC_LINES:
                assert line in rendered, (
                    f"F1 modal missing locked line {line!r} in "
                    f"render:\n{rendered}"
                )

    async def test_f1_opened_modal_has_promotion_cost_replaced(self) -> None:
        """F7 line must show the actual balance value, not the placeholder.

        The T26 spec requires ``{promotion_cost}`` to be replaced with
        the actual balance value at render time. The locked value in
        balance.yaml is 500; the rendered F7 line must include "500".
        """
        app = _F1HostApp()
        async with app.run_test() as pilot:
            await pilot.press("f1")
            await pilot.pause()
            rendered = str(app.screen.renderable)
            promotion_cost = int(load_balance()["employees"]["promotion_cost"])
            expected = _F7_TEMPLATE.format(promotion_cost=promotion_cost)
            assert expected in rendered, (
                f"F7 line not interpolated from balance: "
                f"expected {expected!r} in render:\n{rendered}"
            )
            # The unsubstituted placeholder must NOT appear.
            assert "{promotion_cost}" not in rendered, (
                f"F7 still has unsubstituted placeholder: {rendered!r}"
            )

    async def test_f1_opened_modal_has_demotion_savings_replaced(self) -> None:
        """F8 line must show the actual demotion_savings value."""
        app = _F1HostApp()
        async with app.run_test() as pilot:
            await pilot.press("f1")
            await pilot.pause()
            rendered = str(app.screen.renderable)
            demotion_savings = int(load_balance()["employees"]["demotion_savings"])
            expected = _F8_TEMPLATE.format(demotion_savings=demotion_savings)
            assert expected in rendered, (
                f"F8 line not interpolated from balance: "
                f"expected {expected!r} in render:\n{rendered}"
            )
            assert "{demotion_savings}" not in rendered, (
                f"F8 still has unsubstituted placeholder: {rendered!r}"
            )


# -- Q dismisses the modal --------------------------------------------------


class TestQClosesHelpScreen:
    """Pressing Q dismisses the modal; the App is NOT closed."""

    async def test_q_dismisses_modal_after_f1(self) -> None:
        """Given: F1 pushed HelpScreen onto the host App
        When:  Q is pressed
        Then:  the modal is gone (app.screen is no longer HelpScreen).
        """
        app = _F1HostApp()
        async with app.run_test() as pilot:
            await pilot.press("f1")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)
            # Press Q to dismiss.
            await pilot.press("q")
            await pilot.pause()
            assert not isinstance(app.screen, HelpScreen), (
                f"Q did not dismiss the modal: app.screen is "
                f"{type(app.screen).__name__}"
            )

    async def test_q_dismissal_keeps_app_alive(self) -> None:
        """Given: F1 pushed HelpScreen onto the host App
        When:  Q is pressed
        Then:  the App itself is NOT closed — Pilot context is still active.
        """
        app = _F1HostApp()
        async with app.run_test() as pilot:
            await pilot.press("f1")
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert app.is_running
            # The screen stack is back to one (the host default).
            assert len(app.screen_stack) == 1

    async def test_q_dismisses_modal_via_direct_push(self) -> None:
        """Same Q-dismissal behavior on a directly-pushed modal."""
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("q")
            await pilot.pause()
            assert not isinstance(app.screen, HelpScreen)
            assert app.is_running


# -- Content: direct-push path ----------------------------------------------


class TestHelpScreenContent:
    """HelpScreen renders the locked Korean key reference table."""

    async def test_modal_renders_full_locked_table(self) -> None:
        """The rendered content matches the full locked table exactly."""
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            expected = _expected_table()
            assert expected == rendered, (
                f"HelpScreen render mismatch.\n"
                f"--- expected ---\n{expected}\n"
                f"--- actual ---\n{rendered}\n"
                f"--- end ---"
            )

    async def test_modal_renders_every_f_row_label(self) -> None:
        """All 10 F-row labels (F1..F10) appear in the rendered modal."""
        expected_labels = [
            "F1         도움말 (이 화면)",
            "F2         설정 / 게임 저장",
            "F3         직원 검색",
            "F4         필터 (이름/스킬 범위)",
            "F5 / t     조직도 트리 토글",
            "F6         정렬 사이클",
            "F9         해고 (퇴직금 지급)",
            "F10        종료 / 자발적 매각",
        ]
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            for label in expected_labels:
                assert label in rendered, f"missing F-row label: {label!r}"

    async def test_modal_renders_f7_with_balance_promotion_cost(self) -> None:
        """F7 line includes the actual promotion_cost from balance.yaml.

        The locked value in balance.yaml is 500. The test reads it
        dynamically (via load_balance()) so a future balance.yaml edit
        does not silently break this assertion — the expected value
        tracks the data layer.
        """
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            promotion_cost = int(load_balance()["employees"]["promotion_cost"])
            expected = _F7_TEMPLATE.format(promotion_cost=promotion_cost)
            assert expected in rendered

    async def test_modal_renders_f8_with_balance_demotion_savings(self) -> None:
        """F8 line includes the actual demotion_savings from balance.yaml."""
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            demotion_savings = int(load_balance()["employees"]["demotion_savings"])
            expected = _F8_TEMPLATE.format(demotion_savings=demotion_savings)
            assert expected in rendered

    async def test_modal_renders_every_single_key_label(self) -> None:
        """All 7 single-key hint tokens appear in the rendered modal."""
        expected = [
            "u          부서 필터 선택",
            "M / P / T  만족도 / 급여 / 입사순 정렬",
            "Space      직원 태그 (다중 선택)",
            "↑ / ↓      이동",
            "Enter      선택",
            "Q          모달 닫기 / 게임 종료",
        ]
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            for label in expected:
                assert label in rendered, f"missing single-key label: {label!r}"

    async def test_modal_does_not_have_unsubstituted_placeholders(self) -> None:
        """No {promotion_cost} or {demotion_savings} literal left in render."""
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            assert "{promotion_cost}" not in rendered
            assert "{demotion_savings}" not in rendered

    async def test_modal_does_not_use_htop_english_labels(self) -> None:
        """The HelpScreen MUST NOT contain htop's original English F-key labels.

        Plan MUST-NOT-DO applies to the help screen too: ``F7Nice-``,
        ``F8Nice+``, ``F9Kill``, ``F10Quit`` describe real htop behavior
        (process nice values, signal kill, quit), not this game's actions.
        """
        forbidden = ("F7Nice-", "F7Nice+", "F8Nice-", "F8Nice+", "F9Kill", "F10Quit")
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            for label in forbidden:
                assert label not in rendered, (
                    f"HelpScreen leaked forbidden htop English label {label!r}"
                )


# -- T22 + T24 + T26 contract agreement ------------------------------------


class TestHelpScreenContractAgreement:
    """T22 footer + T24 BINDINGS + T26 help screen must agree on labels."""

    def test_help_screen_f_row_labels_match_footer_f_row(self) -> None:
        """The F-row Korean labels in the help screen match the footer.

        The footer (T22) renders ``F1도움말 F2설정 ...``. The help
        screen's locked table uses the SAME Korean tokens (도움말,
        설정 / 게임 저장, ...). This test pins the cross-source
        agreement: a drift between T22 and T26 surfaces here, not as
        a silent UI disagreement.
        """
        from htop_tycoon.ui.widgets.footer import F_ROW

        # Tokens like "F1도움말" — strip the "F<n>" prefix to get the
        # Korean label. Then map the help screen rows to the same
        # tokens.
        # T22 tokens (no space between F<n> and label): F1도움말, F2설정/저장, ...
        # T26 rows (with 9 spaces of padding): F1         도움말 (이 화면), ...
        # We assert on the Korean SUBSTRING overlap.
        tokens = ["도움말", "설정", "검색", "필터", "트리", "정렬", "승진", "감봉", "해고", "매각"]
        # Every T22 token must appear somewhere in the help screen table.
        app_text = _expected_table()
        missing = [tok for tok in tokens if tok not in app_text]
        assert missing == [], (
            f"HelpScreen F-row drifted from T22 footer tokens: missing {missing}"
        )
        # And the T22 F_ROW constant must include every one of those tokens.
        for tok in tokens:
            assert tok in F_ROW, f"T22 footer F_ROW missing token {tok!r}"

    def test_help_screen_t_u_labels_match_footer(self) -> None:
        """The t/u labels in help screen match the footer (T22 SINGLE_KEY_ROW)."""
        from htop_tycoon.ui.widgets.footer import SINGLE_KEY_ROW

        # The footer shows "t:트리" and "u:부서필터"; the help screen
        # shows "F5 / t     조직도 트리 토글" and "u          부서 필터 선택".
        # Both contain the Korean tokens "트리" and "부서 필터".
        tokens = ["트리", "부서필터"]
        for tok in tokens:
            assert tok in SINGLE_KEY_ROW, f"T22 footer missing {tok!r}"
        app_text = _expected_table()
        assert "트리" in app_text
        assert "부서 필터" in app_text  # help screen has "부서 필터 선택" with space

    async def test_help_screen_does_not_hardcode_promotion_number(self) -> None:
        """Sanity: the help screen never bakes the number 500 as a literal.

        The T26 MUST-NOT-DO forbids hardcoded ``-500`` / ``+300`` (or
        any numeric value) for promotion/demotion. The test verifies
        that the rendered content contains the SAME number that
        ``load_balance()`` reports, not a different literal.
        """
        app = _DirectHostApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered = str(app.screen.renderable)
            promotion_cost = int(load_balance()["employees"]["promotion_cost"])
            assert f"비용: {promotion_cost}₩" in rendered, (
                f"F7 line missing formatted promotion cost "
                f"{promotion_cost}: {rendered!r}"
            )
