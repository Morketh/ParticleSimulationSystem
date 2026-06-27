# src/make_mp4.py

"""Stitch rendered PNG frames into an MP4 video using ffmpeg.

This script reads job data from the database and compiles the frames
into a video file.
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from DBCore import create_database_provider
from dotenv import load_dotenv

from storage.cluster import ClusterManager


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
        self.provider_type = kwargs.get('provider_type')
        self.sqlite_driver = kwargs.get('sqlite_driver')
        self.db_path = kwargs.get('db_path')
        self.db_host = kwargs.get('db_host')
        self.db_port = kwargs.get('db_port')
        self.db_user = kwargs.get('db_user')
        self.db_password = kwargs.get('db_password')
        self.db_database = kwargs.get('db_database')

def detect_ffmpeg_path() -> str:
    """Locate the ffmpeg executable."""
    try:
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print('Error: ffmpeg not found in PATH.', file=sys.stderr)
        sys.exit(1)

async def run_ffmpeg(input_pattern: str, output_file: Path, fps: int, total_frames: int) -> int:
    """Run ffmpeg to stitch frames into an MP4.

    Returns return code (0 = success).
    """
    ffmpeg = detect_ffmpeg_path()
    cmd = [ffmpeg, '-framerate', str(fps), '-i', input_pattern, '-frames:v', str(total_frames), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(output_file)]
    print(f"Running: {' '.join(cmd)}")
    proc = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f'ffmpeg failed: {proc.stderr}', file=sys.stderr)
    return proc.returncode

async def main() -> None:
    """Compile rendered frames into an MP4 for the most recent completed job."""
    load_dotenv()
    backend = os.getenv('DB_BACKEND', 'mariadb')
    config = SimpleConfig(provider_type=backend, db_host=os.getenv('DB_HOST'), db_port=int(os.getenv('DB_PORT', 3306)), db_user=os.getenv('DB_USER'), db_password=os.getenv('DB_PASSWORD'), db_database=os.getenv('DB_DATABASE'), sqlite_driver=os.getenv('SQLITE_DRIVER', 'apsw') if backend == 'sqlite' else None, db_path=os.getenv('DB_PATH') if backend == 'sqlite' else None)
    db = create_database_provider(config)
    await db.initialize()
    cluster = ClusterManager(db)
    jobs = await cluster.db.fetch_all("\n        SELECT job_id, job_name, fps, total_frames\n        FROM render_jobs\n        WHERE status = 'completed'\n        ORDER BY created_at DESC\n        LIMIT 1\n        ")
    if not jobs:
        print('No completed jobs found.')
        await db.close()
        return
    job = jobs[0]
    job_name = job['job_name']
    fps = job['fps']
    total_frames = job['total_frames']
    frames = await cluster.db.fetch_all("SELECT COUNT(*) as count FROM frames WHERE job_id = %s AND status = 'rendered'", (job['job_id'],))
    if not frames or frames[0]['count'] == 0:
        print(f"No rendered frames found for job {job['job_id']}.")
        await db.close()
        return
    output_dir = Path('output') / job_name
    input_pattern = str(output_dir / 'frame_%04d.png')
    output_file = output_dir / f'{job_name}.mp4'
    ret = await run_ffmpeg(input_pattern, output_file, fps, total_frames)
    if ret == 0:
        print(f'Video created: {output_file}')
    else:
        print('Video compilation failed.')
    await db.close()

def main_sync() -> None:
    """Synchronous entry point for console script."""
    asyncio.run(main())
if __name__ == '__main__':
    main_sync()
