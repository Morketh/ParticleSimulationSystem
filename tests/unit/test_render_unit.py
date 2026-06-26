# tests/unit/test_render_unit.py
"""Unit tests for Render.py – mock all dependencies."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from povray_render.Render import (
    build_output_file,
    create_output_directory,
    detect_povray_path,
    format_particle_objects,
    remove_extension,
    render_loop,
    run_povray,
)


# ----------------------------------------------------------------------------
# Unit test for helper functions
# ----------------------------------------------------------------------------

def test_format_particle_objects():
    """Test formatting particle dicts into POV-Ray sphere declarations."""
    particles = [
        {"position_x": 1.0, "position_y": 2.0, "position_z": 3.0, "size": 0.5},
        {"position_x": 4.0, "position_y": 5.0, "position_z": 6.0, "size": 0.7},
    ]
    result = format_particle_objects(particles)
    expected = "sphere { <1.0, 2.0, 3.0>, 0.5, 1.5 }\nsphere { <4.0, 5.0, 6.0>, 0.7, 1.5 }"
    assert result == expected


def test_remove_extension():
    """Test removing file extension."""
    assert remove_extension(Path("foo.pov")) == "foo"
    assert remove_extension(Path("foo.bar.pov")) == "foo.bar"


def test_create_output_directory(tmp_path):
    """Test creation of output directory."""
    new_dir = tmp_path / "output"
    create_output_directory(new_dir)
    assert new_dir.exists()


def test_build_output_file(tmp_path):
    """Test building a POV file from template."""
    template = tmp_path / "template.pov"
    template.write_text("Hello //PARTICLE_SYSTEM World")
    output = tmp_path / "out.pov"
    build_output_file(template, output, "sphere { <0,0,0>, 1 }")
    content = output.read_text()
    assert content == "Hello sphere { <0,0,0>, 1 } World"


@patch("platform.system")
@patch("subprocess.run")
def test_detect_povray_path(mock_run, mock_system):
    """Test detecting POV-Ray path on different OS."""
    # Linux
    mock_system.return_value = "Linux"
    mock_run.return_value = Mock(stdout="/usr/bin/povray\n")
    assert detect_povray_path() == "/usr/bin/povray"
    mock_run.assert_called_with(["which", "povray"], capture_output=True, text=True, check=True)

    # Windows
    mock_system.return_value = "Windows"
    expected = r"C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe"
    assert detect_povray_path() == expected

    # macOS
    mock_system.return_value = "Darwin"
    expected = "/Applications/POV-Ray 3.7/POV-Ray.app/Contents/MacOS/POV-Ray"
    assert detect_povray_path() == expected


@pytest.mark.asyncio
async def test_run_povray_success(tmp_path):
    """Test run_povray success path with subprocess.run mocked."""
    input_file = tmp_path / "in.pov"
    input_file.touch()
    output_file = tmp_path / "out.png"

    # Mock detect_povray_path to return a fixed path (so it doesn't call subprocess.run)
    with patch("povray_render.Render.detect_povray_path") as mock_detect:
        mock_detect.return_value = "/usr/bin/povray"
        with patch("platform.system") as mock_system, patch("subprocess.run") as mock_run:
            mock_system.return_value = "Linux"
            mock_run.return_value = Mock(returncode=0, stderr="")

            ret = await run_povray(input_file, output_file, width=640, height=480, quality=5, antialias=True, antialias_depth=3)
            assert ret == 0

            # subprocess.run is called only once (for the render command)
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "+I" + str(input_file) in cmd
            assert "+O" + str(output_file) in cmd
            assert "+W640" in cmd
            assert "+H480" in cmd
            assert "+Q5" in cmd
            assert "+A" in cmd
            assert "+R3" in cmd


@pytest.mark.asyncio
async def test_run_povray_failure(tmp_path):
    """Test run_povray failure path."""
    input_file = tmp_path / "in.pov"
    input_file.touch()
    output_file = tmp_path / "out.png"

    with patch("povray_render.Render.detect_povray_path") as mock_detect:
        mock_detect.return_value = "/usr/bin/povray"
        with patch("platform.system") as mock_system, patch("subprocess.run") as mock_run:
            mock_system.return_value = "Linux"
            mock_run.return_value = Mock(returncode=1, stderr="error")
            ret = await run_povray(input_file, output_file, width=640, height=480, quality=5, antialias=False, antialias_depth=0)
            assert ret == 1
            mock_run.assert_called_once()


# ----------------------------------------------------------------------------
# Unit tests for render_loop (with mocks)
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_render_loop_one_frame(tmp_path):
    """Test render_loop processes one frame and updates status."""
    mock_cluster = AsyncMock()
    frame_calls = [{"frame_id": 1, "job_id": 10}]
    mock_cluster.db.fetch_all = AsyncMock(side_effect=[
        frame_calls,
        [{"width": 1920, "height": 1080, "quality": 11, "antialias": "on", "antialias_depth": 5}],
        [{"job_name": "test_job"}],
        []
    ])
    mock_cluster.get_textures.return_value = [{"texture_id": 1}]
    mock_cluster.get_particles.return_value = [{"position_x": 0, "position_y": 1, "position_z": 2, "size": 0.5}]
    mock_cluster.update_frame_status = AsyncMock()

    template = tmp_path / "template.pov"
    template.write_text("//PARTICLE_SYSTEM")

    with patch("povray_render.Render.run_povray", new_callable=AsyncMock) as mock_run_povray:
        mock_run_povray.return_value = 0
        try:
            await asyncio.wait_for(
                render_loop(mock_cluster, template, poll_interval=0.01),
                timeout=0.5
            )
        except asyncio.TimeoutError:
            pass

        mock_cluster.db.fetch_all.assert_any_call(
            "SELECT frame_id, job_id FROM frames WHERE status = 'pending' LIMIT 1"
        )
        mock_cluster.update_frame_status.assert_any_call(1, "in progress")
        mock_cluster.update_frame_status.assert_any_call(1, "rendered")
        mock_run_povray.assert_awaited_once()


@pytest.mark.asyncio
async def test_render_loop_no_frames(tmp_path):
    """Test render_loop when no pending frames exist."""
    mock_cluster = AsyncMock()
    mock_cluster.db.fetch_all = AsyncMock(return_value=[])
    mock_cluster.update_frame_status = AsyncMock()

    template = tmp_path / "template.pov"
    template.write_text("//PARTICLE_SYSTEM")

    with patch("povray_render.Render.run_povray", new_callable=AsyncMock) as mock_run_povray:
        try:
            await asyncio.wait_for(
                render_loop(mock_cluster, template, poll_interval=0.01),
                timeout=0.2
            )
        except asyncio.TimeoutError:
            pass

        mock_cluster.db.fetch_all.assert_called()
        mock_run_povray.assert_not_called()


@pytest.mark.asyncio
async def test_render_loop_job_not_found(tmp_path):
    """Test render_loop when job details missing."""
    mock_cluster = AsyncMock()
    mock_cluster.db.fetch_all = AsyncMock(side_effect=[
        [{"frame_id": 1, "job_id": 10}],
        [],
    ])
    mock_cluster.update_frame_status = AsyncMock()
    template = tmp_path / "template.pov"
    template.write_text("//PARTICLE_SYSTEM")

    with patch("povray_render.Render.run_povray", new_callable=AsyncMock) as mock_run_povray:
        try:
            await asyncio.wait_for(
                render_loop(mock_cluster, template, poll_interval=0.01),
                timeout=0.2
            )
        except asyncio.TimeoutError:
            pass

        mock_cluster.update_frame_status.assert_any_call(1, "error")
        mock_run_povray.assert_not_called()