# tests/unit/storage/test_cluster.py
"""Unit tests for ClusterManager - mocks the DatabaseProvider."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from DBCore.ir import IRSelect, IRUpdate
from DBCore.ir.conditions import LogicalExpression

from sim.particles import ParticleBirth
from storage.cluster import ClusterManager


@pytest.fixture
def mock_db():
    """Create a mock DatabaseProvider with all needed async methods."""
    db = Mock()
    db.execute_ir = AsyncMock()
    db.bulk_insert_ir = AsyncMock()
    db.fetch_all_ir = AsyncMock()
    db.fetch_all = AsyncMock()
    db.execute_raw = AsyncMock(return_value=([], "log"))
    return db


@pytest.fixture
def cluster(mock_db):
    """ClusterManager with mocked DB."""
    return ClusterManager(mock_db)


# ----------------------------------------------------------------------------
# Texture and Preset Tests
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_texture_new(cluster, mock_db):
    """Test creating a new texture."""
    mock_db.fetch_all.side_effect = [
        [],                         # select for existence
        [{"LAST_INSERT_ID()": 42}]  # after insert
    ]
    mock_db.execute_raw.return_value = None

    tex_id = await cluster.ensure_texture("WaterTexture", "Water description")
    assert tex_id == 42
    mock_db.execute_raw.assert_awaited_once_with(
        "INSERT INTO textures (texture_name, texture_description) VALUES (%s, %s)",
        ("WaterTexture", "Water description"),
        unsafe=True,
    )


@pytest.mark.asyncio
async def test_ensure_texture_existing(cluster, mock_db):
    """Test retrieving existing texture."""
    mock_db.fetch_all.return_value = [{"texture_id": 5}]

    tex_id = await cluster.ensure_texture("WaterTexture")
    assert tex_id == 5
    mock_db.execute_raw.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_preset_new(cluster, mock_db):
    """Test creating a new preset."""
    with patch.object(cluster, "ensure_texture", new_callable=AsyncMock) as mock_ensure:
        mock_ensure.return_value = 7
        mock_db.fetch_all.side_effect = [
            [],  # no preset found
            [{"LAST_INSERT_ID()": 99}]  # after insert
        ]
        mock_db.execute_raw.return_value = None

        params = {
            "pigment_r": 0.7, "pigment_g": 0.9, "pigment_b": 1.0, "pigment_t": 0.85,
            "ambient": 0.1, "diffuse": 0.9, "reflection": 0.4,
            "specular": 0.9, "roughness": 0.001,
        }
        preset_id = await cluster.ensure_preset("WaterTexture", "Default", params)
        assert preset_id == 99

        mock_db.execute_raw.assert_awaited_once()
        sql, args = mock_db.execute_raw.call_args[0]
        assert "INSERT INTO texture_presets" in sql
        assert args[0] == 7      # texture_id
        assert args[1] == "Default"
        assert args[2] == 0.7    # pigment_r
        assert args[3] == 0.9    # pigment_g
        assert args[4] == 1.0    # pigment_b
        assert args[5] == 0.85   # pigment_t
        assert args[6] == 0.1    # ambient
        assert args[7] == 0.9    # diffuse
        assert args[8] == 0.4    # reflection
        assert args[9] == 0.9    # specular
        assert args[10] == 0.001 # roughness


@pytest.mark.asyncio
async def test_ensure_preset_existing(cluster, mock_db):
    """Test retrieving existing preset."""
    with patch.object(cluster, "ensure_texture", new_callable=AsyncMock) as mock_ensure:
        mock_ensure.return_value = 7
        mock_db.fetch_all.return_value = [{"preset_id": 55}]

        preset_id = await cluster.ensure_preset("WaterTexture", "Default", {})
        assert preset_id == 55
        mock_db.execute_raw.assert_not_called()


@pytest.mark.asyncio
async def test_get_preset_for_job(cluster, mock_db):
    """Test fetching preset for a job."""
    mock_db.fetch_all.return_value = [{
        "preset_id": 1, "texture_id": 2, "name": "Default",
        "pigment_r": 0.7, "pigment_g": 0.9, "pigment_b": 1.0, "pigment_t": 0.85,
        "ambient": 0.1, "diffuse": 0.9, "reflection": 0.4,
        "specular": 0.9, "roughness": 0.001,
    }]

    preset = await cluster.get_preset_for_job(1)
    assert preset["preset_id"] == 1
    assert preset["pigment_r"] == 0.7

    mock_db.fetch_all.return_value = []
    preset = await cluster.get_preset_for_job(1)
    assert preset is None


# ----------------------------------------------------------------------------
# Job Tests
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_job_with_preset(cluster, mock_db):
    """Test creating a job with preset_id."""
    mock_db.fetch_all.return_value = [{"LAST_INSERT_ID()": 42}]

    job_id = await cluster.create_job(
        job_name="test_job",
        num_frames=10,
        width=1920,
        height=1080,
        fps=30,
        gravity=9.81,
        water_level=0.0,
        preset_id=5,
    )
    assert job_id == 42

    insert = mock_db.execute_ir.call_args[0][0]
    assert insert.table == "render_jobs"
    assert insert.values["preset_id"] == 5


@pytest.mark.asyncio
async def test_create_job_without_preset(cluster, mock_db):
    """Test creating a job without preset_id."""
    mock_db.fetch_all.return_value = [{"LAST_INSERT_ID()": 43}]

    job_id = await cluster.create_job(
        job_name="test_job",
        num_frames=10,
        width=1920,
        height=1080,
        fps=30,
    )
    assert job_id == 43

    insert = mock_db.execute_ir.call_args[0][0]
    assert insert.values["preset_id"] is None


@pytest.mark.asyncio
async def test_get_job_config(cluster, mock_db):
    """Test retrieving job configuration."""
    mock_db.fetch_all.return_value = [{"gravity": 9.81, "water_level": 0.5}]
    config = await cluster.get_job_config(1)
    assert config["gravity"] == 9.81
    assert config["water_level"] == 0.5


@pytest.mark.asyncio
async def test_get_job_config_not_found(cluster, mock_db):
    """Test error when job doesn't exist."""
    mock_db.fetch_all.return_value = []
    with pytest.raises(ValueError, match="Job 99 not found"):
        await cluster.get_job_config(99)


