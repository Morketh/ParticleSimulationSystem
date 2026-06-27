# tests/unit/test_render.py

"""Unit tests for render.py - mocks cluster, POV-Ray, and Vapory scene builder."""
import asyncio
import contextlib
from unittest.mock import AsyncMock, Mock, patch

import pytest

from render import detect_povray_path, render_loop, run_povray


def test_detect_povray_path_linux():
    """Tests POV-Ray detection on Linux by mocking platform.system to return 'Linux' and subprocess.run to return a stdout containing '/usr/bin/povray'. Asserts the detected path matches the expected value."""
    with patch('platform.system') as mock_system, patch('subprocess.run') as mock_run:
        mock_system.return_value = 'Linux'
        mock_run.return_value = Mock(stdout='/usr/bin/povray\n')
        assert detect_povray_path() == '/usr/bin/povray'

def test_detect_povray_path_windows():
    """Tests POV-Ray detection on Windows by mocking platform.system to return 'Windows'. Asserts the detected path matches the default Windows installation path for POV-Ray."""
    with patch('platform.system') as mock_system:
        mock_system.return_value = 'Windows'
        expected = 'C:\\Program Files\\POV-Ray\\v3.7\\bin\\pvengine64.exe'
        assert detect_povray_path() == expected

@pytest.mark.asyncio
async def test_run_povray_success(tmp_path):
    """Tests successful execution of run_povray by mocking POV-Ray detection and subprocess.run to return a successful returncode (0). Creates temporary input and output files, calls the async function with sample parameters, and asserts the return value is 0 and subprocess.run was called once."""
    input_file = tmp_path / 'in.pov'
    input_file.touch()
    output_file = tmp_path / 'out.png'
    with patch('render.detect_povray_path') as mock_detect, patch('platform.system') as mock_system, patch('subprocess.run') as mock_run:
        mock_detect.return_value = '/usr/bin/povray'
        mock_system.return_value = 'Linux'
        mock_run.return_value = Mock(returncode=0)
        ret = await run_povray(input_file, output_file, 640, 480, 5, True, 3)
        assert ret == 0
        mock_run.assert_called_once()

@pytest.mark.asyncio
async def test_run_povray_failure(tmp_path):
    """Tests failure execution of run_povray by mocking POV-Ray detection and subprocess.run to return a failure returncode (1) with stderr output. Creates temporary input and output files, calls the async function with sample parameters, and asserts the return value is 1 and subprocess.run was called once."""
    input_file = tmp_path / 'in.pov'
    input_file.touch()
    output_file = tmp_path / 'out.png'
    with patch('render.detect_povray_path') as mock_detect, patch('platform.system') as mock_system, patch('subprocess.run') as mock_run:
        mock_detect.return_value = '/usr/bin/povray'
        mock_system.return_value = 'Linux'
        mock_run.return_value = Mock(returncode=1, stderr='error')
        ret = await run_povray(input_file, output_file, 640, 480, 5, False, 0)
        assert ret == 1
        mock_run.assert_called_once()

@pytest.mark.asyncio
async def test_render_loop_single_frame(tmp_path):
    """Test that render_loop processes one frame and updates status."""
    mock_cluster = AsyncMock()
    mock_cluster.db.fetch_all = AsyncMock(side_effect=[[{'frame_id': 1, 'job_id': 10}], [{'fps': 30, 'width': 1920, 'height': 1080, 'quality': 11, 'antialias': 'on', 'antialias_depth': 5}], [{'job_name': 'test_job'}]])
    mock_cluster.get_particles_at_time = AsyncMock(return_value=[{'position_x': 0, 'position_y': 1, 'position_z': 2, 'size': 0.02}])
    mock_cluster.get_preset_for_job = AsyncMock(return_value={'pigment_r': 0.7, 'pigment_g': 0.9, 'pigment_b': 1.0, 'pigment_t': 0.85, 'ambient': 0.1, 'diffuse': 0.9, 'reflection': 0.4, 'specular': 0.9, 'roughness': 0.001})
    mock_cluster.update_frame_status = AsyncMock()
    mock_cluster.insert_node_info = AsyncMock()
    template = tmp_path / 'template.pov'
    template.write_text('//PARTICLE_SYSTEM')
    with patch('render.build_scene') as mock_build_scene, patch('render.write_pov_file') as mock_write_pov, patch('render.run_povray', new_callable=AsyncMock) as mock_run_povray:
        mock_scene = Mock()
        mock_build_scene.return_value = mock_scene
        mock_write_pov.return_value = str(tmp_path / 'out.pov')
        mock_run_povray.return_value = 0
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(render_loop(mock_cluster, template, poll_interval=0.01), timeout=0.5)
        mock_cluster.update_frame_status.assert_any_call(1, 'in progress')
        mock_cluster.update_frame_status.assert_any_call(1, 'rendered')
        mock_run_povray.assert_awaited_once()
        mock_write_pov.assert_called_once()

@pytest.mark.asyncio
async def test_render_loop_no_frames(tmp_path):
    """Test that loop sleeps when no frames are pending."""
    mock_cluster = AsyncMock()
    mock_cluster.db.fetch_all = AsyncMock(return_value=[])
    mock_cluster.update_frame_status = AsyncMock()
    template = tmp_path / 'template.pov'
    template.write_text('//PARTICLE_SYSTEM')
    with patch('render.run_povray', new_callable=AsyncMock) as mock_run:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(render_loop(mock_cluster, template, poll_interval=0.01), timeout=0.2)
        mock_run.assert_not_called()
        mock_cluster.update_frame_status.assert_not_called()

@pytest.mark.asyncio
async def test_render_loop_job_missing(tmp_path):
    """Test that missing job config marks frame as error."""
    mock_cluster = AsyncMock()
    mock_cluster.db.fetch_all = AsyncMock(side_effect=[[{'frame_id': 1, 'job_id': 10}], []])
    mock_cluster.update_frame_status = AsyncMock()
    template = tmp_path / 'template.pov'
    template.write_text('//PARTICLE_SYSTEM')
    with patch('render.run_povray', new_callable=AsyncMock) as mock_run:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(render_loop(mock_cluster, template, poll_interval=0.01), timeout=0.2)
        mock_cluster.update_frame_status.assert_any_call(1, 'error')
        mock_run.assert_not_called()

@pytest.mark.asyncio
async def test_render_loop_with_job_filter(tmp_path):
    """Test that render_loop filters by job_id when provided."""
    mock_cluster = AsyncMock()
    mock_cluster.db.fetch_all = AsyncMock(side_effect=[[{'frame_id': 1, 'job_id': 10}], [{'fps': 30, 'width': 1920, 'height': 1080, 'quality': 11, 'antialias': 'on', 'antialias_depth': 5}], [{'job_name': 'test_job'}]])
    mock_cluster.get_particles_at_time = AsyncMock(return_value=[])
    mock_cluster.get_preset_for_job = AsyncMock(return_value=None)
    mock_cluster.update_frame_status = AsyncMock()
    template = tmp_path / 'template.pov'
    template.write_text('//PARTICLE_SYSTEM')
    with patch('render.build_scene') as mock_build_scene, patch('render.write_pov_file') as mock_write_pov, patch('render.run_povray', new_callable=AsyncMock) as mock_run:
        mock_scene = Mock()
        mock_build_scene.return_value = mock_scene
        mock_write_pov.return_value = str(tmp_path / 'out.pov')
        mock_run.return_value = 0
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(render_loop(mock_cluster, template, poll_interval=0.01, job_id=10), timeout=0.5)
        assert mock_cluster.db.fetch_all.call_count >= 1
        mock_run.assert_awaited_once()
