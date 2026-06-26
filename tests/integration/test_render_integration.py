# tests/integration/test_render_integration.py
"""Integration test for Render.py with real database and mocked POV‑Ray."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from povray_render.Render import render_loop


pytestmark = pytest.mark.asyncio


async def test_render_loop_integration(cluster_with_schema, tmp_path):
    """
    Integration test: create a job, insert frames and particles,
    then run render_loop and verify status updates.
    """
    cluster = cluster_with_schema

    # 1. Create a job with 2 frames
    job_id = await cluster.create_job(
        job_name="IntegTestRender",
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
    await cluster.insert_frames(job_id, 2)

    # 2. Insert some particles for frame 1
    await cluster.db.execute_raw(
        "INSERT IGNORE INTO textures (texture_name) VALUES ('WaterTexture')",
        unsafe=True,
    )
    textures = await cluster.get_textures()
    water_id = next(t["texture_id"] for t in textures if t["texture_name"] == "WaterTexture")

    for i in range(5):
        await cluster.db.execute_raw(
            """
            INSERT INTO particles
            (particle_id, frame_id, job_id, position_x, position_y, position_z,
             velocity_x, velocity_y, velocity_z, size, texture_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (i + 1, 1, job_id, i * 0.5, 1.0, 0.0, 0.0, -0.5, 0.0, 0.1, water_id),
            unsafe=True,
        )

    # 3. Create a template POV file
    template = tmp_path / "template.pov"
    template.write_text("//PARTICLE_SYSTEM")

    # 4. Mock run_povray to return success
    with patch("povray_render.Render.run_povray", new_callable=AsyncMock) as mock_run_povray:
        mock_run_povray.return_value = 0

        # 5. Run the render loop with a short timeout to process one frame
        try:
            await asyncio.wait_for(
                render_loop(cluster, template, poll_interval=0.01),
                timeout=0.5
            )
        except asyncio.TimeoutError:
            pass

        # 6. Verify that run_povray was called twice (for frame 1 and frame 2)
        assert mock_run_povray.await_count == 2

        # 7. Check frame status updates – both frames should be 'rendered'
        frames = await cluster.fetch_frame_by_job(job_id)
        frame_status = {f["frame_id"]: f["status"] for f in frames}
        assert frame_status[1] == "rendered"
        assert frame_status[2] == "rendered"