# tests/unit/test_make_mp4.py
"""Unit tests for make_mp4.py - mocks cluster and ffmpeg."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from make_mp4 import detect_ffmpeg_path, main, run_ffmpeg


def test_detect_ffmpeg_path():
    """Test detection of ffmpeg path."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout="/usr/bin/ffmpeg\n")
        assert detect_ffmpeg_path() == "/usr/bin/ffmpeg"


@pytest.mark.asyncio
async def test_run_ffmpeg_success():
    """Test successful ffmpeg execution."""
    with patch("subprocess.run") as mock_run, \
         patch("make_mp4.detect_ffmpeg_path") as mock_detect:
        mock_run.return_value = Mock(returncode=0)
        mock_detect.return_value = "/usr/bin/ffmpeg"
        ret = await run_ffmpeg("frame_%04d.png", Path("out.mp4"), 30, 100)
        assert ret == 0
        mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_run_ffmpeg_failure():
    """Test failed ffmpeg execution."""
    with patch("subprocess.run") as mock_run, \
         patch("make_mp4.detect_ffmpeg_path") as mock_detect:
        mock_run.return_value = Mock(returncode=1, stderr="error")
        mock_detect.return_value = "/usr/bin/ffmpeg"
        ret = await run_ffmpeg("frame_%04d.png", Path("out.mp4"), 30, 100)
        assert ret == 1
        mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_main_no_completed_jobs():
    """Test that main exits gracefully when no jobs are found."""
    with patch.dict("os.environ", {
        "DB_BACKEND": "sqlite",
        "DB_PATH": "/tmp/test.db",
    }) as _env, \
         patch("make_mp4.create_database_provider") as mock_create, \
         patch("make_mp4.ClusterManager") as mock_cls:

        mock_db = AsyncMock()
        mock_create.return_value = mock_db

        mock_cluster = AsyncMock()
        mock_cluster.db.fetch_all = AsyncMock(return_value=[])
        mock_cls.return_value = mock_cluster

        await main()

        mock_db.initialize.assert_awaited_once()
        mock_db.close.assert_awaited_once()
        expected_sql = """
        SELECT job_id, job_name, fps, total_frames
        FROM render_jobs
        WHERE status = 'completed'
        ORDER BY created_at DESC
        LIMIT 1
        """
        mock_cluster.db.fetch_all.assert_called_with(expected_sql)


@pytest.mark.asyncio
async def test_main_no_rendered_frames():
    """Test that main exits when job has no rendered frames."""
    with patch.dict("os.environ", {
        "DB_BACKEND": "sqlite",
        "DB_PATH": "/tmp/test.db",
    }) as _env, \
         patch("make_mp4.create_database_provider") as mock_create, \
         patch("make_mp4.ClusterManager") as mock_cls, \
         patch("make_mp4.run_ffmpeg", new_callable=AsyncMock) as mock_run:

        mock_db = AsyncMock()
        mock_create.return_value = mock_db

        mock_cluster = AsyncMock()
        mock_cluster.db.fetch_all = AsyncMock(side_effect=[
            [{"job_id": 1, "job_name": "test_job", "fps": 30, "total_frames": 100}],
            [{"count": 0}],
        ])
        mock_cls.return_value = mock_cluster

        await main()

        mock_db.close.assert_awaited_once()
        mock_run.assert_not_called()
