"""T28: JSON deserialize + safe corruption recovery (deterministic seed).

This module is the *read* half of the persistence layer. The *write* half
(``serialize`` / ``save``) lives in T27.

Two public functions:

- :func:`deserialize` -- convert a v1/v2 envelope (``{"version": 1 or 2,
  "state": {...}, "saved_at_iso": "..."}``) back to a
  :class:`~htop_tycoon.domain.state.GameState`. On ANY error (missing key,
  unknown version, bad field type, malformed envelope), log a warning and
  return :func:`new_game` seeded with :data:`CORRUPTION_RECOVERY_SEED`.
  NEVER raises.
- :func:`load` -- read JSON from ``path`` and delegate to :func:`deserialize`.
  On ``json.JSONDecodeError`` from the primary file, tries
  ``path.with_suffix('.bak')``. If the backup also fails to parse, returns
  the recovery state. On ``FileNotFoundError``, returns the recovery state
  without consulting backup.

Load-from-JSON materialization:

After ``serialize`` -> JSON -> ``deserialize`` the nested ``departments`` /
``employees`` / ``products`` / ``competitors`` fields are raw dicts (from
``dataclasses.asdict``). The fix is ``_materialize_loaded_state``: walk each
collection and convert shape-valid entries to their typed dataclass via
``Domain(**...)``. Malformed entries are left as raw dicts (partial
corruption degrades gracefully). UI consumers in v0.2.0 expect typed
objects; without this materialize step, ``OrgTree``, ``EmployeeTable``,
and ``DepartmentDetail`` crash on attribute access.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Any

from htop_tycoon.domain.state import (
    Company,
    GameState,
    GameTime,
    new_game,
)
from htop_tycoon.domain.regimes import default_regime_state
from htop_tycoon.persistence.serialize import SCHEMA_VERSION

__all__ = ["CORRUPTION_RECOVERY_SEED", "deserialize", "load"]

CORRUPTION_RECOVERY_SEED: int = 0

_logger = logging.getLogger(__name__)


def _recovery_state() -> GameState:
    return new_game(CORRUPTION_RECOVERY_SEED)


def _materialize_loaded_state(state: GameState) -> GameState:
    """Reconstruct typed domain objects from JSON-derived nested dicts.

    Live in-memory states pass through unchanged. JSON-loaded states
    have raw dicts in the four nested collections; this function walks
    each and reconstructs ``Department``/``Employee``/``Product``/
    ``Competitor`` instances via ``Domain(**...)`` so the v0.2.0 widgets
    (which read ``emp.id``, ``dept.type.value``, etc.) work.

    Forgiving: malformed entries (missing required fields, unknown
    enum values) are left as raw dicts. Partial corruption degrades
    gracefully; full corruption is the recovery path's responsibility
    (not reached here because ``Company``/``GameTime`` already
    reconstructed successfully above the materialize call).
    """
    from htop_tycoon.domain.dept import Department, DepartmentType
    from htop_tycoon.domain.employee import Employee
    from htop_tycoon.domain.market import Competitor
    from htop_tycoon.domain.product import (
        LifecycleStage,
        Product,
        ProductType,
    )

    def _safe_dept(d: Any) -> Any:
        if not isinstance(d, dict):
            return d
        try:
            type_obj = d.get("type")
            if isinstance(type_obj, str):
                try:
                    type_obj = DepartmentType(type_obj)
                except ValueError:
                    return d
            return Department(
                id=d.get("id"),
                type=type_obj,
                head_employee_id=d.get("head_employee_id"),
                employee_ids=list(d.get("employee_ids") or []),
                founded_tick=int(d.get("founded_tick", 0)),
                unlocked=bool(d.get("unlocked", False)),
            )
        except (KeyError, TypeError, ValueError):
            return d

    def _safe_emp(e: Any) -> Any:
        if not isinstance(e, dict):
            return e
        try:
            return Employee(
                id=e.get("id"),
                name=e.get("name"),
                dept_id=e.get("dept_id"),
                skill=int(e.get("skill", 1)),
                tier=int(e.get("tier", 1)),
                salary_per_week=int(e.get("salary_per_week", 0)),
                satisfaction=int(e.get("satisfaction", 60)),
                hired_tick=int(e.get("hired_tick", 0)),
            )
        except (KeyError, TypeError, ValueError):
            return e

    def _safe_product(p: Any) -> Any:
        if not isinstance(p, dict):
            return p
        try:
            type_obj = p.get("type")
            if isinstance(type_obj, str):
                try:
                    type_obj = ProductType(type_obj)
                except ValueError:
                    return p
            stage_obj = p.get("lifecycle")
            if isinstance(stage_obj, str):
                try:
                    stage_obj = LifecycleStage(stage_obj)
                except ValueError:
                    return p
            return Product(
                id=p.get("id"),
                type=type_obj,
                lifecycle=stage_obj,
                weeks_in_stage=int(p.get("weeks_in_stage", 0)),
                market_share=float(p.get("market_share", 0.0)),
                revenue_per_week=int(p.get("revenue_per_week", 0)),
            )
        except (KeyError, TypeError, ValueError):
            return p

    def _safe_competitor(c: Any) -> Any:
        if not isinstance(c, dict):
            return c
        try:
            name = c.get("name")
            if not isinstance(name, str):
                name = ""
            cid = c.get("id")
            if not isinstance(cid, str):
                cid = "comp-default"
            return Competitor(
                id=cid,
                name=name,
                market_share=float(c.get("market_share", 0.0)),
                aggression=float(c.get("aggression", 0.0)),
                cash=int(c.get("cash", 0)),
                alive=bool(c.get("alive", True)),
            )
        except (KeyError, TypeError, ValueError):
            return c

    def _safe_regime(r: Any) -> Any:
        from htop_tycoon.domain.regimes import RegimeState, RegimeType
        if not isinstance(r, dict):
            return r
        try:
            current = r.get("current", "NORMAL")
            if isinstance(current, str):
                current = RegimeType(current)
            return RegimeState(
                current=current,
                weeks_in_regime=int(r.get("weeks_in_regime", 0)),
                started_tick=int(r.get("started_tick", 0)),
            )
        except (KeyError, TypeError, ValueError):
            return r

    raw_depts = state.departments
    raw_emps = state.employees
    raw_prods = state.products
    raw_comps = state.competitors
    raw_regime = state.regime

    new_depts = (
        {k: _safe_dept(v) for k, v in raw_depts.items()}
        if isinstance(raw_depts, dict)
        else raw_depts
    )
    new_emps = (
        {k: _safe_emp(v) for k, v in raw_emps.items()}
        if isinstance(raw_emps, dict)
        else raw_emps
    )
    new_prods = (
        {k: _safe_product(v) for k, v in raw_prods.items()}
        if isinstance(raw_prods, dict)
        else raw_prods
    )
    new_comps = (
        {k: _safe_competitor(v) for k, v in raw_comps.items()}
        if isinstance(raw_comps, dict)
        else raw_comps
    )
    new_regime = _safe_regime(raw_regime) if raw_regime else raw_regime

    if (
        new_depts is raw_depts
        and new_emps is raw_emps
        and new_prods is raw_prods
        and new_comps is raw_comps
        and new_regime is raw_regime
    ):
        return state
    return dataclasses.replace(
        state,
        departments=new_depts,
        employees=new_emps,
        products=new_prods,
        competitors=new_comps,
        regime=new_regime,
    )


def deserialize(data: dict[str, Any]) -> GameState:
    """Convert a v1/v2 envelope to a GameState, or return recovery state.

    Returns the recovery state (seed=0, new_game) on any error:
    missing key, wrong type, unknown version, bad field type, malformed
    envelope. Versions < ``SCHEMA_VERSION`` are auto-migrated via
    :func:`upgrade_v1_to_v2`. Versions > ``SCHEMA_VERSION`` fall through
    to recovery (future migration plan must add an upgrade_vN_to_v2 step).

    On success, runs the loaded state through
    :func:`_materialize_loaded_state` so that ``Department`` /
    ``Employee`` / ``Product`` / ``Competitor`` entries are typed
    dataclass instances (not raw JSON-derived dicts).
    """
    try:
        version_raw = data["version"]  # KeyError -> recovery
        if not isinstance(version_raw, int) or isinstance(version_raw, bool):
            _logger.warning(
                "deserialize: version is not a real int (got %r); recovering",
                type(version_raw).__name__,
            )
            return _recovery_state()
        if version_raw < SCHEMA_VERSION:
            from htop_tycoon.persistence.migration import upgrade_v1_to_v2

            upgraded = upgrade_v1_to_v2(data)
            _logger.info(
                "deserialize: migrated save from v1 -> v2 (regime + dept_focus default)"
            )
            return deserialize(upgraded)
        if version_raw > SCHEMA_VERSION:
            _logger.warning(
                "deserialize: unknown schema version %r (expected %d); recovering",
                version_raw,
                SCHEMA_VERSION,
            )
            return _recovery_state()

        state_dict = data["state"]  # KeyError -> recovery
        if not isinstance(state_dict, dict):
            _logger.warning(
                "deserialize: 'state' is not a dict (got %s); recovering",
                type(state_dict).__name__,
            )
            return _recovery_state()

        company = Company(**state_dict["company"])  # KeyError/TypeError/ValueError
        game_time = GameTime(**state_dict["game_time"])  # KeyError/ValueError

        # v2 schema adds two new fields. They are present in fresh v2
        # saves; for older v2 saves written before T45 the migration path
        # filled them in via upgrade_v1_to_v2. Default the fields to
        # their typed empty values when missing so GameState can be
        # constructed typed.
        from htop_tycoon.domain.regimes import RegimeState, RegimeType
        regime_dict = state_dict.get("regime")
        if not isinstance(regime_dict, dict) or not regime_dict:
            regime_obj: RegimeState = default_regime_state()
        else:
            current = regime_dict.get("current", "NORMAL")
            if isinstance(current, str):
                current = RegimeType(current)
            regime_obj = RegimeState(
                current=current,
                weeks_in_regime=int(regime_dict.get("weeks_in_regime", 0)),
                started_tick=int(regime_dict.get("started_tick", 0)),
            )
        dept_focus_value: dict[Any, Any] = state_dict.get("dept_focus", {}) or {}
        if not isinstance(dept_focus_value, dict):
            dept_focus_value = {}

        new_state = GameState(
            company=company,
            departments=state_dict["departments"],
            employees=state_dict["employees"],
            products=state_dict["products"],
            competitors=state_dict["competitors"],
            events_active=state_dict["events_active"],
            ending_history=state_dict["ending_history"],
            secret_investor_cleared=state_dict["secret_investor_cleared"],
            tick=state_dict["tick"],
            rng_seed=state_dict["rng_seed"],
            game_time=game_time,
            dept_focus=dept_focus_value,
            regime=regime_obj,
            version=state_dict.get("version", 1),
        )
        # Materialize: convert JSON-derived dicts in departments/employees
        # /products/competitors back to typed dataclass instances so
        # v0.2.0 UI consumers (which read attributes) don't crash.
        return _materialize_loaded_state(new_state)
    except (KeyError, TypeError, ValueError) as exc:
        _logger.warning(
            "deserialize: corruption detected (%s: %s); recovering with seed=%d",
            type(exc).__name__,
            exc,
            CORRUPTION_RECOVERY_SEED,
        )
        return _recovery_state()


def load(path: Path) -> GameState:
    """Load a :class:`GameState` from ``path``, with backup fallback and recovery."""
    try:
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            _logger.warning(
                "load: primary file at %s is not valid JSON (%s); trying backup",
                path,
                exc,
            )
            return _load_from_backup(path, exc)
    except FileNotFoundError:
        _logger.warning("load: primary file at %s not found; recovering", path)
        return _recovery_state()
    except OSError as exc:
        _logger.warning(
            "load: OS error reading %s (%s); recovering", path, exc
        )
        return _recovery_state()

    if not isinstance(data, dict):
        _logger.warning(
            "load: top-level JSON in %s is not a dict (got %s); recovering",
            path,
            type(data).__name__,
        )
        return _recovery_state()

    return deserialize(data)


def _load_from_backup(path: Path, primary_error: json.JSONDecodeError) -> GameState:
    backup_path = path.with_suffix(".bak")
    try:
        backup_text = backup_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _logger.warning(
            "load: backup file at %s not found; recovering (primary was: %s)",
            backup_path,
            primary_error,
        )
        return _recovery_state()
    except OSError as exc:
        _logger.warning(
            "load: OS error reading backup %s (%s); recovering", backup_path, exc
        )
        return _recovery_state()

    try:
        backup_data = json.loads(backup_text)
    except json.JSONDecodeError as exc:
        _logger.warning(
            "load: backup file at %s is also not valid JSON (%s); recovering",
            backup_path,
            exc,
        )
        return _recovery_state()

    if not isinstance(backup_data, dict):
        _logger.warning(
            "load: backup file at %s top-level is not a dict (got %s); recovering",
            backup_path,
            type(backup_data).__name__,
        )
        return _recovery_state()

    _logger.warning(
        "load: using backup at %s (primary was corrupt: %s)",
        backup_path,
        primary_error,
    )
    return deserialize(backup_data)
