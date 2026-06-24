"""Engine package marker for htop-tycoon.

Holds deterministic, side-effect-free game logic: RNG, tick loop, state
transitions, event production. UI must NOT mutate state directly — engine
functions are the only writers.
"""

from __future__ import annotations

