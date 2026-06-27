# src/render.py

"""Render daemon - polls database for pending frames and renders them with POV-Ray.

Time-based particle queries: each frame is sampled at t = frame / fps.
No frame semantics leak into the physics core.
Textures are generated from preset parameters stored in the database.
Scene construction uses Vapory (object-oriented) to generate .pov files.
"""
import asyncio
import os
import platform
import subprocess
import sys
from pathlib import Path

from DBCore import create_database_provider
from dotenv import load_dotenv

from lib.pov_builder import build_scene, write_pov_file
from sim.validator import PhysicsValidator
from storage.cluster import ClusterManager


class SimpleConfig:
    """Simple configuration container for database connections.

    Attributes:
    provider_type (str | None): Type of database provider.
    sqlite_driver (str | None): SQLite driver name.
    db_path (str | None): Path to the SQLite database file.
    db_host (str | None): Database server hostname.
    db_port (str | None): Database server port.
    db_user (str | None): Username for database authentication.
    db_password (str | None): Password for database authentication.
    db_database (str | None): Name of the target database.
    """

    def __init__(self, **kwargs):
        self.provider_type = kwargs.get('provider_type')
        self.sqlite_driver = kwargs.get('sqlite_driver')
        self.db_path = kwargs.get('db_path')
        self.db_host = kwargs.get('db_host')
        self.db_port = kwargs.get('db_port')
        self.db_user = kwargs.get('db_user')
        self.db_password = kwargs.get('db_password')
        self.db_database = kwargs.get('db_database')