@pytest.mark.asyncio
async def test_update_job_status(cluster, mock_db):
    """Test updating job status."""
    await cluster.update_job_status(1, "completed")
    update = mock_db.execute_ir.call_args[0][0]
    assert isinstance(update, IRUpdate)
    assert update.table == "render_jobs"
    assert update.set_values["status"] == "completed"
    assert update.where.column == "job_id"
    assert update.where.value == 1


# ----------------------------------------------------------------------------
# Particle Births Tests
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_particle_births_ensures_textures(cluster, mock_db):
    """Test that insert_particle_births calls ensure_texture for each texture."""
    births = [
        ParticleBirth(
            particle_id=0,
            birth_time=0.0,
            x0=0, y0=10, z0=0,
            vx0=0, vy0=0, vz0=0,
            size=0.02,
            texture="WaterTexture",
            seed=42,
            impact_time=1.428,
        ),
        ParticleBirth(
            particle_id=1,
            birth_time=0.0,
            x0=1, y0=9, z0=0,
            vx0=0, vy0=0, vz0=0,
            size=0.02,
            texture="Jade",
            seed=43,
            impact_time=1.354,
        ),
    ]
    with patch.object(cluster, "ensure_texture", new_callable=AsyncMock) as mock_ensure:
        mock_ensure.return_value = 1
        with patch.object(cluster, "_get_texture_id_map", new_callable=AsyncMock) as mock_map:
            mock_map.return_value = {"WaterTexture": 1, "Jade": 2}

            await cluster.insert_particle_births(1, births)

            assert mock_ensure.call_count == 2
            mock_ensure.assert_any_call("WaterTexture")
            mock_ensure.assert_any_call("Jade")

            mock_db.bulk_insert_ir.assert_awaited_once()
            bulk = mock_db.bulk_insert_ir.call_args[0][0]
            assert bulk.table == "particle_births"
            assert len(bulk.values) == 2
            assert bulk.values[0][10] == 1  # texture_id index
            assert bulk.values[1][10] == 2


@pytest.mark.asyncio
async def test_insert_particle_births_empty(cluster, mock_db):
    """Test empty births list does nothing."""
    await cluster.insert_particle_births(1, [])
    mock_db.bulk_insert_ir.assert_not_called()


# ----------------------------------------------------------------------------
# Time-Based Queries
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_particles_at_time(cluster, mock_db):
    """Test reconstructing particle states from birth records."""
    mock_db.fetch_all.side_effect = [
        [{"gravity": 9.81, "water_level": 0.0}],
        [
            {
                "particle_id": 0,
                "birth_time": 0.0,
                "x0": 0.0, "y0": 10.0, "z0": 0.0,
                "vx0": 0.0, "vy0": 0.0, "vz0": 0.0,
                "size": 0.02,
                "texture_name": "WaterTexture",
                "impact_time": 1.428,
            },
            {
                "particle_id": 1,
                "birth_time": 0.0,
                "x0": 2.0, "y0": 10.0, "z0": 0.0,
                "vx0": 0.0, "vy0": 1.0, "vz0": 0.0,
                "size": 0.025,
                "texture_name": "Jade",
                "impact_time": None,
            },
        ],
    ]

    t = 0.5
    states = await cluster.get_particles_at_time(1, t)
    assert len(states) == 2

    p0 = states[0]
    assert p0["particle_id"] == 0
    expected_y = 10.0 - 0.5 * 9.81 * (0.5**2)
    assert abs(p0["position_y"] - expected_y) < 1e-6

    p1 = states[1]
    expected_y = 10.0 + 1.0 * 0.5 - 0.5 * 9.81 * (0.5**2)
    assert abs(p1["position_y"] - expected_y) < 1e-6


