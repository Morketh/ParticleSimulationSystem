# src/storage/cluster.py
"""ClusterManager - DBCore IR-based storage and retrieval layer for the fountain simulation.

This layer is responsible for:
- Storing particle birth records (initial conditions)
- Retrieving particle states at arbitrary absolute time t
- Managing job configuration (gravity, water_level, texture preset)
- Ensuring textures and presets exist

IMPORTANT: This layer contains NO physics constants.
Physics constants are read from the job config (database).
"""

import json
from typing import Any

from DBCore.base import DatabaseProvider
from DBCore.ir import IRBulkInsert, IRInsert, IRSelect, IRUpdate
from DBCore.ir.conditions import Condition, LogicalExpression

from sim.particles import ParticleBirth


class ClusterManager:
    """Database manager for the fountain simulation system.

    Uses DBCore IR for all database operations.
    """

    def __init__(self, db: DatabaseProvider):
        self.db = db

    # --------------------------------------------------------------------------
    # Texture and Preset Management
    # --------------------------------------------------------------------------

    async def ensure_texture(self, name: str, description: str = "") -> int:
        """Get or create a texture identity. Returns texture_id."""
        rows = await self.db.fetch_all(
            "SELECT texture_id FROM textures WHERE texture_name = %s",
            (name,)
        )
        if rows:
            return rows[0]["texture_id"]
        await self.db.execute_raw(
            "INSERT INTO textures (texture_name, texture_description) VALUES (%s, %s)",
            (name, description),
            unsafe=True,
        )
        return await self._last_insert_id()

    async def ensure_preset(
        self,
        texture_name: str,
        preset_name: str,
        params: dict[str, float],
    ) -> int:
        """Get or create a texture preset. Returns preset_id.

        Expects params with keys: pigment_r, pigment_g, pigment_b, pigment_t,
        ambient, diffuse, reflection, specular, roughness.
        """
        tex_id = await self.ensure_texture(texture_name)
        # Check existing
        rows = await self.db.fetch_all(
            """
            SELECT preset_id FROM texture_presets
            WHERE texture_id = %s AND name = %s
            """,
            (tex_id, preset_name)
        )
        if rows:
            return rows[0]["preset_id"]

        # Insert new preset
        sql = """
            INSERT INTO texture_presets
            (texture_id, name, pigment_r, pigment_g, pigment_b, pigment_t,
             ambient, diffuse, reflection, specular, roughness)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        await self.db.execute_raw(
            sql,
            (
                tex_id,
                preset_name,
                params.get("pigment_r", 1.0),
                params.get("pigment_g", 1.0),
                params.get("pigment_b", 1.0),
                params.get("pigment_t", 0.0),
                params.get("ambient", 0.1),
                params.get("diffuse", 0.9),
                params.get("reflection", 0.0),
                params.get("specular", 0.0),
                params.get("roughness", 0.0),
            ),
            unsafe=True,
        )
        return await self._last_insert_id()

    async def get_preset_for_job(self, job_id: int) -> dict[str, Any] | None:
        """Fetch the texture preset parameters for a job."""
        rows = await self.db.fetch_all("""
            SELECT tp.*
            FROM texture_presets tp
            JOIN render_jobs rj ON rj.preset_id = tp.preset_id
            WHERE rj.job_id = %s
        """, (job_id,))
        return rows[0] if rows else None

    async def _get_texture_id_map(self) -> dict[str, int]:
        """Fetch texture_name -> texture_id mapping."""
        select = IRSelect(table="textures", columns=["texture_id", "texture_name"])
        rows = await self.db.fetch_all_ir(select)
        return {row["texture_name"]: row["texture_id"] for row in rows}

    # --------------------------------------------------------------------------
    # Job Configuration
    # --------------------------------------------------------------------------

    async def create_job(
        self,
        job_name: str,
        num_frames: int,
        width: int,
        height: int,
        fps: int,
        gravity: float = 9.81,
        water_level: float = 0.0,
        preset_id: int | None = None,
    ) -> int:
        """Create a new render job with physics constants and optional preset.

        Returns job_id.
        """
        insert = IRInsert(
            table="render_jobs",
            values={
                "job_name": job_name,
                "total_frames": num_frames,
                "width": width,
                "height": height,
                "fps": fps,
                "status": "pending",
                "gravity": gravity,
                "water_level": water_level,
                "preset_id": preset_id,
            },
        )
        await self.db.execute_ir(insert)
        return await self._last_insert_id()

    async def get_job_config(self, job_id: int) -> dict[str, Any]:
        """Retrieve gravity and water_level for a job."""
        rows = await self.db.fetch_all(
            "SELECT gravity, water_level FROM render_jobs WHERE job_id = %s",
            (job_id,),
        )
        if not rows:
            raise ValueError(f"Job {job_id} not found")
        return {"gravity": rows[0]["gravity"], "water_level": rows[0]["water_level"]}

    async def update_job_status(self, job_id: int, status: str) -> None:
        """Update job status (pending, in progress, completed)."""
        update = IRUpdate(
            table="render_jobs",
            set_values={"status": status},
            where=Condition("job_id", "=", job_id),
        )
        await self.db.execute_ir(update)

    # --------------------------------------------------------------------------
    # Particle Births (Initial Conditions)
    # --------------------------------------------------------------------------

    async def insert_particle_births(self, job_id: int, births: list[ParticleBirth]) -> None:
        """Bulk insert particle birth records.

        Stores only initial conditions - the physics is evaluated at query time.
        """
        if not births:
            return

        # Ensure all textures exist (they should, but just in case)
        texture_names = {b.texture for b in births}
        for name in texture_names:
            await self.ensure_texture(name)

        # Get texture map
        texture_map = await self._get_texture_id_map()

        rows = []
        for b in births:
            tex_id = texture_map.get(b.texture)
            if tex_id is None:
                raise RuntimeError(f"Texture '{b.texture}' not found after ensure.")
            rows.append([
                job_id,
                b.particle_id,
                b.birth_time,
                b.x0, b.y0, b.z0,
                b.vx0, b.vy0, b.vz0,
                b.size,
                tex_id,
                b.seed,
                b.impact_time,
            ])

        bulk = IRBulkInsert(
            table="particle_births",
            columns=[
                "job_id", "particle_id", "birth_time",
                "x0", "y0", "z0",
                "vx0", "vy0", "vz0",
                "size", "texture_id", "seed", "impact_time",
            ],
            values=rows,
        )
        await self.db.bulk_insert_ir(bulk)

    # --------------------------------------------------------------------------
    # Time-Based Particle Queries (Core API)
    # --------------------------------------------------------------------------

    async def get_particles_at_time(
        self,
        job_id: int,
        t: float,
    ) -> list[dict[str, Any]]:
        """Return alive particle states at absolute simulation time t.

        This is the primary API for the renderer.
        Physics is evaluated analytically from stored initial conditions.
        No frame semantics are exposed - t is absolute time.
        """
        config = await self.get_job_config(job_id)
        gravity = config["gravity"]
        water_level = config["water_level"]

        births = await self.db.fetch_all(
            """
            SELECT particle_id, birth_time, x0, y0, z0,
                   vx0, vy0, vz0, size, texture_name, impact_time
            FROM particle_births pb
            JOIN textures tx ON pb.texture_id = tx.texture_id
            WHERE job_id = %s
            """,
            (job_id,),
        )

        states = []
        for b in births:
            if t < b["birth_time"]:
                continue
            if b["impact_time"] is not None and t >= b["impact_time"]:
                continue

            dt = t - b["birth_time"]
            x = b["x0"] + b["vx0"] * dt
            y = b["y0"] + b["vy0"] * dt - 0.5 * gravity * dt * dt
            z = b["z0"] + b["vz0"] * dt

            if y <= water_level:
                continue

            states.append({
                "particle_id": b["particle_id"],
                "position_x": float(x),
                "position_y": float(y),
                "position_z": float(z),
                "velocity_x": float(b["vx0"]),
                "velocity_y": float(b["vy0"] - gravity * dt),
                "velocity_z": float(b["vz0"]),
                "size": float(b["size"]),
                "texture_name": b["texture_name"],
                "status": "alive",
            })

        return states

    # --------------------------------------------------------------------------
    # Frame Cache (Optional, for Render Performance)
    # --------------------------------------------------------------------------

    async def cache_frame_particles(self, job_id: int, frame: int, particle_data: list[dict]) -> None:
        """Cache pre-computed particle data for a specific frame."""
        data_json = json.dumps(particle_data)
        await self.db.execute_raw(
            """
            INSERT INTO frame_particle_cache (job_id, frame, particle_data)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE particle_data = VALUES(particle_data)
            """,
            (job_id, frame, data_json),
            unsafe=True,
        )

    async def get_cached_frame(self, job_id: int, frame: int) -> list[dict] | None:
        """Retrieve cached frame data, if available."""
        rows = await self.db.fetch_all(
            "SELECT particle_data FROM frame_particle_cache WHERE job_id = %s AND frame = %s",
            (job_id, frame),
        )
        if rows:
            return json.loads(rows[0]["particle_data"])
        return None

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------

    async def _last_insert_id(self) -> int:
        """Fetch last auto-increment ID."""
        rows = await self.db.fetch_all("SELECT LAST_INSERT_ID()")
        if rows:
            return rows[0]["LAST_INSERT_ID()"]
        raise RuntimeError("Could not retrieve last insert ID")

    # --------------------------------------------------------------------------
    # Frame Management (for render loop)
    # --------------------------------------------------------------------------

    async def insert_frames(self, job_id: int, num_frames: int) -> None:
        """Insert placeholder rows for frames."""
        for frame_num in range(1, num_frames + 1):
            insert = IRInsert(
                table="frames",
                values={
                    "job_id": job_id,
                    "frame_id": frame_num,
                    "status": "pending",
                },
            )
            await self.db.execute_ir(insert)

    async def get_next_pending_frame(self, job_id: int) -> dict[str, Any] | None:
        """Fetch the next pending frame for a job."""
        select = IRSelect(
            table="frames",
            where=LogicalExpression(
                operator="AND",
                conditions=[
                    Condition("job_id", "=", job_id),
                    Condition("status", "=", "pending"),
                ],
            ),
            limit=1,
        )
        rows = await self.db.fetch_all_ir(select)
        return rows[0] if rows else None

    async def update_frame_status(self, frame_id: int, status: str) -> None:
        """Update frame status."""
        update = IRUpdate(
            table="frames",
            set_values={"status": status},
            where=Condition("frame_id", "=", frame_id),
        )
        await self.db.execute_ir(update)

    async def get_total_frames(self, job_id: int) -> int:
        """Return total frame count for a job."""
        rows = await self.db.fetch_all(
            "SELECT COUNT(*) as total FROM frames WHERE job_id = %s",
            (job_id,),
        )
        return rows[0]["total"] if rows else 0
