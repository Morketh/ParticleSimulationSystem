# tests/integration/test_render_pipeline.py
"""Integration tests for the render pipeline (with mocked POV-Ray)."""

import asyncio
import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from render import render_loop
from sim.particles import FountainSimulator

pytestmark = pytest.mark.asyncio


async def test_render_loop_with_real_db(cluster_with_schema, tmp_path):
    """Test render loop with real database, mock POV-Ray."""
    sim = FountainSimulator(gravity=9.81, water_level=0.0)
    sim.add_conical_fountain(
        num_particles=10,
        apex_x=0, apex_y=1.5, apex_z=14,
        cone_height=2.0,
        cone_angle_rad=3.14159 / 6,
        base_radius=1.75,
        speed_min=3.0, speed_max=8.0,
        birth_start=0.0, birth_end=0.5,
        size_min=0.01, size_max=0.03,
        seed_offset=42,
    )

    job_id = await cluster_with_schema.create_job(
        job_name="RenderTest",
        num_frames=3,
        width=320,
        height=240,
        fps=10,
        gravity=9.81,
        water_level=0.0,
    )
    await cluster_with_schema.insert_frames(job_id, 3)
    await cluster_with_schema.insert_particle_births(job_id, sim.particles)

    template = tmp_path / "template.pov"
    template.write_text("//PARTICLE_SYSTEM")

    with patch("render.run_povray", new_callable=AsyncMock) as mock_povray:
        mock_povray.return_value = 0

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(
                render_loop(
                    cluster_with_schema,
                    template,
                    poll_interval=0.01,
                    job_id=job_id,
                ),
                timeout=1.0,
            )

        assert mock_povray.await_count == 3

        frames = await cluster_with_schema.db.fetch_all(
            "SELECT status FROM frames WHERE job_id = %s",
            (job_id,)
        )
        assert all(f["status"] == "rendered" for f in frames)

        output_dir = Path("output") / "RenderTest"
        pov_files = list(output_dir.glob("*.pov"))
        assert len(pov_files) == 3
