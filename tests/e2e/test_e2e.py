# tests/e2e/test_e2e.py
"""Automated E2E test: generator → render → make_mp4."""

import asyncio
import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from generator import main as generator_main
from make_mp4 import main as make_mp4_main
from render import render_loop

pytestmark = pytest.mark.asyncio


async def test_e2e_pipeline(cluster_with_schema, test_db_name, tmp_path):
    """Full pipeline test: generate → render → compile MP4."""
    template = tmp_path / "template.pov"
    template.write_text("//PARTICLE_SYSTEM")

    env_vars = {
        "DB_BACKEND": "mariadb",
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "3306",
        "DB_USER": "pytest_user",
        "DB_PASSWORD": "123qwe",
        "DB_DATABASE": test_db_name,
        "NUM_PARTICLES": "10",
        "NUM_FRAMES": "5",
        "FPS": "5",
        "RENDER_WIDTH": "320",
        "RENDER_HEIGHT": "240",
        "QUALITY": "0",
        "ANTIALIAS": "off",
        "TEMPLATE_FILE": str(template),
        "RUN_VALIDATION": "true",
    }

    with patch.dict("os.environ", env_vars):
        await generator_main()

    rows = await cluster_with_schema.db.fetch_all(
        "SELECT job_id FROM render_jobs ORDER BY created_at DESC LIMIT 1"
    )
    assert rows, "No job created"
    job_id = rows[0]["job_id"]

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
                timeout=1.5
            )

        frames = await cluster_with_schema.db.fetch_all(
            "SELECT status FROM frames WHERE job_id = %s",
            (job_id,)
        )
        assert all(f["status"] == "rendered" for f in frames)
        assert mock_povray.await_count == 5

    # Mark job as completed
    await cluster_with_schema.update_job_status(job_id, "completed")

    # Verify job status was updated
    status_rows = await cluster_with_schema.db.fetch_all(
        "SELECT status FROM render_jobs WHERE job_id = %s",
        (job_id,)
    )
    assert status_rows, "Job not found after status update"
    assert status_rows[0]["status"] == "completed", f"Job status is {status_rows[0]['status']}, expected 'completed'"

    # Run make_mp4 with mocked ffmpeg
    with patch.dict("os.environ", env_vars), \
         patch("make_mp4.run_ffmpeg", new_callable=AsyncMock) as mock_ffmpeg:
        mock_ffmpeg.return_value = 0
        await make_mp4_main()
        mock_ffmpeg.assert_awaited_once()

    output_dir = Path("output") / "Fountain_10p_5f_5fps"
    assert output_dir.exists()
    pov_files = list(output_dir.glob("*.pov"))
    # PNG files are not created by the mock, so we only check POV files.
    # MP4 is also not created because ffmpeg is mocked, so skip checking it.
    assert len(pov_files) == 5
    # Optionally, we could check that the mock was called, which we already do.
