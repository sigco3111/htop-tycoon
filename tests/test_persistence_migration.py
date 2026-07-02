import pytest

from htop_tycoon.persistence.migration import _MIGRATIONS, register_migration, upgrade_save
from htop_tycoon.persistence.serialize import SCHEMA_VERSION


def test_register_migration_happy_path() -> None:
    """vN -> vN+1 migration registers and runs against current SCHEMA_VERSION."""
    from_v = SCHEMA_VERSION - 1
    to_v = SCHEMA_VERSION
    try:
        @register_migration(from_v, to_v)
        def add_field(payload: dict) -> dict:
            payload["new_field"] = "x"
            payload["schema_version"] = to_v
            return payload

        result = {"schema_version": from_v, "data": "old"}
        upgraded = upgrade_save(result)
        assert upgraded["schema_version"] == to_v
        assert upgraded["new_field"] == "x"
        # registration stored in module registry
        assert _MIGRATIONS[from_v] is add_field  # type: ignore[index]
    finally:
        _MIGRATIONS.pop(from_v, None)


def test_register_migration_rejects_non_sequential() -> None:
    """register_migration(from, to) requires to == from + 1."""
    with pytest.raises(ValueError, match="must be sequential"):
        register_migration(2, 5)  # type: ignore[call-arg]


def test_register_migration_rejects_duplicate_from_version() -> None:
    """register_migration raises when from_version already taken."""
    from_v = SCHEMA_VERSION - 2
    to_v = from_v + 1
    try:
        register_migration(from_v, to_v)(lambda p: p)
        with pytest.raises(ValueError, match="already registered"):
            register_migration(from_v, to_v)(lambda p: p)  # second raises
    finally:
        _MIGRATIONS.pop(from_v, None)


def test_register_migration_decorator_returns_function() -> None:
    """Decorator must return the decorated function unchanged."""
    def my_fn(p: dict) -> dict:
        return p
    from_v = SCHEMA_VERSION - 3
    to_v = from_v + 1
    try:
        decorated = register_migration(from_v, to_v)(my_fn)
        assert decorated is my_fn
    finally:
        _MIGRATIONS.pop(from_v, None)


def test_upgrade_save_no_op_when_current() -> None:
    """upgrade_save returns payload unchanged when already at SCHEMA_VERSION."""
    from htop_tycoon.persistence.serialize import SCHEMA_VERSION

    payload = {"schema_version": SCHEMA_VERSION, "data": "test"}
    result = upgrade_save(payload)
    assert result is not None
    assert result["schema_version"] == SCHEMA_VERSION


def test_upgrade_save_walks_multi_step_chain() -> None:
    """upgrade_save chains multiple migrations vN -> vN+1 -> vN+2."""
    v1 = SCHEMA_VERSION - 2
    v2 = SCHEMA_VERSION - 1
    v3 = SCHEMA_VERSION
    try:
        @register_migration(v1, v2)
        def step1(p: dict) -> dict:
            p["v2_added"] = True
            p["schema_version"] = v2
            return p

        @register_migration(v2, v3)
        def step2(p: dict) -> dict:
            p["v3_added"] = True
            p["schema_version"] = v3
            return p

        payload = {"schema_version": v1, "data": "old"}
        result = upgrade_save(payload)
        assert result["schema_version"] == v3
        assert result.get("v2_added") is True
        assert result.get("v3_added") is True
    finally:
        _MIGRATIONS.pop(v1, None)
        _MIGRATIONS.pop(v2, None)


def test_upgrade_save_raises_on_missing_migration() -> None:
    """upgrade_save raises ValueError when chain has a gap."""
    missing_from = SCHEMA_VERSION - 5
    payload = {"schema_version": missing_from, "data": "old"}
    # Ensure there's no migration registered for missing_from
    _MIGRATIONS.pop(missing_from, None)
    with pytest.raises(ValueError, match="no migration registered"):
        upgrade_save(payload)


def test_upgrade_save_deep_copies_input() -> None:
    """upgrade_save must not mutate the input dict."""
    from_v = SCHEMA_VERSION - 1
    to_v = SCHEMA_VERSION
    try:
        @register_migration(from_v, to_v)
        def noop_mutation(p: dict) -> dict:
            p["schema_version"] = to_v
            return p

        original = {"schema_version": from_v, "data": "test"}
        original_snapshot = dict(original)
        result = upgrade_save(original)
        # Original should be unchanged
        assert original == original_snapshot
        # Result is a separate dict and updated
        assert result is not original
        assert result["schema_version"] == to_v
    finally:
        _MIGRATIONS.pop(from_v, None)
