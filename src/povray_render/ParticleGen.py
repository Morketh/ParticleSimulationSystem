#!/usr/bin/env python3
# src/povray_render/ParticleGen.py
"""Particle generation script for fountain simulations.

Generates particle data for a fountain simulation and inserts it into
the database via DBCore IR.
"""

import asyncio
import os

import numpy as np
from dotenv import load_dotenv

from DBCore import create_database_provider

from .cluster import ClusterManager
from .particles import ParticleGenerator


# ----------------------------------------------------------------------------
# Local config class matching DBCore's DatabaseConfigProtocol
# ----------------------------------------------------------------------------
class SimpleConfig:
    def __init__(self, **kwargs):
        self.provider_type = kwargs.get("provider_type")
        self.sqlite_driver = kwargs.get("sqlite_driver")
        self.db_path = kwargs.get("db_path")
        self.db_host = kwargs.get("db_host")
        self.db_port = kwargs.get("db_port")
        self.db_user = kwargs.get("db_user")
        self.db_password = kwargs.get("db_password")
        self.db_database = kwargs.get("db_database")


async def main() -> None:
    """Generate fountain particles and insert them into the database."""
    load_dotenv()
    backend = os.getenv("DB_BACKEND", "mariadb")

    config = SimpleConfig(
        provider_type=backend,
        db_host=os.getenv("DB_HOST"),
        db_port=int(os.getenv("DB_PORT", 3306)),
        db_user=os.getenv("DB_USER"),
        db_password=os.getenv("DB_PASSWORD"),
        db_database=os.getenv("DB_DATABASE"),
        sqlite_driver=os.getenv("SQLITE_DRIVER", "apsw") if backend == "sqlite" else None,
        db_path=os.getenv("DB_PATH") if backend == "sqlite" else None,
    )

    db = create_database_provider(config)
    await db.initialize()

    cluster = ClusterManager(db)

    res_x = int(os.getenv("RES_X", 1920))
    res_y = int(os.getenv("RES_Y", 1080))
    antialias = os.getenv("ANTIALIAS", "off")
    quality = int(os.getenv("QUALITY", 11))
    fps = int(os.getenv("FPS", 45))
    num_frames = int(os.getenv("NUM_FRAMES", 1000))
    num_particles = int(os.getenv("NUM_PARTICLES", 1000))

    job_name = f"Fountain_{res_x}x{res_y}_Q{quality}_aa{antialias}_fr{fps}"

    apex_position = [0, 1.5, 14]
    cone_height = 2.0
    cone_angle = np.pi / 6
    base_radius = 1.75
    wind_direction = [1, 0.5, 0]
    wind_velocity = 0.0

    water_particles = ParticleGenerator()
    water_particles.generate_conical_fountain(
        num_particles,
        apex_position,
        cone_height,
        cone_angle,
        base_radius,
        wind_direction,
        wind_velocity,
        texture="WaterTexture",
    )

    await cluster.insert_node_info(status="active", role="generator")

    job_id = await cluster.create_job(
        job_name=job_name,
        num_frames=num_frames,
        res_x=res_x,
        res_y=res_y,
        fps=fps,
        quality=quality,
        antialias=antialias,
        antialias_depth=5,
        antialias_threshold=0.1,
        sampling_method=2,
    )

    await cluster.insert_frames(job_id, num_frames)

    print(f"Inserting particle data for job {job_id}...")
    for frame_num in range(1, num_frames + 1):
        print(f"  Frame {frame_num}/{num_frames}", end="\r", flush=True)
        particle_data = water_particles.plot_particles_at_frame(frame_num, frame_rate=fps)
        await cluster.insert_particle_data(job_id, frame_num, particle_data)

    print(f"\nParticle data inserted for job {job_name} (job_id={job_id})")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())