# tests/conftest.py
"""Pytest configuration and fixtures for the Particle Simulation System tests."""

import asyncio
import logging
import os
import sys
import uuid

import asyncmy
import pytest
import pytest_asyncio
from DBCore import create_database_provider
from dotenv import load_dotenv

from storage.cluster import ClusterManager

# ----------------------------------------------------------------------------
# Suppress asyncmy warnings that break pytest logging
# ----------------------------------------------------------------------------
logging.getLogger("asyncmy").setLevel(logging.ERROR)


# ----------------------------------------------------------------------------
# Load environment variables (only once)
# ----------------------------------------------------------------------------
load_dotenv()


# ----------------------------------------------------------------------------
# Local SimpleConfig (matches DBCore's DatabaseConfigProtocol)
# ----------------------------------------------------------------------------
class SimpleConfig:
    """Simple configuration container for database connection parameters.

    Attributes:
    provider_type (str | None): Database provider type, e.g., 'sqlite', 'postgres'.
    sqlite_driver (str | None): SQLite driver name if using SQLite.
    db_path (str | None): File path to the SQLite database file.
    db_host (str | None): Database server hostname or IP address.
    db_port (str | None): Database server port number.
    db_user (str | None): Username for database authentication.
    db_password (str | None): Password for database authentication.
    db_database (str | None): Name of the specific database to connect to.

    Args:
    **kwargs: Arbitrary keyword arguments corresponding to the above attributes.
    """
    def __init__(self, **kwargs):
        self.provider_type = kwargs.get("provider_type")
        self.sqlite_driver = kwargs.get("sqlite_driver")
        self.db_path = kwargs.get("db_path")
        self.db_host = kwargs.get("db_host")
        self.db_port = kwargs.get("db_port")
        self.db_user = kwargs.get("db_user")
        self.db_password = kwargs.get("db_password")
        self.db_database = kwargs.get("db_database")


# ----------------------------------------------------------------------------
# Session-level state
# ----------------------------------------------------------------------------
_TEST_DB_NAME: str | None = None
_KEEP_TEST_DB: bool = False


def pytest_addoption(parser):
    """Add command-line option to keep test databases after test session."""
    parser.addoption(
        "--keep-test-db",
        action="store_true",
        default=False,
        help="Keep test databases (do not drop after tests)",
    )


def pytest_sessionstart(session):
    """Generate a unique test database name for the session."""
    global _TEST_DB_NAME, _KEEP_TEST_DB
    _KEEP_TEST_DB = session.config.getoption("--keep-test-db")
    raw_uuid = uuid.uuid4().hex[:8]
    _TEST_DB_NAME = f"povray_test_{raw_uuid}"


async def _drop_database(db_name: str, config: dict) -> None:
    """Drop the test database using a separate connection."""
    conn = await asyncmy.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        db="mysql",
    )
    async with conn.cursor() as cur:
        await cur.execute(f"DROP DATABASE IF EXISTS {db_name}")
    await conn.ensure_closed()


def pytest_sessionfinish(session, exitstatus):
    """Drop the test database at session end unless --keep-test-db is set."""
    global _TEST_DB_NAME, _KEEP_TEST_DB
    if not _TEST_DB_NAME or _KEEP_TEST_DB:
        return

    backend = os.getenv("DB_BACKEND", "mariadb")
    if backend in ("sqlite", "apsw_sqlite", "aio_sqlite"):
        return

    config = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }
    try:
        asyncio.run(_drop_database(_TEST_DB_NAME, config))
    except Exception as e:
        print(f"Warning: Failed to drop test database {_TEST_DB_NAME}: {e}", file=sys.stderr)


# ----------------------------------------------------------------------------
# Fixtures - all async fixtures MUST be function-scoped to avoid event-loop mismatch
# ----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_db_name() -> str:
    """Return the unique test database name for this session."""
    global _TEST_DB_NAME
    return _TEST_DB_NAME


@pytest_asyncio.fixture(scope="function")  # <-- CRITICAL: function scope
async def db_provider(test_db_name):
    """Create a DBCore provider connected to the test database.

    The database is created if it does not exist.
    """
    backend = os.getenv("DB_BACKEND", "mariadb")

    config = SimpleConfig(
        provider_type=backend,
        db_host=os.getenv("DB_HOST"),
        db_port=int(os.getenv("DB_PORT", 3306)),
        db_user=os.getenv("DB_USER"),
        db_password=os.getenv("DB_PASSWORD"),
        db_database=test_db_name,
        sqlite_driver=os.getenv("SQLITE_DRIVER", "apsw") if backend == "sqlite" else None,
        db_path=os.getenv("DB_PATH", "/tmp/povray_test.db") if backend == "sqlite" else None,
    )

    provider = create_database_provider(config)

    # For MariaDB/MySQL, ensure the database exists
    if backend in ("mariadb", "mysql"):
        sys_conn = await asyncmy.connect(
            host=config.db_host,
            port=config.db_port,
            user=config.db_user,
            password=config.db_password,
            db="mysql",
        )
        async with sys_conn.cursor() as cur:
            await cur.execute(f"CREATE DATABASE IF NOT EXISTS {test_db_name}")
        await sys_conn.ensure_closed()

    await provider.initialize()
    yield provider
    await provider.close()


