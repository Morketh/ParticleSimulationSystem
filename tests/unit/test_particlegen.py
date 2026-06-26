"""Unit tests for ParticleGen main entry point logic."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

# Use absolute import from the installed package
from povray_render.ParticleGen import main


@pytest.mark.asyncio
async def test_main_flow():
    """Test that main calls ClusterManager methods correctly."""
    with patch.dict("os.environ", {
        "DB_BACKEND": "sqlite",
        "DB_PATH": "/tmp/test.db",
        "RES_X": "640",
        "RES_Y": "480",
        "ANTIALIAS": "on",
        "QUALITY": "5",
        "FPS": "30",
        "NUM_FRAMES": "2",
        "NUM_PARTICLES": "10",
    }):
        with patch("povray_render.ParticleGen.create_database_provider") as mock_create:
            mock_db = AsyncMock()
            mock_create.return_value = mock_db

            with patch("povray_render.ParticleGen.ClusterManager") as mock_cls:
                mock_manager = AsyncMock()
                mock_cls.return_value = mock_manager

                with patch("povray_render.ParticleGen.ParticleGenerator") as mock_gen_cls:
                    mock_gen = Mock()
                    mock_gen.generate_conical_fountain = Mock()
                    mock_gen.plot_particles_at_frame = Mock(return_value=[{"particle_id": 1}])
                    mock_gen_cls.return_value = mock_gen

                    await main()

                    mock_manager.insert_node_info.assert_awaited_once()
                    mock_manager.create_job.assert_awaited_once()
                    mock_manager.insert_frames.assert_awaited_once()
                    mock_manager.insert_particle_data.assert_awaited()

                    mock_gen.generate_conical_fountain.assert_called_once()
                    assert mock_gen.plot_particles_at_frame.call_count == 2


@pytest.mark.asyncio
async def test_main_uses_correct_parameters():
    """Test that main builds the correct job_name and passes parameters."""
    with patch.dict("os.environ", {
        "DB_BACKEND": "mariadb",
        "DB_HOST": "testhost",
        "DB_PORT": "3307",
        "DB_USER": "testuser",
        "DB_PASSWORD": "testpass",
        "DB_DATABASE": "testdb",
        "RES_X": "1024",
        "RES_Y": "768",
        "FPS": "60",
        "NUM_FRAMES": "5",
    }):
        with patch("povray_render.ParticleGen.create_database_provider") as mock_create:
            mock_db = AsyncMock()
            mock_create.return_value = mock_db
            with patch("povray_render.ParticleGen.ClusterManager") as mock_cls:
                mock_manager = AsyncMock()
                mock_cls.return_value = mock_manager
                with patch("povray_render.ParticleGen.ParticleGenerator") as mock_gen_cls:
                    mock_gen = Mock()
                    mock_gen.generate_conical_fountain = Mock()
                    mock_gen.plot_particles_at_frame = Mock(return_value=[])
                    mock_gen_cls.return_value = mock_gen

                    await main()

                    config = mock_create.call_args[0][0]
                    assert config.provider_type == "mariadb"
                    assert config.db_host == "testhost"
                    assert config.db_port == 3307
                    assert config.db_user == "testuser"
                    assert config.db_password == "testpass"
                    assert config.db_database == "testdb"

                    # Check job_name and parameters
                    job_call = mock_manager.create_job.call_args
                    kwargs = job_call[1]  # all arguments are keyword arguments
                    assert "1024x768" in kwargs["job_name"]
                    assert kwargs["res_x"] == 1024
                    assert kwargs["res_y"] == 768
                    assert kwargs["fps"] == 60
                    assert kwargs["num_frames"] == 5