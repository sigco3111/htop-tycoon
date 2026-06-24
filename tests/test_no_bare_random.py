"""Static guard: no bare ``random.<func>`` calls anywhere in src/.

Anti-pattern from AGENTS.md: "No bare ``random.*`` outside rng.py or the
RNG adapter. Use GameRNG(seed)." This test fails the suite if a stray
``random.choice`` / ``random.randint`` / etc. slips into any module other
than ``engine/rng.py``.

The exception list below intentionally contains only ``engine/rng.py``
because that file is the single sanctioned adapter for stdlib ``random``.
"""

from __future__ import annotations

import re
from pathlib import Path

# Project layout constants.
SRC_ROOT = Path("src") / "htop_tycoon"
RNG_MODULE_RELATIVE = SRC_ROOT / "engine" / "rng.py"

# Matches ``random.<name>(`` where name is one of the documented offenders.
BARE_RANDOM_PATTERN = re.compile(
    r"\brandom\.(choice|randint|random|uniform|sample|shuffle)\b"
)


def _iter_python_files(exclude: Path) -> list[Path]:
    """Yield all .py files under src/htop_tycoon/, excluding ``exclude``."""
    if not SRC_ROOT.exists():
        return []
    files: list[Path] = []
    for path in SRC_ROOT.rglob("*.py"):
        if path.resolve() == exclude.resolve():
            continue
        files.append(path)
    return files


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_no, line) for every offending match in ``path``."""
    matches: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if BARE_RANDOM_PATTERN.search(line):
            matches.append((line_no, line.strip()))
    return matches


class TestNoBareRandom:
    """Guard rails: every ``random.<func>(...)`` outside rng.py is a defect."""

    def test_no_bare_random_in_src(self) -> None:
        """Given: every .py under src/htop_tycoon/ except engine/rng.py
        When: scanned for ``random.(choice|randint|random|uniform|sample|shuffle)``
        Then: zero matches (otherwise fail with offending file + line)
        """
        offenders: list[str] = []
        for path in _iter_python_files(exclude=RNG_MODULE_RELATIVE):
            for line_no, line in _scan_file(path):
                rel = path.as_posix()
                offenders.append(f"{rel}:{line_no}: {line}")
        assert offenders == [], (
            "Bare stdlib random.<func> usage detected outside rng.py. "
            "Use GameRNG(seed) instead.\n"
            + "\n".join(offenders)
        )

    def test_rng_module_exists_and_is_excluded(self) -> None:
        """Given: the src tree
        When: we list the files the scan would examine
        Then: engine/rng.py exists (otherwise the wrapper contract is unmet)
        """
        assert RNG_MODULE_RELATIVE.exists(), (
            "engine/rng.py missing — the GameRNG adapter must exist before "
            "the rest of the codebase can avoid bare random.<func>."
        )

    def test_helper_iter_excludes_rng(self) -> None:
        """Given: a populated src/htop_tycoon/ tree
        When: the file iterator runs
        Then: engine/rng.py is never yielded
        """
        yielded = {p.resolve() for p in _iter_python_files(exclude=RNG_MODULE_RELATIVE)}
        assert RNG_MODULE_RELATIVE.resolve() not in yielded


class TestNoBareRandomGuardContract:
    """Self-test: the regex actually catches the pattern we ban."""

    def test_pattern_detects_bare_random_choice(self) -> None:
        """Given: the regex
        When: applied to a string containing ``random.choice([1])``
        Then: it matches
        """
        assert BARE_RANDOM_PATTERN.search("random.choice([1])")

    def test_pattern_detects_bare_random_randint(self) -> None:
        """Given: the regex
        When: applied to a string containing ``random.randint(0, 9)``
        Then: it matches
        """
        assert BARE_RANDOM_PATTERN.search("random.randint(0, 9)")

    def test_pattern_ignores_rng_attribute_access(self) -> None:
        """Given: the regex
        When: applied to ``rng.random`` (a hypothetical attribute)
        Then: it does NOT match (we only flag bare-module usage)
        """
        assert not BARE_RANDOM_PATTERN.search("rng.random")

    def test_pattern_ignores_word_random_in_identifier(self) -> None:
        """Given: the regex
        When: applied to ``my_random.choice`` (subword reference)
        Then: it does NOT match (word-boundary respected)
        """
        assert not BARE_RANDOM_PATTERN.search("my_random.choice([1])")

    def test_pattern_ignores_import_line(self) -> None:
        """Given: the regex
        When: applied to ``import random``
        Then: it does NOT match (no call site)
        """
        assert not BARE_RANDOM_PATTERN.search("import random")
