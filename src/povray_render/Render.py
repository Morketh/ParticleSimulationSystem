#!/usr/bin/env python3
# src/povray_render/Render.py
"""Render node daemon – polls the database for pending frames and renders them with POV‑Ray.

This script runs an infinite loop, fetching the next pending frame for a job,
building the POV‑Ray scene with particle data, invoking the renderer, and
updating the database accordingly.
"""

import asyncio
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from DBCore import create_database_provider

from .cluster import ClusterManager
from .particles import ParticleGenerator  # not directly used here, but for reference

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


# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------

def detect_povray_path() -> str:
    """
    Locate the POV‑Ray executable on the current system.
    Returns the path as a string, or exits on failure.
    """
    current_os = platform.system()
    if current_os == "Windows":
        # Default Windows path (may need to be adjusted)
        return r"C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe"
    elif current_os == "Darwin":
        # macOS default path
        return "/Applications/POV-Ray 3.7/POV-Ray.app/Contents/MacOS/POV-Ray"
    else:
        # Linux/Unix: try `which povray`
        try:
            result = subprocess.run(
                ["which", "povray"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            print("Error: POV-Ray executable not found in PATH. Please install POV-Ray or set the path.", file=sys.stderr)
            sys.exit(1)


def format_particle_objects(particles: list[dict[str, Any]]) -> str:
    """
    Format a list of particle dictionaries into POV‑Ray object syntax.

    Each dict must contain:
        position_x, position_y, position_z, size

    Returns a string of sphere declarations.
    """
    lines = []
    for p in particles:
        x, y, z = p["position_x"], p["position_y"], p["position_z"]
        size = p["size"]
        lines.append(f"sphere {{ <{x}, {y}, {z}>, {size}, 1.5 }}")
    return "\n".join(lines)


def build_output_file(template_path: Path, output_path: Path, particle_objects: str) -> None:
    """
    Read a POV‑Ray template file, replace the //PARTICLE_SYSTEM marker,
    and write the result to output_path.
    """
    content = template_path.read_text(encoding="utf-8")
    content = content.replace("//PARTICLE_SYSTEM", particle_objects)
    output_path.write_text(content, encoding="utf-8")


async def run_povray(
    input_file: Path,
    output_file: Path,
    width: int,
    height: int,
    quality: int,
    antialias: bool,
    antialias_depth: int,
) -> int:
    """
    Invoke POV‑Ray as a subprocess to render the given file.

    Returns the return code (0 = success).
    """
    povray = detect_povray_path()
    cmd = [povray]
    if platform.system() == "Windows":
        cmd.append("/Exit")
    else:
        cmd.append("+X")

    cmd.extend([
        f"+I{input_file}",
        f"+O{output_file}",
        f"+W{width}",
        f"+H{height}",
        f"+Q{quality}",
    ])
    if antialias:
        cmd.append("+A")
        cmd.append(f"+R{antialias_depth}")

    print(f"  Rendering: {input_file.name} -> {output_file.name}")
    proc = await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"    POV‑Ray failed with code {proc.returncode}: {proc.stderr}", file=sys.stderr)
    return proc.returncode


def remove_extension(path: Path) -> str:
    """Return the file name without its extension."""
    return path.stem


def create_output_directory(path: Path) -> None:
    """Ensure the output directory exists."""
    path.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------------
# Main render loop
# ----------------------------------------------------------------------------

async def render_loop(
    cluster: ClusterManager,
    template_path: Path,
    poll_interval: int = 10,
) -> None:
    """
    Infinite loop: poll for pending frames, render them, and update status.

    Args:
        cluster: Initialised ClusterManager.
        template_path: Path to the POV‑Ray template file.
        poll_interval: Seconds to wait between polls.
    """
    print(f"Render node started. Polling every {poll_interval}s...")
    while True:
        try:
            # 1. Fetch the next pending frame
            frame = await cluster.get_next_frame(job_id=1)  # TODO: support multiple jobs
            # For now, we assume a single job; later we could query for the earliest pending job.
            # Better: we need a method to get the next pending job. For simplicity, we'll use job_id=1.
            # In a real system, we'd have a job scheduler.
            # For now, we'll fetch the first pending frame from any job.
            # We'll need a method to get the next pending frame across all jobs.
            # Let's adjust ClusterManager to have a method `get_next_available_frame()` that finds any pending frame.
            # Since we haven't added that, we'll fallback to using raw SQL for this.
            # TODO: add proper job scheduling.
            # For now, we'll just get the first pending frame from the frames table.
            rows = await cluster.db.fetch_all(
                "SELECT frame_id, job_id FROM frames WHERE status = 'pending' LIMIT 1"
            )
            if not rows:
                await asyncio.sleep(poll_interval)
                continue
            frame_id = rows[0]["frame_id"]
            job_id = rows[0]["job_id"]

            # 2. Mark frame as 'in progress'
            await cluster.update_frame_status(frame_id, "in progress")

            # 3. Fetch job details (render settings)
            job_rows = await cluster.db.fetch_all(
                "SELECT width, height, quality, antialias, antialias_depth FROM render_jobs WHERE job_id = %s",
                (job_id,)
            )
            if not job_rows:
                print(f"Job {job_id} not found. Skipping frame {frame_id}.")
                await cluster.update_frame_status(frame_id, "error")
                continue
            job = job_rows[0]

            # 4. Fetch particles for this frame, grouped by texture
            textures = await cluster.get_textures()
            all_particles = []
            for tex in textures:
                tex_id = tex["texture_id"]
                particles = await cluster.get_particles(job_id, frame_id, tex_id)
                if particles:
                    all_particles.extend(particles)

            # 5. Build the POV file
            job_name_rows = await cluster.db.fetch_all(
                "SELECT job_name FROM render_jobs WHERE job_id = %s",
                (job_id,)
            )
            job_name = job_name_rows[0]["job_name"] if job_name_rows else "unknown"
            output_dir = Path("output") / job_name
            create_output_directory(output_dir)
            out_pov = output_dir / f"{remove_extension(template_path)}_frame-{frame_id:04d}.pov"
            particle_objects = format_particle_objects(all_particles)
            build_output_file(template_path, out_pov, particle_objects)

            # 6. Render the frame
            png_file = output_dir / f"{remove_extension(template_path)}_frame-{frame_id:04d}.png"
            ret = await run_povray(
                out_pov,
                png_file,
                width=job["width"],
                height=job["height"],
                quality=job["quality"],
                antialias=job["antialias"] == "on",
                antialias_depth=job["antialias_depth"],
            )

            # 7. Update frame status
            if ret == 0:
                await cluster.update_frame_status(frame_id, "rendered")
                print(f"Frame {frame_id} rendered successfully.")
            else:
                await cluster.update_frame_status(frame_id, "error")
                print(f"Frame {frame_id} failed.")

        except Exception as e:
            print(f"Error in render loop: {e}")
            await asyncio.sleep(poll_interval)


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

async def main() -> None:
    """Set up database connection and start the render loop."""
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

    # Register this node as a render node
    await cluster.insert_node_info(status="active", role="render")

    # Path to the template POV file
    template = Path(os.getenv("TEMPLATE_FILE", "scenes/NewBegining.pov"))
    if not template.exists():
        raise FileNotFoundError(f"Template file not found: {template}")

    poll_interval = int(os.getenv("POLL_INTERVAL", 10))

    try:
        await render_loop(cluster, template, poll_interval)
    except KeyboardInterrupt:
        print("\nRender node shutting down.")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())