@pytest.mark.asyncio
async def test_get_particles_at_time_dead_particle(cluster, mock_db):
    """Test that dead particles (impact_time passed) are filtered out."""
    mock_db.fetch_all.side_effect = [
        [{"gravity": 9.81, "water_level": 0.0}],
        [
            {
                "particle_id": 0,
                "birth_time": 0.0,
                "x0": 0.0, "y0": 10.0, "z0": 0.0,
                "vx0": 0.0, "vy0": 0.0, "vz0": 0.0,
                "size": 0.02,
                "texture_name": "WaterTexture",
                "impact_time": 1.428,
            },
        ],
    ]

    states = await cluster.get_particles_at_time(1, 2.0)
    assert len(states) == 0


@pytest.mark.asyncio
async def test_get_particles_at_time_not_born(cluster, mock_db):
    """Test that particles not yet born are filtered out."""
    mock_db.fetch_all.side_effect = [
        [{"gravity": 9.81, "water_level": 0.0}],
        [
            {
                "particle_id": 0,
                "birth_time": 2.0,
                "x0": 0.0, "y0": 10.0, "z0": 0.0,
                "vx0": 0.0, "vy0": 0.0, "vz0": 0.0,
                "size": 0.02,
                "texture_name": "WaterTexture",
                "impact_time": None,
            },
        ],
    ]

    states = await cluster.get_particles_at_time(1, 0.5)
    assert len(states) == 0


# ----------------------------------------------------------------------------
# Frame Cache Tests
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_frame_particles(cluster, mock_db):
    """Test caching frame particle data."""
    particles = [{"particle_id": 1, "position_x": 0.0, "position_y": 5.0, "position_z": 0.0}]
    await cluster.cache_frame_particles(1, 10, particles)
    mock_db.execute_raw.assert_awaited_once()
    args = mock_db.execute_raw.call_args[0][1]
    assert args[0] == 1
    assert args[1] == 10
    assert json.loads(args[2]) == particles


@pytest.mark.asyncio
async def test_get_cached_frame(cluster, mock_db):
    """Test retrieving cached frame data."""
    particles = [{"particle_id": 1, "position_x": 0.0, "position_y": 5.0, "position_z": 0.0}]
    mock_db.fetch_all.return_value = [{"particle_data": json.dumps(particles)}]
    cached = await cluster.get_cached_frame(1, 10)
    assert cached == particles

    mock_db.fetch_all.return_value = []
    cached = await cluster.get_cached_frame(1, 99)
    assert cached is None


# ----------------------------------------------------------------------------
# Frame Management Tests
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_frames(cluster, mock_db):
    """Test inserting frames."""
    await cluster.insert_frames(1, 3)
    assert mock_db.execute_ir.call_count == 3
    for i, call in enumerate(mock_db.execute_ir.call_args_list):
        insert = call[0][0]
        assert insert.table == "frames"
        assert insert.values["frame_id"] == i + 1
        assert insert.values["job_id"] == 1
        assert insert.values["status"] == "pending"


@pytest.mark.asyncio
async def test_get_next_pending_frame(cluster, mock_db):
    """Test fetching the next pending frame."""
    mock_db.fetch_all_ir.return_value = [{"frame_id": 5, "status": "pending"}]
    frame = await cluster.get_next_pending_frame(1)
    assert frame["frame_id"] == 5

    select = mock_db.fetch_all_ir.call_args[0][0]
    assert isinstance(select, IRSelect)
    assert select.table == "frames"
    assert select.limit == 1
    assert isinstance(select.where, LogicalExpression)


@pytest.mark.asyncio
async def test_get_next_pending_frame_none(cluster, mock_db):
    """Test when no pending frame exists."""
    mock_db.fetch_all_ir.return_value = []
    frame = await cluster.get_next_pending_frame(1)
    assert frame is None


@pytest.mark.asyncio
async def test_update_frame_status(cluster, mock_db):
    """Test updating frame status."""
    await cluster.update_frame_status(10, "rendered")
    update = mock_db.execute_ir.call_args[0][0]
    assert isinstance(update, IRUpdate)
    assert update.table == "frames"
    assert update.set_values["status"] == "rendered"
    assert update.where.column == "frame_id"
    assert update.where.value == 10


@pytest.mark.asyncio
async def test_get_total_frames(cluster, mock_db):
    """Test getting total frame count."""
    mock_db.fetch_all.return_value = [{"total": 5}]
    total = await cluster.get_total_frames(1)
    assert total == 5

    mock_db.fetch_all.return_value = []
    total = await cluster.get_total_frames(2)
    assert total == 0


# ----------------------------------------------------------------------------
# Helper Tests
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_last_insert_id_success(cluster, mock_db):
    """Test retrieving last insert ID."""
    mock_db.fetch_all.return_value = [{"LAST_INSERT_ID()": 123}]
    result = await cluster._last_insert_id()
    assert result == 123


@pytest.mark.asyncio
async def test_last_insert_id_failure(cluster, mock_db):
    """Test error when last insert ID is not available."""
    mock_db.fetch_all.return_value = []
    with pytest.raises(RuntimeError, match="Could not retrieve last insert ID"):
        await cluster._last_insert_id()
