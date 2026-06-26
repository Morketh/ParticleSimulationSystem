# tests/unit/test_cluster.py (full corrected file)

import pytest
from unittest.mock import AsyncMock, Mock, patch

from DBCore.ir import IRBulkInsert, IRInsert, IRSelect, IRUpdate
from DBCore.ir.conditions import Condition, LogicalExpression

from povray_render.cluster import ClusterManager


@pytest.fixture
def mock_db():
    """Create a mock DatabaseProvider with all needed async methods."""
    db = Mock()
    db.execute_ir = AsyncMock()
    db.bulk_insert_ir = AsyncMock()
    db.fetch_all_ir = AsyncMock()
    # NEW: mock for raw SELECT queries
    db.fetch_all = AsyncMock(return_value=[{"LAST_INSERT_ID()": 42}])
    db.execute_raw = AsyncMock(return_value=([], "log"))
    return db


@pytest.fixture
def cluster(mock_db):
    return ClusterManager(mock_db)


@pytest.mark.asyncio
async def test_create_job(cluster, mock_db):
    """Test create_job builds correct IRInsert and returns job_id."""
    job_id = await cluster.create_job(
        job_name="test_job",
        num_frames=10,
        res_x=1920,
        res_y=1080,
        fps=24,
        quality=11,
        antialias="on",
        antialias_depth=5,
        antialias_threshold=0.1,
        sampling_method=2,
    )
    assert job_id == 42

    mock_db.execute_ir.assert_awaited_once()
    insert = mock_db.execute_ir.call_args[0][0]
    assert isinstance(insert, IRInsert)
    assert insert.table == "render_jobs"
    assert insert.values["job_name"] == "test_job"


@pytest.mark.asyncio
async def test_insert_frames(cluster, mock_db):
    """Test insert_frames loops and calls execute_ir for each frame."""
    await cluster.insert_frames(job_id=1, num_frames=3)
    assert mock_db.execute_ir.call_count == 3
    for i, call in enumerate(mock_db.execute_ir.call_args_list):
        insert = call[0][0]
        assert insert.table == "frames"
        assert insert.values["frame_id"] == i + 1
        assert insert.values["job_id"] == 1
        assert insert.values["status"] == "pending"


@pytest.mark.asyncio
async def test_get_next_frame(cluster, mock_db):
    """Test get_next_frame builds correct IRSelect."""
    mock_db.fetch_all_ir.return_value = [{"frame_id": 5, "status": "pending"}]
    frame = await cluster.get_next_frame(job_id=1)
    assert frame["frame_id"] == 5

    select = mock_db.fetch_all_ir.call_args[0][0]
    assert isinstance(select, IRSelect)
    assert select.table == "frames"
    assert select.limit == 1

    cond = select.where
    assert isinstance(cond, LogicalExpression)
    assert cond.operator == "AND"
    assert len(cond.conditions) == 2
    cond1, cond2 = cond.conditions
    assert isinstance(cond1, Condition)
    assert cond1.column == "job_id"
    assert cond1.operator == "="
    assert cond1.value == 1
    assert isinstance(cond2, Condition)
    assert cond2.column == "status"
    assert cond2.operator == "="
    assert cond2.value == "pending"


@pytest.mark.asyncio
async def test_update_frame_status(cluster, mock_db):
    """Test update_frame_status builds correct IRUpdate."""
    await cluster.update_frame_status(frame_id=10, status="rendered")
    update = mock_db.execute_ir.call_args[0][0]
    assert isinstance(update, IRUpdate)
    assert update.table == "frames"
    assert update.set_values["status"] == "rendered"
    assert update.where.column == "frame_id"
    assert update.where.value == 10


@pytest.mark.asyncio
async def test_insert_particle_data(cluster, mock_db):
    """Test insert_particle_data maps textures and uses IRBulkInsert."""
    mock_db.fetch_all_ir.return_value = [
        {"texture_id": 1, "texture_name": "WaterTexture"},
        {"texture_id": 2, "texture_name": "Jade"},
    ]
    particles = [
        {
            "particle_id": 1,
            "position": [1.0, 2.0, 3.0],
            "velocity": [0.1, 0.2, 0.3],
            "size": 0.5,
            "texture": "WaterTexture",
        },
        {
            "particle_id": 2,
            "position": [4.0, 5.0, 6.0],
            "velocity": [0.4, 0.5, 0.6],
            "size": 0.7,
            "texture": "Jade",
        },
    ]
    await cluster.insert_particle_data(job_id=1, frame_id=2, particle_data=particles)

    mock_db.bulk_insert_ir.assert_awaited_once()
    bulk = mock_db.bulk_insert_ir.call_args[0][0]
    assert isinstance(bulk, IRBulkInsert)
    assert bulk.table == "particles"
    assert len(bulk.values) == 2
    assert bulk.values[0][10] == 1  # texture_id for WaterTexture
    assert bulk.values[1][10] == 2  # texture_id for Jade


@pytest.mark.asyncio
async def test_node_insert_new(cluster, mock_db):
    """Test insert_node_info when node does not exist (insert)."""
    mock_db.fetch_all_ir.return_value = []  # no existing node
    with patch("povray_render.cluster.ClusterManager.get_node_info") as mock_info:
        mock_info.return_value = ("host1", "192.168.1.1", 8, 16.0)
        await cluster.insert_node_info(status="active", role="render")

    assert mock_db.execute_ir.call_count == 1
    insert = mock_db.execute_ir.call_args[0][0]
    assert isinstance(insert, IRInsert)
    assert insert.table == "nodes"
    assert insert.values["node_name"] == "host1"


@pytest.mark.asyncio
async def test_node_insert_update(cluster, mock_db):
    """Test insert_node_info when node exists (update)."""
    mock_db.fetch_all_ir.return_value = [{"node_id": 1}]  # exists
    with patch("povray_render.cluster.ClusterManager.get_node_info") as mock_info:
        mock_info.return_value = ("host1", "192.168.1.2", 16, 32.0)
        await cluster.insert_node_info(status="inactive", role="monitor")

    update = mock_db.execute_ir.call_args[0][0]
    assert isinstance(update, IRUpdate)
    assert update.table == "nodes"
    assert update.set_values["status"] == "inactive"
    assert update.where.column == "node_name"
    assert update.where.value == "host1"