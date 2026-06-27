# src/sim/particles.py
"""V1 Fountain Simulation Core - Analytic, time-based particle system.

No numerical integration. No environmental forces.
Deterministic, reproducible, and frame-rate independent.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

# ----------------------------------------------------------------------------
# Deterministic stateless RNG (splitmix64)
# ----------------------------------------------------------------------------

def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    x = (x ^ (x >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return (x ^ (x >> 31)) & 0xFFFFFFFFFFFFFFFF


def rng_float(seed: int, idx: int, min_val: float, max_val: float) -> float:
    """Deterministic hash-based float in [min_val, max_val]."""
    h = _splitmix64(seed + idx)
    return min_val + (h / 2**64) * (max_val - min_val)


# ----------------------------------------------------------------------------
# Particle Birth Record
# ----------------------------------------------------------------------------

@dataclass
class ParticleBirth:
    """Immutable initial conditions for a single particle."""
    particle_id: int
    birth_time: float
    x0: float
    y0: float
    z0: float
    vx0: float
    vy0: float
    vz0: float
    size: float
    texture: str
    seed: int
    impact_time: float | None = None  # absolute time of death (if computed)


# ----------------------------------------------------------------------------
# Fountain Simulator (V1)
# ----------------------------------------------------------------------------

class FountainSimulator:
    """Deterministic fountain particle generator.

    Produces ParticleBirth records for a conical fountain.
    """

    def __init__(self, gravity: float = 9.81, water_level: float = 0.0):
        self.gravity = gravity
        self.water_level = water_level
        self._particles: list[ParticleBirth] = []
        self._next_id = 0

    def _compute_impact_time(self, y0: float, vy0: float) -> float | None:
        """Solve for relative impact time when particle hits water plane."""
        if y0 <= self.water_level:
            return 0.0  # born dead

        # Quadratic: -0.5*g*t^2 + vy0*t + (y0 - water_level) = 0
        a = -0.5 * self.gravity
        b = vy0
        c = y0 - self.water_level
        disc = b * b - 4 * a * c
        if disc < 0:
            return None  # never hits
        sqrt_disc = np.sqrt(disc)
        t1 = (-b + sqrt_disc) / (2 * a)
        t2 = (-b - sqrt_disc) / (2 * a)
        roots = [r for r in (t1, t2) if r > 0]
        return min(roots) if roots else None

    def add_conical_fountain(
        self,
        num_particles: int,
        apex_x: float,
        apex_y: float,
        apex_z: float,
        cone_height: float,
        cone_angle_rad: float,
        base_radius: float,
        speed_min: float,
        speed_max: float,
        birth_start: float,
        birth_end: float,
        size_min: float,
        size_max: float,
        texture: str = "WaterTexture",
        seed_offset: int = 0,
    ) -> None:
        """Generate particles in a conical fountain pattern.

        All particles are born with uniform random distribution within the cone.
        """
        for i in range(num_particles):
            seed = seed_offset + i

            # Deterministic random values
            birth_time = rng_float(seed, 0, birth_start, birth_end)
            height = rng_float(seed, 1, 0.0, cone_height)
            angle = rng_float(seed, 2, 0.0, 2.0 * np.pi)
            radius_factor = rng_float(seed, 3, 0.0, 1.0)
            radius = base_radius * (1.0 - height / cone_height) * radius_factor

            x0 = apex_x + radius * np.cos(angle)
            y0 = apex_y + height
            z0 = apex_z + radius * np.sin(angle)

            vel_angle = rng_float(seed, 4, -cone_angle_rad, cone_angle_rad)
            vel_mag = rng_float(seed, 5, speed_min, speed_max)
            az_angle = rng_float(seed, 6, 0.0, 2.0 * np.pi)

            vx0 = vel_mag * np.cos(vel_angle) * np.cos(az_angle)
            vy0 = vel_mag * np.sin(vel_angle)
            vz0 = vel_mag * np.cos(vel_angle) * np.sin(az_angle)

            size = rng_float(seed, 7, size_min, size_max)

            impact_rel = self._compute_impact_time(y0, vy0)
            impact_time = birth_time + impact_rel if impact_rel is not None else None

            birth = ParticleBirth(
                particle_id=self._next_id,
                birth_time=birth_time,
                x0=x0, y0=y0, z0=z0,
                vx0=vx0, vy0=vy0, vz0=vz0,
                size=size,
                texture=texture,
                seed=seed,
                impact_time=impact_time,
            )
            self._particles.append(birth)
            self._next_id += 1

    def evaluate_at_time(self, t: float) -> list[dict[str, Any]]:
        """Return list of alive particle states at absolute time t."""
        states = []
        for b in self._particles:
            # Not yet born
            if t < b.birth_time:
                continue
            # Dead by impact
            if b.impact_time is not None and t >= b.impact_time:
                continue

            dt = t - b.birth_time
            x = b.x0 + b.vx0 * dt
            y = b.y0 + b.vy0 * dt - 0.5 * self.gravity * dt * dt
            z = b.z0 + b.vz0 * dt

            # Safety check (should never be below water if impact_time correct)
            if y <= self.water_level:
                continue

            states.append({
                'particle_id': b.particle_id,
                'position_x': float(x),
                'position_y': float(y),
                'position_z': float(z),
                'velocity_x': float(b.vx0),
                'velocity_y': float(b.vy0 - self.gravity * dt),
                'velocity_z': float(b.vz0),
                'size': float(b.size),
                'texture': b.texture,
                'status': 'alive',
            })
        return states

    @property
    def particles(self) -> list[ParticleBirth]:
        """Return the list of particle births."""
        return self._particles

    def clear(self) -> None:
        """Clear all particles and reset ID counter."""
        self._particles = []
        self._next_id = 0
