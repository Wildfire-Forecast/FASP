"""Known ground-truth fire cluster placements from world setup.

Single source of truth for the fire clusters LustraApp.setup_simulation()
spawns via WorldBuilder.spawn_fire() -- kept here (instead of inline in
app.py) so the accuracy instrumentation and the spawn calls can't drift
apart. If you change where fires spawn, edit this list; app.py loops over
it to call spawn_fire().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class FireSpawnSpec:
    name: str
    center_pos: Tuple[float, float, float]
    grid_size: int
    max_radius: float
    max_scale: float

    @property
    def center_xy(self) -> Tuple[float, float]:
        return (float(self.center_pos[0]), float(self.center_pos[1]))

    @property
    def radius_m(self) -> float:
        # The largest fire billboard (scale=max_scale) spawns at the cluster
        # center, so max_scale/2 is a reasonable true-extent radius -- the
        # grid_size/max_radius jitter around the center is small (<=1 m) by
        # comparison.
        return float(self.max_scale) / 2.0


FIRE_SPAWN_SPECS = [
    FireSpawnSpec("fire_1", (25.0, 25.0, 1.0), grid_size=7, max_radius=0.5, max_scale=20.0),
    FireSpawnSpec("fire_2", (70.0, -10.0, 1.0), grid_size=8, max_radius=0.5, max_scale=15.0),
    FireSpawnSpec("fire_3", (-50.0, -25.0, 1.0), grid_size=6, max_radius=0.5, max_scale=25.0),
]
