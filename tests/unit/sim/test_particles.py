# tests/unit/sim/test_particles.py
"""Unit tests for FountainSimulator and RNG functions."""

import numpy as np

from sim.particles import FountainSimulator, ParticleBirth, rng_float


def test_rng_float_determinism():
    """Same seed + idx returns same float."""
    a = rng_float(42, 0, 0.0, 1.0)
    b = rng_float(42, 0, 0.0, 1.0)
    assert a == b
    c = rng_float(43, 0, 0.0, 1.0)
    assert a != c


def test_rng_float_bounds():
    """Returns values within [min, max]."""
    for i in range(100):
        val = rng_float(42, i, 5.0, 10.0)
        assert 5.0 <= val <= 10.0


def test_fountain_simulator_initial():
    """Check simulator initialises correctly."""
    sim = FountainSimulator(gravity=9.81, water_level=0.0)
    assert sim.gravity == 9.81
    assert sim.water_level == 0.0
    assert sim.particles == []


def test_add_conical_fountain():
    """Test particle generation count and attribute setting."""
    sim = FountainSimulator()
    sim.add_conical_fountain(
        num_particles=10,
        apex_x=0, apex_y=1.5, apex_z=14,
        cone_height=2.0,
        cone_angle_rad=np.pi / 6,
        base_radius=1.75,
        speed_min=3.0, speed_max=8.0,
        birth_start=0.0, birth_end=0.5,
        size_min=0.01, size_max=0.03,
        seed_offset=42,
    )
    assert len(sim.particles) == 10
    for i, p in enumerate(sim.particles):
        assert p.seed == 42 + i
        assert p.texture == "WaterTexture"


def test_evaluate_at_time_before_birth():
    """No particles before birth time."""
    sim = FountainSimulator()
    sim.add_conical_fountain(
        num_particles=1,
        apex_x=0, apex_y=1.5, apex_z=0,
        cone_height=1, cone_angle_rad=0.1, base_radius=0.5,
        speed_min=1, speed_max=2,
        birth_start=1.0, birth_end=1.0,
        size_min=0.01, size_max=0.02,
        seed_offset=0
    )
    states = sim.evaluate_at_time(0.5)
    assert len(states) == 0


def test_evaluate_at_time_after_impact():
    """Particle removed after impact time."""
    sim = FountainSimulator(gravity=9.81, water_level=0.0)
    birth = ParticleBirth(
        particle_id=0,
        birth_time=0.0,
        x0=0, y0=10, z0=0,
        vx0=0, vy0=0, vz0=0,
        size=0.02,
        texture="WaterTexture",
        seed=1,
        impact_time=1.428
    )
    sim._particles = [birth]
    states = sim.evaluate_at_time(1.0)
    assert len(states) == 1
    states = sim.evaluate_at_time(2.0)
    assert len(states) == 0


def test_impact_time_math():
    """Verify analytic impact time calculation."""
    sim = FountainSimulator(gravity=9.81, water_level=0.0)

    # Case: y0=10, vy0=0 (dropped from rest)
    impact = sim._compute_impact_time(10.0, 0.0)
    assert impact is not None
    assert abs(impact - np.sqrt(2 * 10 / 9.81)) < 1e-6

    # Case: y0=10, vy0=5 (thrown upward)
    impact = sim._compute_impact_time(10.0, 5.0)
    expected = (5 + np.sqrt(25 + 2 * 9.81 * 10)) / 9.81
    assert abs(impact - expected) < 1e-6

    # Case: y0=10, vy0=-5 (thrown downward)
    impact = sim._compute_impact_time(10.0, -5.0)
    # Equation: -0.5*9.81*t^2 -5*t + 10 = 0
    # Multiply by -2: 9.81*t^2 + 10*t - 20 = 0
    # Positive root: t = (-10 + sqrt(100 + 4*9.81*20)) / (2*9.81)
    expected = (-10 + np.sqrt(100 + 4 * 9.81 * 20)) / (2 * 9.81)
    assert abs(impact - expected) < 1e-6


def test_energy_conservation_without_collision():
    """Energy should be conserved for analytic trajectories."""
    sim = FountainSimulator(gravity=9.81, water_level=-10)
    sim.add_conical_fountain(
        num_particles=1,
        apex_x=0, apex_y=10, apex_z=0,
        cone_height=1, cone_angle_rad=0.1, base_radius=0.5,
        speed_min=2, speed_max=2,
        birth_start=0, birth_end=0,
        size_min=0.02, size_max=0.02,
        seed_offset=0
    )

    def energy(state):
        mass = state['size']
        v2 = state['velocity_x']**2 + state['velocity_y']**2 + state['velocity_z']**2
        ke = 0.5 * mass * v2
        pe = mass * sim.gravity * state['position_y']
        return ke + pe

    s1 = sim.evaluate_at_time(0.0)[0]
    s2 = sim.evaluate_at_time(0.5)[0]
    e1 = energy(s1)
    e2 = energy(s2)
    assert abs(e1 - e2) < 1e-9
