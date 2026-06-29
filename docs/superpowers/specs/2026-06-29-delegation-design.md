# 위임기능 (Delegation / Auto-Manager) — Design Spec

**Date:** 2026-06-29
**Status:** Draft — awaiting user review
**Scope:** htop-tycoon v0.1.0+ (Wave 8 amendment)

## 1. Background

htop-tycoon is a TUI business simulator disguised as `htop`. The player currently drives every decision manually via F-keys (F7=promote, F8=demote, F9=fire). The user requested a **delegation feature**: an AI auto-manager that runs the business autonomously while the player can step in via a keyboard shortcut.

Existing state: `_paused: bool` halts the per-tick clock when True. The new delegation feature is **independent of pause** — the clock may still tick while AI controls decisions, or both may be active simultaneously.

## 2. Goals

1. Player can toggle AI auto-manager on/off with a single keyboard shortcut.
2. When ON, AI makes all decisions (promote / demote / fire) deterministically via explicit heuristic rules.
3. When player presses ANY other interaction key (F1-F10, t/u/m/s/i, etc.), delegation auto-disables — the player's input is treated as a takeover signal.
4. UI clearly shows delegation state (header prefix) so the player always knows who's in control.
5. AI is unit-testable in isolation (no Textual, no RNG coupling) so heuristics are auditable.

## 3. Non-Goals (YAGNI)

- AI does NOT control product market / competitor / event chains (those remain in their existing engine modules).
- No "approve queue" — AI decisions are applied immediately, no preview.
- No learning / mimicry — heuristics are static rules, not trained on player behavior.
- No difficulty modifier / AI personality selection.
- No pause-on-firing-event — fire is just another engine action.
- No multi-level delegation (regional managers, dept heads) — single global auto-manager.

## 4. State Model

Add to `HtopTycoonApp.__init__`:

```python
self._delegated: bool = False  # True = AI makes decisions; False = player does
```

The two flags are independent:

| `_paused` | `_delegated` | Meaning |
|---|---|---|
| False | False | Normal play (player + clock running) |
| False | True  | AI control (clock running, AI acts) |
| True  | False | Player control, clock halted |
| True  | True  | Both halted (clock + AI) — no-ops |

## 5. Heuristic Rules (delegation ON, evaluated once per tick)

All rules are **read-only** against `state.employees`, `state.company.cash`, etc. and only fire when their preconditions hold. Rules are evaluated in priority order; the first matching rule per employee wins.

| Action | Precondition (all must hold) | Postcondition |
|---|---|---|
| **promote** | `employee.tier < TIER_MAX` AND `employee.skill >= promote_skill_threshold` (default 7) AND `state.company.cash >= promote_cost * safety_multiplier` (default 1.5) | `engine.actions.promote()` |
| **demote**  | `employee.tier > 1` AND (`state.company.cash < total_salary_per_week * runway_weeks` (default 4) OR `employee.satisfaction < demote_satisfaction_threshold` (default 30)) | `engine.actions.demote()` |
| **fire**    | `employee.satisfaction < fire_satisfaction_threshold` (default 20) | `engine.actions.fire()` |

**Defaults** (single source of truth in `balance.yaml` under a new `ai_manager` section):

```yaml
ai_manager:
  promote_skill_threshold: 7
  promote_safety_multiplier: 1.5
  demote_satisfaction_threshold: 30
  fire_satisfaction_threshold: 20
  cash_runway_weeks: 4
```

If no rule matches for an employee, AI does nothing for that employee that tick.

## 6. UX Flow

### Toggle

- `d` keypress: `_delegated = not _delegated`
- Header prefix updates: `🤖 위임  |  tick: N  |  ...` when ON, no prefix when OFF
- Footer `SINGLE_KEY_ROW` includes `d:위임` token (70 → 81 cells, still fits 80-wide terminals with a single wrap or the CJK width test updates)

### Auto-disable on player action

When `_delegated is True` AND the player presses any key other than `d` (e.g., F1, F7, t, etc.), the App's keypress handler:

1. Sets `_delegated = False` (player took over)
2. Forwards the keypress to its normal action (F7 promotes, etc.)
3. Header prefix clears (delegation OFF)

