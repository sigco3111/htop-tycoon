"""Quality axes (4 dimensions 0..100) + Progress (0..100, monotonic)."""

from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


@dataclass(frozen=True, slots=True)
class QualityAxes:
    fun: int = 0
    graphics: int = 0
    sound: int = 0
    originality: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "fun", _clamp(self.fun))
        object.__setattr__(self, "graphics", _clamp(self.graphics))
        object.__setattr__(self, "sound", _clamp(self.sound))
        object.__setattr__(self, "originality", _clamp(self.originality))

    def sum(self) -> int:
        return self.fun + self.graphics + self.sound + self.originality


@dataclass(frozen=True, slots=True)
class Progress:
    value: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _clamp(self.value))

    @property
    def is_complete(self) -> bool:
        return self.value == 100

    def with_increment(self, delta: int) -> Progress:
        return Progress(self.value + delta)