def detect_povray_path() -> str:
    """Locate the POV-Ray executable."""
    current_os = platform.system()
    if current_os == 'Windows':
        return 'C:\\Program Files\\POV-Ray\\v3.7\\bin\\pvengine64.exe'
    elif current_os == 'Darwin':
        return '/Applications/POV-Ray 3.7/POV-Ray.app/Contents/MacOS/POV-Ray'
    else:
        try:
            result = subprocess.run(['which', 'povray'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            print('Error: POV-Ray not found in PATH.', file=sys.stderr)
            sys.exit(1)

async def run_povray(input_file: Path, output_file: Path, width: int, height: int, quality: int, antialias: bool, antialias_depth: int) -> int:
    """Run POV-Ray on a single frame.

    Returns return code (0 = success).
    """
    povray = detect_povray_path()
    cmd = [povray]
    if platform.system() == 'Windows':
        cmd.append('/Exit')
    else:
        cmd.append('+X')
    cmd.extend([f'+I{input_file}', f'+O{output_file}', f'+W{width}', f'+H{height}', f'+Q{quality}'])
    if antialias:
        cmd.append('+A')
        cmd.append(f'+R{antialias_depth}')
    print(f'  Rendering: {input_file.name} -> {output_file.name}')
    proc = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f'    POV-Ray failed: {proc.stderr}', file=sys.stderr)
    return proc.returncode

async def _fetch_next_frame(cluster: ClusterManager, job_id: int | None=None) -> tuple[int, int] | None:
    """Fetch the next pending frame."""
    if job_id is not None:
        rows = await cluster.db.fetch_all("\n            SELECT f.frame_id, f.job_id\n            FROM frames f\n            JOIN render_jobs j ON f.job_id = j.job_id\n            WHERE f.status = 'pending' AND f.job_id = %s\n            ORDER BY f.frame_id\n            LIMIT 1\n            ", (job_id,))
    else:
        rows = await cluster.db.fetch_all("\n            SELECT f.frame_id, f.job_id\n            FROM frames f\n            JOIN render_jobs j ON f.job_id = j.job_id\n            WHERE f.status = 'pending'\n            ORDER BY j.created_at, f.frame_id\n            LIMIT 1\n            ")
    if rows:
        return (rows[0]['frame_id'], rows[0]['job_id'])
    return None

async def _get_job_details(cluster: ClusterManager, job_id: int) -> dict | None:
    """Fetch job details (fps, width, height, quality, antialias, antialias_depth)."""
    rows = await cluster.db.fetch_all('\n        SELECT fps, width, height, quality, antialias, antialias_depth\n        FROM render_jobs\n        WHERE job_id = %s\n        ', (job_id,))
    return rows[0] if rows else None

async def _get_texture_code(cluster: ClusterManager, job_id: int) -> str:
    """Get texture code from preset or fallback.

    This is kept for compatibility, but with Vapory we build the texture object directly.
    """
    preset = await cluster.get_preset_for_job(job_id)
    if not preset:
        print(f'Frame: no preset found for job {job_id}. Using fallback.')
        return 'texture { pigment { rgb <1,1,1> } }'
    return ''

async def _render_single_frame(cluster: ClusterManager, template_path: Path, frame_id: int, job_id: int) -> bool:
    """Render a single frame using Vapory scene builder."""
    job = await _get_job_details(cluster, job_id)
    if not job:
        print(f'Job {job_id} not found. Marking frame {frame_id} as error.')
        await cluster.update_frame_status(frame_id, 'error')
        return False
    fps = job['fps']
    t = frame_id / fps
    particles = await cluster.get_particles_at_time(job_id, t)
    if particles:
        validator = PhysicsValidator()
        valid, errors = validator.validate_frame(particles)
        if not valid:
            print(f'Frame {frame_id}: validation failed. Errors: {errors}')
    preset = await cluster.get_preset_for_job(job_id)
    if not preset:
        print(f'Frame {frame_id}: no preset found for job {job_id}. Using fallback.')
        preset = {'pigment_r': 1.0, 'pigment_g': 1.0, 'pigment_b': 1.0, 'pigment_t': 0.0, 'ambient': 0.1, 'diffuse': 0.9, 'reflection': 0.0, 'specular': 0.0, 'roughness': 0.0}
    job_name_rows = await cluster.db.fetch_all('SELECT job_name FROM render_jobs WHERE job_id = %s', (job_id,))
    job_name = job_name_rows[0]['job_name'] if job_name_rows else f'job_{job_id}'
    output_dir = Path('output') / job_name
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = template_path.stem
    pov_file = output_dir / f'{base_name}_frame-{frame_id:04d}.pov'
    png_file = output_dir / f'{base_name}_frame-{frame_id:04d}.png'
    camera_pos = [0, 2.5, -3]
    look_at = [0, 2.5, 0]
    if os.getenv('CAMERA_POS'):
        camera_pos = [float(x) for x in os.getenv('CAMERA_POS').split(',')]
    if os.getenv('LOOK_AT'):
        look_at = [float(x) for x in os.getenv('LOOK_AT').split(',')]
    scene = build_scene(particles=particles, preset=preset, camera_pos=camera_pos, look_at=look_at, light_pos=[1500, 2500, -2500], background_color=[0.1, 0.1, 0.1])
    write_pov_file(scene=scene, output_path=str(pov_file), width=job['width'], height=job['height'], quality=job['quality'], antialiasing=job['antialias'] == 'on')
    ret = await run_povray(pov_file, png_file, width=job['width'], height=job['height'], quality=job['quality'], antialias=job['antialias'] == 'on', antialias_depth=job['antialias_depth'])
    if ret == 0:
        await cluster.update_frame_status(frame_id, 'rendered')
        print(f'Frame {frame_id} rendered successfully.')
        return True
    else:
        await cluster.update_frame_status(frame_id, 'error')
        print(f'Frame {frame_id} failed with return code {ret}.')
        return False

async def render_loop(cluster: ClusterManager, template_path: Path, poll_interval: int=10, job_id: int | None=None) -> None:
    """Main render loop with reduced complexity."""
    print(f'Render node started. Polling every {poll_interval}s.')
    print(f'Using template: {template_path}')
    if job_id is not None:
        print(f'Filtering to job_id: {job_id}')
    while True:
        try:
            frame = await _fetch_next_frame(cluster, job_id)
            if not frame:
                await asyncio.sleep(poll_interval)
                continue
            frame_id, current_job_id = frame
            await cluster.update_frame_status(frame_id, 'in progress')
            await _render_single_frame(cluster, template_path, frame_id, current_job_id)
        except KeyboardInterrupt:
            print('\nRender node shutting down.')
            break
        except Exception as e:
            print(f'Error in render loop: {e}')
            await asyncio.sleep(poll_interval)

async def main() -> None:
    """Set up database connection and start the render loop."""
    load_dotenv()
    backend = os.getenv('DB_BACKEND', 'mariadb')
    config = SimpleConfig(provider_type=backend, db_host=os.getenv('DB_HOST'), db_port=int(os.getenv('DB_PORT', 3306)), db_user=os.getenv('DB_USER'), db_password=os.getenv('DB_PASSWORD'), db_database=os.getenv('DB_DATABASE'), sqlite_driver=os.getenv('SQLITE_DRIVER', 'apsw') if backend == 'sqlite' else None, db_path=os.getenv('DB_PATH') if backend == 'sqlite' else None)
    db = create_database_provider(config)
    await db.initialize()
    cluster = ClusterManager(db)
    await cluster.insert_node_info(status='active', role='render')
    template = Path(os.getenv('TEMPLATE_FILE', 'scenes/NewBegining.pov'))
    if not template.exists():
        raise FileNotFoundError(f'Template file not found: {template}')
    poll_interval = int(os.getenv('POLL_INTERVAL', 10))
    try:
        await render_loop(cluster, template, poll_interval)
    except KeyboardInterrupt:
        print('Shutting down...')
    finally:
        await db.close()

def main_sync() -> None:
    """Synchronous entry point for console script."""
    asyncio.run(main())
if __name__ == '__main__':
    main_sync()