The `d` key itself does NOT trigger auto-disable (it's the toggle key).

### Visual indicators

| State | Header |
|---|---|
| Normal | `tick: 0  |  1년 1분기 1주차  |  ...` |
| Paused | `⏸ 일시정지  |  tick: 0  |  ...` |
| Delegated | `🤖 위임  |  tick: 0  |  ...` |
| Both | `⏸ 일시정지  |  🤖 위임  |  tick: 0  |  ...` |

(Footer unchanged, all hints still visible.)

## 7. Architecture

### New file: `src/htop_tycoon/engine/ai_manager.py`

```python
class AutoManager:
    """Deterministic heuristic auto-manager for the delegation feature.

    Pure function over (state, balance) → list of (employee_id, action) tuples.
    Does NOT mutate state; the caller (the App) is responsible for
    dispatching actions via engine.actions and applying the resulting
    state changes.
    """

    def __init__(self, balance: Mapping[str, Any]) -> None: ...
    def decide(self, state: GameState) -> list[tuple[EmployeeId, Literal["promote", "demote", "fire"]]]: ...
```

Decision logic:

```python
def decide(self, state):
    out = []
    cfg = self._cfg  # from balance["ai_manager"]
    for emp_id, emp in state.employees.items():
        if emp.tier < TIER_MAX and emp.skill >= cfg.promote_skill_threshold and state.company.cash >= promote_cost * cfg.promote_safety_multiplier:
            out.append((emp_id, "promote"))
            continue
        if emp.tier > 1 and (state.company.cash < total_salary * cfg.cash_runway_weeks or emp.satisfaction < cfg.demote_satisfaction_threshold):
            out.append((emp_id, "demote"))
            continue
        if emp.satisfaction < cfg.fire_satisfaction_threshold:
            out.append((emp_id, "fire"))
            continue
    return out
```

### Modified: `src/htop_tycoon/ui/app.py`

```python
def _tick_once(self) -> None:
    if self._paused:
        return
    if self._delegated:
        decisions = self._auto_manager.decide(self.state)
        for emp_id, action in decisions:
            if action == "promote":
                new_state, events = engine_actions.promote(self.state, emp_id)
            elif action == "demote":
                new_state, events = engine_actions.demote(self.state, emp_id)
            elif action == "fire":
                new_state, events = engine_actions.fire(self.state, emp_id)
            self._apply_state_change(new_state)
            self.event_bus.publish_many(events)
        return  # skip the normal pipeline (no product/competitor/events)
    # ... existing pipeline ...
```

**Important**: when delegated, the normal product/competitor/event pipeline is SKIPPED (otherwise AI would have to decide those too — out of scope). Only employee-management actions are taken by AI.

Wait — re-reading the user's choice "전체 자동 매니저 (모든 결정)" — the user said ALL decisions, but our heuristic rules only cover employee management. Re-scoping: the heuristic AI covers employee management only; product/competitor/events keep running their normal pipeline (the engine, not the AI, drives those). This matches what a "manager" would do in a real company — products and competitors are market forces outside manager control.

**Clarified interpretation**: "전체" = "all the *decisions the user currently makes via F-keys*" (i.e., F7/F8/F9). Product/competitor/events are not "decisions" — they are simulation. AI covers F7/F8/F9 only.

### Auto-disable wiring

In `HtopTycoonApp` keypress handlers (e.g., `action_fire_selected`):

```python
def action_fire_selected(self) -> None:
    if self._delegated:
        self._delegated = False
        self._refresh_delegate_indicator()
    action_handlers.fire_selected(self)
```

Refactor: extract a helper `_claim_control()` that disables delegation, refreshes UI, and is called by every action_* method except `action_toggle_pause` and `action_toggle_delegate`.

## 8. API Contracts

### `HtopTycoonApp.action_toggle_delegate`

Toggles `_delegated`. Refreshes header indicator and button label (if any). No state mutation in `GameState`.

### `engine.ai_manager.AutoManager.decide(state) -> list[tuple[EmployeeId, str]]`

Pure function. Does not raise on invalid state — returns empty list. Deterministic given same `(state, balance)` — tested with frozen fixture.

## 9. Testing Strategy

### Unit tests (new file `tests/test_ai_manager.py`)

- `test_decide_empty_when_no_employees`
- `test_promote_when_skill_high_and_cash_sufficient`
- `test_promote_blocked_when_cash_below_safety_multiplier`
- `test_promote_blocked_at_tier_max`
- `test_demote_when_low_cash_runway`
- `test_demote_when_satisfaction_below_threshold`
- `test_demote_blocked_at_tier_1`
- `test_fire_when_satisfaction_below_fire_threshold`
- `test_no_action_when_all_thresholds_safe`
- `test_decide_is_pure_does_not_mutate_state`
- `test_decide_is_deterministic_across_calls`

### Pilot tests (extend `tests/test_single_key_bindings_pilot.py`)

- `test_d_toggles_delegated_flag`
- `test_d_keypress_shows_robot_prefix_in_header`
- `test_d_keypress_does_not_push_modal`
- `test_other_keypress_auto_disables_delegation`
- `test_p_and_d_are_independent`

### BINDINGS test updates

- BINDINGS count: 19 → 20
- `LOCKED_SINGLE_KEY_BINDINGS` / `LOCKED_SINGLE_KEY_ROW` etc. unchanged in the 8 single-key block; the 20th entry is in the extra block
- `LOCKED_SINGLE_KEY_ROW`: append `d:위임` (70 → 81 cells)
- CJK width assertion: 70 → 81

### Scenario contract (manual QA)

1. Run app, press `d` → header shows `🤖 위임 | tick: ...`
2. Press `d` again → header prefix clears
3. Press `d`, then press `F7` → delegation auto-disables, F7 still works
4. Press `d` and `p` together → header shows both prefixes
5. AI fires promote / demote / fire correctly given fixture state

## 10. Files Affected

| File | Change | Lines (est.) |
|---|---|---|
| `src/htop_tycoon/engine/ai_manager.py` | **NEW** AutoManager class | +60 |
| `src/htop_tycoon/data/balance.yaml` | Add `ai_manager` section | +6 |
| `src/htop_tycoon/bindings/registry.py` | Add `d` to `register_extra_bindings` | +3 |
| `src/htop_tycoon/ui/app.py` | `_delegated` state + `action_toggle_delegate` + `_claim_control` helper + `_tick_once` integration | +60 |
| `src/htop_tycoon/ui/widgets/header.py` | `set_delegated(bool)` method, prefix | +20 |
| `src/htop_tycoon/ui/widgets/footer.py` | `SINGLE_KEY_ROW` append `d:위임` | +1 |
| `src/htop_tycoon/ui/action_handlers.py` | `toggle_delegate` handler + export | +10 |
| `tests/test_ai_manager.py` | **NEW** — 11 unit tests | +200 |
| `tests/test_single_key_bindings_pilot.py` | 5 new tests + BINDINGS count 20 | +120 |
| `tests/test_header_footer_pilot.py` | `LOCKED_SINGLE_KEY_ROW` width 81 | +5 |
| `tests/test_cjk_theme_audit.py` | width assertion 81 | +3 |
| `tests/test_app_pilot.py` | BINDINGS count 20 | +2 |
| `tests/test_bindings_pilot.py` | comment update | +3 |
| `README.md` | keybindings row | +1 |
| `docs/superpowers/specs/2026-06-29-delegation-design.md` | **NEW** this file | +200 |

**Total estimated: ~700 lines**

## 11. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| AI fires too many actions per tick (cascade) | `decide()` evaluates ALL employees but action handlers run sequentially in the same tick; if state goes out of budget mid-loop, subsequent promotes are blocked by the cash precondition on the next state. Unit tests cover the cash guard. |
| AI fires when player doesn't want it | Auto-disable on any non-`d` keypress; UI shows delegation state. |
| Heuristic rules feel arbitrary / exploitable | Defaults are conservative (promote_skill_threshold=7, safety_multiplier=1.5). All thresholds live in `balance.yaml` so they're tunable without code changes. |
| `_tick_once` double-pipeline (AI acts, then normal engine runs) | AI path RETURNS EARLY after processing; normal engine only runs when not delegated. |
| `d` key conflicts with future debug/dev mode | `d` is mnemonic for "delegate"; the locked F-row pattern is preserved. If dev mode is added later, it can use a different key (e.g., `ctrl+d` chord). |

## 12. Open Questions

None — all design decisions resolved in the interview:

1. Scope: 전체 자동 매니저 (employee management only — products/competitors/events remain engine-driven)
2. Intervention: 일시중지 + 수동재개 (toggle on `d`, auto-disable on any other key)
3. Strategy: 휴리스틱 규칙 기반
4. Shortcut: `d`
