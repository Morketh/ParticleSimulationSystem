# src/generator.py
"""Particle generation entry point.

Creates a fountain simulation, stores birth records in the database,
ensures texture presets exist, and optionally runs validation.
"""

import asyncio
import os

import numpy as np
from DBCore import create_database_provider
from dotenv import load_dotenv

from sim.particles import FountainSimulator
from sim.validator import PhysicsValidator
from storage.cluster import ClusterManager


class SimpleConfig:
    """Configuration object matching DBCore's DatabaseConfigProtocol."""

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
    """Generate particles and store in database."""
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

    # Simulation parameters from environment or defaults
    num_particles = int(os.getenv("NUM_PARTICLES", 10000))
    num_frames = int(os.getenv("NUM_FRAMES", 1000))
    fps = int(os.getenv("FPS", 60))
    gravity = float(os.getenv("GRAVITY", 9.81))
    water_level = float(os.getenv("WATER_LEVEL", 0.0))

    # Emitter parameters
    apex_x = float(os.getenv("APEX_X", 0.0))
    apex_y = float(os.getenv("APEX_Y", 1.5))
    apex_z = float(os.getenv("APEX_Z", 14.0))
    cone_height = float(os.getenv("CONE_HEIGHT", 2.0))
    cone_angle_deg = float(os.getenv("CONE_ANGLE", 30.0))
    cone_angle_rad = np.radians(cone_angle_deg)
    base_radius = float(os.getenv("BASE_RADIUS", 1.75))
    speed_min = float(os.getenv("SPEED_MIN", 3.0))
    speed_max = float(os.getenv("SPEED_MAX", 8.0))
    birth_start = float(os.getenv("BIRTH_START", 0.0))
    birth_end = float(os.getenv("BIRTH_END", 0.5))
    size_min = float(os.getenv("SIZE_MIN", 0.01))
    size_max = float(os.getenv("SIZE_MAX", 0.03))
    texture_name = os.getenv("TEXTURE", "WaterTexture")
    preset_name = os.getenv("PRESET_NAME", "Default")
    seed_offset = int(os.getenv("SEED_OFFSET", 42))

    # Preset parameters (PBR)
    preset_params = {
        "pigment_r": float(os.getenv("PIGMENT_R", 0.7)),
        "pigment_g": float(os.getenv("PIGMENT_G", 0.9)),
        "pigment_b": float(os.getenv("PIGMENT_B", 1.0)),
        "pigment_t": float(os.getenv("PIGMENT_T", 0.85)),
        "ambient": float(os.getenv("AMBIENT", 0.1)),
        "diffuse": float(os.getenv("DIFFUSE", 0.9)),
        "reflection": float(os.getenv("REFLECTION", 0.4)),
        "specular": float(os.getenv("SPECULAR", 0.9)),
        "roughness": float(os.getenv("ROUGHNESS", 0.001)),
    }

    # Ensure preset exists and get its ID
    preset_id = await cluster.ensure_preset(texture_name, preset_name, preset_params)

    # Job name
    job_name = f"Fountain_{num_particles}p_{num_frames}f_{fps}fps"

    # Create simulator and generate particles
    sim = FountainSimulator(gravity=gravity, water_level=water_level)
    sim.add_conical_fountain(
        num_particles=num_particles,
        apex_x=apex_x, apex_y=apex_y, apex_z=apex_z,
        cone_height=cone_height,
        cone_angle_rad=cone_angle_rad,
        base_radius=base_radius,
        speed_min=speed_min,
        speed_max=speed_max,
        birth_start=birth_start,
        birth_end=birth_end,
        size_min=size_min,
        size_max=size_max,
        texture=texture_name,
        seed_offset=seed_offset,
    )
    print(f"Generated {len(sim.particles)} particles.")

    # Create job with preset_id
    width = int(os.getenv("RENDER_WIDTH", 1920))
    height = int(os.getenv("RENDER_HEIGHT", 1080))
#    quality = int(os.getenv("QUALITY", 11))
#    antialias = os.getenv("ANTIALIAS", "on")
#    antialias_depth = int(os.getenv("ANTIALIAS_DEPTH", 5))
    job_id = await cluster.create_job(
        job_name=job_name,
        num_frames=num_frames,
        width=width,
        height=height,
        fps=fps,
        gravity=gravity,
        water_level=water_level,
        preset_id=preset_id,
    )
    print(f"Job created with ID {job_id}")

    # Insert frames
    await cluster.insert_frames(job_id, num_frames)
    print(f"Inserted {num_frames} frames.")

    # Insert particle births
    await cluster.insert_particle_births(job_id, sim.particles)
    print(f"Inserted {len(sim.particles)} birth records.")

    # Optional validation
    if os.getenv("RUN_VALIDATION", "true").lower() in ("true", "1", "yes"):
        print("Running validation on sampled frames...")
        validator = PhysicsValidator()
        sample_interval = max(1, num_frames // 20)
        sample_frames = range(1, num_frames+1, sample_interval)
        valid_count = 0
        for frame in sample_frames:
            t = frame / fps
            particles = await cluster.get_particles_at_time(job_id, t)
            if not particles:
                continue
            valid, errors = validator.validate_frame(particles)
            if valid:
                valid_count += 1
            else:
                print(f"  Frame {frame}: validation failed.")
                for err in errors:
                    print(f"    Particle {err['particle_id']}: {err['errors']}")
        print(f"Validated {len(sample_frames)} frames, {valid_count} passed.")

    # Mark job as ready for rendering
    await cluster.update_job_status(job_id, "pending")
    print(f"Job {job_id} is ready for rendering.")

    await db.close()
    print("Done.")


def main_sync() -> None:
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
