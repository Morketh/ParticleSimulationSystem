# tests/unit/test_generator.py
"""Unit tests for generator.py - mocks the simulator and cluster."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from generator import main  # import async main


@pytest.mark.asyncio
async def test_generator_main_flow():
    """Test that generator creates simulator, stores births, and updates job."""
    with patch.dict("os.environ", {
        "DB_BACKEND": "sqlite",
        "DB_PATH": "/tmp/test.db",
        "NUM_PARTICLES": "10",
        "NUM_FRAMES": "5",
        "FPS": "30",
        "GRAVITY": "9.81",
        "WATER_LEVEL": "0.0",
        "RUN_VALIDATION": "false",
        "RENDER_WIDTH": "640",
        "RENDER_HEIGHT": "480",
        "QUALITY": "0",
        "ANTIALIAS": "off",
        "TEXTURE": "WaterTexture",
        "PRESET_NAME": "Default",
        "PIGMENT_R": "0.7",
        "PIGMENT_G": "0.9",
        "PIGMENT_B": "1.0",
        "PIGMENT_T": "0.85",
        "AMBIENT": "0.1",
        "DIFFUSE": "0.9",
        "REFLECTION": "0.4",
        "SPECULAR": "0.9",
        "ROUGHNESS": "0.001",
    }), patch("generator.create_database_provider") as mock_create:
        mock_db = AsyncMock()
        mock_create.return_value = mock_db

        with patch("generator.ClusterManager") as mock_cls:
            mock_cluster = AsyncMock()
            mock_cluster.ensure_preset = AsyncMock(return_value=99)
            mock_cluster.create_job = AsyncMock(return_value=42)
            mock_cluster.insert_frames = AsyncMock()
            mock_cluster.insert_particle_births = AsyncMock()
            mock_cluster.update_job_status = AsyncMock()
            mock_cluster.get_particles_at_time = AsyncMock(return_value=[])
            mock_cls.return_value = mock_cluster

            with patch("generator.FountainSimulator") as mock_sim_cls:
                mock_sim = Mock()
                mock_sim.particles = [Mock()]
                mock_sim.add_conical_fountain = Mock()
                mock_sim_cls.return_value = mock_sim

                await main()   # directly call async main

                mock_cluster.ensure_preset.assert_awaited_once_with(
                    "WaterTexture", "Default",
                    {
                        "pigment_r": 0.7, "pigment_g": 0.9, "pigment_b": 1.0, "pigment_t": 0.85,
                        "ambient": 0.1, "diffuse": 0.9, "reflection": 0.4,
                        "specular": 0.9, "roughness": 0.001,
                    }
                )

                mock_cluster.create_job.assert_awaited_once_with(
                    job_name="Fountain_10p_5f_30fps",
                    num_frames=5,
                    width=640,
                    height=480,
                    fps=30,
                    gravity=9.81,
                    water_level=0.0,
                    preset_id=99,
                )

                mock_cluster.insert_frames.assert_awaited_once()
                mock_cluster.insert_particle_births.assert_awaited_once()
                mock_cluster.update_job_status.assert_awaited_with(42, "pending")
                mock_db.initialize.assert_awaited_once()
                mock_db.close.assert_awaited_once()
