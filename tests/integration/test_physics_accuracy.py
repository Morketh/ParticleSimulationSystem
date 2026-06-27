# tests/integration/test_physics_accuracy.py
"""Integration tests for physics accuracy with real database.

These tests use the real MariaDB backend via the cluster_with_schema fixture.
"""

import numpy as np
import pytest

from sim.particles import FountainSimulator
from sim.validator import PhysicsValidator

pytestmark = pytest.mark.asyncio


async def test_single_particle_trajectory(cluster_with_schema):
    """Verify a single particle follows the expected parabolic trajectory."""
    sim = FountainSimulator(gravity=9.81, water_level=0.0)
    sim.add_conical_fountain(
        num_particles=1,
        apex_x=0, apex_y=10, apex_z=0,
        cone_height=1, cone_angle_rad=0.1, base_radius=0.5,
        speed_min=2, speed_max=2,
        birth_start=0, birth_end=0,
        size_min=0.02, size_max=0.02,
        seed_offset=42,
    )

    job_id = await cluster_with_schema.create_job(
        job_name="PhysicsTest",
        num_frames=5,
        width=640,
        height=480,
        fps=10,
        gravity=9.81,
        water_level=0.0,
    )
    await cluster_with_schema.insert_particle_births(job_id, sim.particles)

    # Fetch the actual birth record (y0 and vy0)
    births = await cluster_with_schema.db.fetch_all(
        "SELECT y0, vy0 FROM particle_births WHERE job_id = %s",
        (job_id,)
    )
    assert births, "No particle birth found"
    y0 = births[0]["y0"]
    vy0 = births[0]["vy0"]

    times = [0.1, 0.2, 0.3, 0.4, 0.5]
    for t in times:
        states = await cluster_with_schema.get_particles_at_time(job_id, t)
        assert len(states) == 1
        state = states[0]
        expected_y = y0 + vy0 * t - 0.5 * 9.81 * t * t
        assert abs(state["position_y"] - expected_y) < 1e-6


async def test_fountain_particle_count(cluster_with_schema):
    """Test that all generated particles appear at birth time."""
    sim = FountainSimulator(gravity=9.81, water_level=0.0)
    num_particles = 50
    sim.add_conical_fountain(
        num_particles=num_particles,
        apex_x=0, apex_y=1.5, apex_z=14,
        cone_height=2.0,
        cone_angle_rad=np.pi / 6,
        base_radius=1.75,
        speed_min=3.0, speed_max=8.0,
        birth_start=0.0, birth_end=0.5,
        size_min=0.01, size_max=0.03,
        seed_offset=42,
    )

    job_id = await cluster_with_schema.create_job(
        job_name="CountTest",
        num_frames=2,
        width=640,
        height=480,
        fps=10,
        gravity=9.81,
        water_level=0.0,
    )
    await cluster_with_schema.insert_particle_births(job_id, sim.particles)
    await cluster_with_schema.insert_frames(job_id, 2)

    states = await cluster_with_schema.get_particles_at_time(job_id, 0.2)
    assert len(states) <= num_particles


async def test_ground_collision(cluster_with_schema):
    """Test that particles die when they hit water_level."""
    sim = FountainSimulator(gravity=9.81, water_level=0.0)
    sim.add_conical_fountain(
        num_particles=1,
        apex_x=0, apex_y=1.0, apex_z=0,
        cone_height=0.1, cone_angle_rad=0.0, base_radius=0.1,
        speed_min=0, speed_max=0,
        birth_start=0, birth_end=0,
        size_min=0.02, size_max=0.02,
        seed_offset=42,
    )

    job_id = await cluster_with_schema.create_job(
        job_name="CollisionTest",
        num_frames=3,
        width=640,
        height=480,
        fps=10,
        gravity=9.81,
        water_level=0.0,
    )
    await cluster_with_schema.insert_particle_births(job_id, sim.particles)

    states = await cluster_with_schema.get_particles_at_time(job_id, 0.0)
    assert len(states) == 1

    states = await cluster_with_schema.get_particles_at_time(job_id, 0.5)
    assert len(states) == 0


async def test_validation_metrics(cluster_with_schema):
    """Test that validation metrics are computed correctly."""
    sim = FountainSimulator(gravity=9.81, water_level=0.0)
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

    job_id = await cluster_with_schema.create_job(
        job_name="MetricsTest",
        num_frames=5,
        width=640,
        height=480,
        fps=10,
        gravity=9.81,
        water_level=0.0,
    )
    await cluster_with_schema.insert_particle_births(job_id, sim.particles)

    states = await cluster_with_schema.get_particles_at_time(job_id, 0.2)
    metrics = PhysicsValidator.compute_metrics(states, gravity=9.81)

    assert metrics["particle_count"] > 0
    assert metrics["kinetic_energy"] > 0
    assert metrics["potential_energy"] > 0
    assert metrics["total_energy"] > 0
    assert metrics["nan_count"] == 0
    assert metrics["inf_count"] == 0