@pytest_asyncio.fixture(scope="function")  # <-- CRITICAL: function scope
async def cluster_with_schema(db_provider):
    """ClusterManager instance with a full schema applied."""
    cluster = ClusterManager(db_provider)

    # Create tables (simplified from install.sql)
    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS render_jobs (
            job_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            job_name VARCHAR(255) NOT NULL,
            total_frames INTEGER,
            width INTEGER,
            height INTEGER,
            fps INTEGER,
            quality INTEGER,
            antialias VARCHAR(10),
            antialias_depth INTEGER,
            antialias_threshold FLOAT,
            sampling_method INTEGER,
            gravity FLOAT NOT NULL DEFAULT 9.81,
            water_level FLOAT NOT NULL DEFAULT 0.0,
            preset_id INTEGER,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """, unsafe=True)

    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS frames (
            job_id INTEGER,
            frame_id INTEGER,
            status VARCHAR(20) DEFAULT 'pending',
            started_at TIMESTAMP NULL,
            completed_at TIMESTAMP NULL,
            PRIMARY KEY (job_id, frame_id)
        )
    """, unsafe=True)

    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS textures (
            texture_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            texture_name VARCHAR(255) UNIQUE,
            texture_description TEXT
        )
    """, unsafe=True)

    # Insert default textures
    for tex in ["WaterTexture", "Jade", "FireTexture", "LimeStoneTexture"]:
        await db_provider.execute_raw(
            "INSERT IGNORE INTO textures (texture_name) VALUES (%s)",
            (tex,),
            unsafe=True,
        )

    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS texture_presets (
            preset_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            texture_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            pigment_r FLOAT NOT NULL DEFAULT 1.0,
            pigment_g FLOAT NOT NULL DEFAULT 1.0,
            pigment_b FLOAT NOT NULL DEFAULT 1.0,
            pigment_t FLOAT NOT NULL DEFAULT 0.0,
            ambient FLOAT NOT NULL DEFAULT 0.1,
            diffuse FLOAT NOT NULL DEFAULT 0.9,
            reflection FLOAT NOT NULL DEFAULT 0.0,
            specular FLOAT NOT NULL DEFAULT 0.0,
            roughness FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (texture_id) REFERENCES textures(texture_id) ON DELETE CASCADE
        )
    """, unsafe=True)

    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS particle_births (
            birth_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            job_id INTEGER NOT NULL,
            particle_id INTEGER NOT NULL,
            birth_time FLOAT NOT NULL,
            x0 FLOAT NOT NULL,
            y0 FLOAT NOT NULL,
            z0 FLOAT NOT NULL,
            vx0 FLOAT NOT NULL,
            vy0 FLOAT NOT NULL,
            vz0 FLOAT NOT NULL,
            size FLOAT NOT NULL,
            texture_id INTEGER NOT NULL,
            seed INTEGER NOT NULL,
            impact_time FLOAT DEFAULT NULL,
            UNIQUE KEY (job_id, particle_id),
            FOREIGN KEY (job_id) REFERENCES render_jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (texture_id) REFERENCES textures(texture_id)
        )
    """, unsafe=True)

    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS simulation_metrics (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            job_id INTEGER NOT NULL,
            time FLOAT NOT NULL,
            particle_count INTEGER DEFAULT 0,
            min_x FLOAT DEFAULT NULL,
            max_x FLOAT DEFAULT NULL,
            min_y FLOAT DEFAULT NULL,
            max_y FLOAT DEFAULT NULL,
            min_z FLOAT DEFAULT NULL,
            max_z FLOAT DEFAULT NULL,
            avg_velocity FLOAT DEFAULT NULL,
            max_velocity FLOAT DEFAULT NULL,
            kinetic_energy FLOAT DEFAULT NULL,
            potential_energy FLOAT DEFAULT NULL,
            total_energy FLOAT DEFAULT NULL,
            momentum_x FLOAT DEFAULT NULL,
            momentum_y FLOAT DEFAULT NULL,
            momentum_z FLOAT DEFAULT NULL,
            nan_count INTEGER DEFAULT 0,
            inf_count INTEGER DEFAULT 0,
            UNIQUE KEY (job_id, time),
            FOREIGN KEY (job_id) REFERENCES render_jobs(job_id) ON DELETE CASCADE
        )
    """, unsafe=True)

    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS frame_particle_cache (
            cache_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            job_id INTEGER NOT NULL,
            frame INTEGER NOT NULL,
            particle_data LONGTEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY (job_id, frame),
            FOREIGN KEY (job_id) REFERENCES render_jobs(job_id) ON DELETE CASCADE
        )
    """, unsafe=True)

    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS nodes (
            node_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            node_name VARCHAR(255) NOT NULL,
            ip_address VARCHAR(45) NOT NULL,
            role ENUM('master','render','database','storage','monitor','generator') NOT NULL,
            status ENUM('active','inactive') NOT NULL DEFAULT 'active',
            last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            cpu_cores INTEGER NOT NULL,
            memory_gb FLOAT NOT NULL DEFAULT 0
        )
    """, unsafe=True)

    await db_provider.execute_raw("""
        CREATE TABLE IF NOT EXISTS work_threads (
            thread_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            node_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            frame_id INTEGER NOT NULL,
            status ENUM('queued','processing','completed') DEFAULT 'queued',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY (node_id),
            KEY (job_id),
            KEY (frame_id),
            KEY (job_id, frame_id),
            FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES render_jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (job_id, frame_id) REFERENCES frames(job_id, frame_id) ON DELETE CASCADE
        )
    """, unsafe=True)

    return cluster
