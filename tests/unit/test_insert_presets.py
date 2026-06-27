# tests/unit/test_insert_presets.py

"""Unit tests for insert_preset.py - mocks cluster and tests JSON parsing."""
import io
import json
from unittest.mock import AsyncMock, patch

import pytest

from insert_preset import main


@pytest.mark.asyncio
async def test_insert_preset_from_file(tmp_path):
    """Tests inserting a preset from a JSON file specified as a command-line argument. Mocks environment, database provider, and cluster manager to verify that the preset is correctly parsed from the file and passed to ClusterManager.ensure_preset, and that database initialization and cleanup occur."""
    json_file = tmp_path / 'preset.json'
    json_file.write_text(json.dumps({'texture_name': 'WaterTexture', 'preset_name': 'Default', 'parameters': {'pigment_r': 0.7, 'pigment_g': 0.9, 'pigment_b': 1.0, 'pigment_t': 0.85, 'ambient': 0.1, 'diffuse': 0.9, 'reflection': 0.4, 'specular': 0.9, 'roughness': 0.001}}))
    with patch.dict('os.environ', {'DB_BACKEND': 'sqlite', 'DB_PATH': '/tmp/test.db'}) as _env, patch('insert_preset.create_database_provider') as mock_create, patch('insert_preset.ClusterManager') as mock_cls:
        mock_db = AsyncMock()
        mock_create.return_value = mock_db
        mock_cluster = AsyncMock()
        mock_cluster.ensure_preset = AsyncMock(return_value=99)
        mock_cls.return_value = mock_cluster
        with patch('sys.argv', ['insert_preset.py', str(json_file)]):
            await main()
        mock_cluster.ensure_preset.assert_awaited_once_with('WaterTexture', 'Default', {'pigment_r': 0.7, 'pigment_g': 0.9, 'pigment_b': 1.0, 'pigment_t': 0.85, 'ambient': 0.1, 'diffuse': 0.9, 'reflection': 0.4, 'specular': 0.9, 'roughness': 0.001})
        mock_db.initialize.assert_awaited_once()
        mock_db.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_insert_preset_stdin():
    """Tests inserting a preset from JSON data provided via standard input. Mocks stdin as a StringIO containing valid preset JSON, verifies that main() reads from stdin, calls ensure_preset with the correct texture name and preset name, and handles database lifecycle correctly."""
    json_data = json.dumps({'texture_name': 'Jade', 'preset_name': 'Green', 'parameters': {'pigment_r': 0.0, 'pigment_g': 0.8, 'pigment_b': 0.0, 'pigment_t': 0.0, 'ambient': 0.2, 'diffuse': 0.7, 'reflection': 0.1, 'specular': 0.5, 'roughness': 0.2}})
    with patch.dict('os.environ', {'DB_BACKEND': 'sqlite', 'DB_PATH': '/tmp/test.db'}) as _env, patch('insert_preset.create_database_provider') as mock_create, patch('insert_preset.ClusterManager') as mock_cls:
        mock_db = AsyncMock()
        mock_create.return_value = mock_db
        mock_cluster = AsyncMock()
        mock_cluster.ensure_preset = AsyncMock(return_value=100)
        mock_cls.return_value = mock_cluster
        with patch('sys.stdin', io.StringIO(json_data)), patch('sys.argv', ['insert_preset.py']):
            await main()
        mock_cluster.ensure_preset.assert_awaited_once()
        args = mock_cluster.ensure_preset.call_args[0]
        assert args[0] == 'Jade'
        assert args[1] == 'Green'

@pytest.mark.asyncio
async def test_insert_preset_multiple():
    """Tests inserting multiple presets from a JSON array provided via standard input. Verifies that main() processes each preset in the array, calls ensure_preset once per preset with the correct parameters, and that all calls are made with the expected data."""
    json_data = json.dumps([{'texture_name': 'WaterTexture', 'preset_name': 'Default', 'parameters': {'pigment_r': 0.7, 'pigment_g': 0.9, 'pigment_b': 1.0, 'pigment_t': 0.85, 'ambient': 0.1, 'diffuse': 0.9, 'reflection': 0.4, 'specular': 0.9, 'roughness': 0.001}}, {'texture_name': 'WaterTexture', 'preset_name': 'Blue', 'parameters': {'pigment_r': 0.0, 'pigment_g': 0.2, 'pigment_b': 1.0, 'pigment_t': 0.9, 'ambient': 0.1, 'diffuse': 0.8, 'reflection': 0.5, 'specular': 0.9, 'roughness': 0.0005}}])
    with patch.dict('os.environ', {'DB_BACKEND': 'sqlite', 'DB_PATH': '/tmp/test.db'}) as _env, patch('insert_preset.create_database_provider') as mock_create, patch('insert_preset.ClusterManager') as mock_cls:
        mock_db = AsyncMock()
        mock_create.return_value = mock_db
        mock_cluster = AsyncMock()
        mock_cluster.ensure_preset = AsyncMock(return_value=101)
        mock_cls.return_value = mock_cluster
        with patch('sys.stdin', io.StringIO(json_data)), patch('sys.argv', ['insert_preset.py']):
            await main()
        assert mock_cluster.ensure_preset.call_count == 2
        mock_cluster.ensure_preset.assert_any_call('WaterTexture', 'Default', {'pigment_r': 0.7, 'pigment_g': 0.9, 'pigment_b': 1.0, 'pigment_t': 0.85, 'ambient': 0.1, 'diffuse': 0.9, 'reflection': 0.4, 'specular': 0.9, 'roughness': 0.001})
        mock_cluster.ensure_preset.assert_any_call('WaterTexture', 'Blue', {'pigment_r': 0.0, 'pigment_g': 0.2, 'pigment_b': 1.0, 'pigment_t': 0.9, 'ambient': 0.1, 'diffuse': 0.8, 'reflection': 0.5, 'specular': 0.9, 'roughness': 0.0005})

@pytest.mark.asyncio
async def test_insert_preset_missing_fields():
    """Tests handling of malformed JSON input missing required fields (preset_name). Verifies that main() does not call ensure_preset when required fields are absent, and that the database connection is still properly closed."""
    json_data = json.dumps({'texture_name': 'WaterTexture'})
    with patch.dict('os.environ', {'DB_BACKEND': 'sqlite', 'DB_PATH': '/tmp/test.db'}) as _env, patch('insert_preset.create_database_provider') as mock_create, patch('insert_preset.ClusterManager') as mock_cls:
        mock_db = AsyncMock()
        mock_create.return_value = mock_db
        mock_cluster = AsyncMock()
        mock_cluster.ensure_preset = AsyncMock()
        mock_cls.return_value = mock_cluster
        with patch('sys.stdin', io.StringIO(json_data)), patch('sys.argv', ['insert_preset.py']):
            await main()
        mock_cluster.ensure_preset.assert_not_called()
        mock_db.close.assert_awaited_once()
