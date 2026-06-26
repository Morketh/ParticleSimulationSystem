"""Integration test for particle simulation with real database."""

import pytest
pytestmark = pytest.mark.asyncio  # Apply to all tests in this module

from povray_render.particles import ParticleGenerator


async def test_particle_simulation_and_storage(cluster_with_schema):
    """Generate particles and store them using ClusterManager."""
    job_id = await cluster_with_schema.create_job(
        job_name="IntegrationTest",
        num_frames=2,
        res_x=640,
        res_y=480,
        fps=30,
        quality=5,
        antialias="off",
        antialias_depth=0,
        antialias_threshold=0.0,
        sampling_method=0,
    )
    assert job_id > 0

    await cluster_with_schema.insert_frames(job_id, 2)

    gen = ParticleGenerator()
    gen.generate_conical_fountain(
        num_particles=10,
        apex_position=[0, 1.5, 14],
        cone_height=2.0,
        cone_angle=3.14159 / 6,
        base_radius=1.75,
        wind_direction=[1, 0.5, 0],
        wind_velocity=0.0,
        texture="WaterTexture",
    )

    for frame_num in range(1, 3):
        particle_data = gen.plot_particles_at_frame(frame_num, frame_rate=30)
        await cluster_with_schema.insert_particle_data(job_id, frame_num, particle_data)

    # Verify
    total = await cluster_with_schema.get_total_frames(job_id)
    assert total == 2

    textures = await cluster_with_schema.get_textures()
    water_id = next(t["texture_id"] for t in textures if t["texture_name"] == "WaterTexture")
    particles = await cluster_with_schema.get_particles(job_id, 1, water_id)
    assert len(particles) == 10