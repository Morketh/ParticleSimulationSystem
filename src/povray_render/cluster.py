# src/povray_render/cluster.py
"""ClusterManager for distributed POV-Ray rendering, powered by DBCore IR."""

import socket
from typing import Any, Optional

import psutil
from DBCore.base import DatabaseProvider
from DBCore.ir import IRBulkInsert, IRDelete, IRInsert, IRSelect, IRUpdate, LogicalExpression
from DBCore.ir.conditions import Condition


class ClusterManager:
    """
    Manages the render cluster database operations using DBCore IR.
    Replaces MySQLdb with async DBCore methods.
    """

    def __init__(self, db: DatabaseProvider):
        """
        Args:
            db: Initialized DBCore DatabaseProvider (e.g., MariaDB, SQLite).
        """
        self.db = db

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    async def _last_insert_id(self) -> int:
        """Fetch the last auto‑increment ID using raw SQL."""
        res, _ = await self.db.execute_raw("SELECT LAST_INSERT_ID()", unsafe=True)
        if res and len(res) > 0:
            return res[0]["LAST_INSERT_ID()"]
        raise RuntimeError("Could not retrieve last insert ID")

    # ------------------------------------------------------------------
    #  Jobs
    # ------------------------------------------------------------------

    async def create_job(
        self,
        job_name: str,
        num_frames: int,
        res_x: int,
        res_y: int,
        fps: int,
        quality: int,
        antialias: str,
        antialias_depth: int,
        antialias_threshold: float,
        sampling_method: int,
    ) -> int:
        """Create a new render job and return its job_id."""
        insert = IRInsert(
            table="render_jobs",
            values={
                "job_name": job_name,
                "total_frames": num_frames,
                "width": res_x,
                "height": res_y,
                "fps": fps,
                "quality": quality,
                "antialias": antialias,
                "antialias_depth": antialias_depth,
                "antialias_threshold": antialias_threshold,
                "sampling_method": sampling_method,
                "status": "pending",
            },
        )
        await self.db.execute_ir(insert)
        return await self._last_insert_id()

    async def get_job(self, query: str) -> list[dict[str, Any]]:
        """
        Execute an arbitrary SELECT query (use only when IR can't express it).
        Returns a list of dicts.
        """
        res, _ = await self.db.execute_raw(query, unsafe=True)
        return res

    async def get_total_frames(self, job_id: int) -> int:
        """Return total frame count for a job."""
        select = IRSelect(
            table="frames",
            columns=["COUNT(*) as total"],
            where=Condition("job_id", "=", job_id),
        )
        rows = await self.db.fetch_all_ir(select)
        return rows[0]["total"] if rows else 0

    async def update_job_status(self, job_id: int, status: str) -> None:
        """Update the job status."""
        update = IRUpdate(
            table="render_jobs",
            set_values={"status": status},
            where=Condition("job_id", "=", job_id),
        )
        await self.db.execute_ir(update)

    # ------------------------------------------------------------------
    #  Frames
    # ------------------------------------------------------------------

    async def insert_frames(self, job_id: int, num_frames: int) -> None:
        """Insert multiple frames for a job (one row per frame)."""
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

    async def get_next_frame(self, job_id: int) -> Optional[dict[str, Any]]:
        """Fetch the first pending frame for a job."""
        select = IRSelect(
            table="frames",
            where=LogicalExpression(
                operator="AND",
                conditions=[
                    Condition("job_id", "=", job_id),
                    Condition("status", "=", "pending"),
                ]
            ),
            limit=1,
        )
        rows = await self.db.fetch_all_ir(select)
        return rows[0] if rows else None
    
    async def get_active_render_nodes(self) -> list[dict[str, Any]]:
        """Fetch all active render nodes."""
        select = IRSelect(
            table="nodes",
            where=LogicalExpression(
                operator="AND",
                conditions=[
                    Condition("role", "=", "render"),
                    Condition("status", "=", "active"),
                ]
            ),
        )
        return await self.db.fetch_all_ir(select)

    async def update_frame_status(self, frame_id: int, status: str) -> None:
        """Update the status of a specific frame."""
        update = IRUpdate(
            table="frames",
            set_values={"status": status},
            where=Condition("frame_id", "=", frame_id),
        )
        await self.db.execute_ir(update)

    async def fetch_frame_by_job(self, job_id: int) -> list[dict[str, Any]]:
        """Fetch all frames for a job (with all columns)."""
        select = IRSelect(table="frames", where=Condition("job_id", "=", job_id))
        return await self.db.fetch_all_ir(select)

    # ------------------------------------------------------------------
    #  Particles
    # ------------------------------------------------------------------

    async def insert_particle_data(
        self,
        job_id: int,
        frame_id: int,
        particle_data: list[dict],
    ) -> None:
        """
        Insert many particles for a frame using bulk insert.

        particle_data: list of dicts with keys:
            particle_id, position (list of 3 floats), velocity (list of 3 floats),
            size, texture (string name)
        """
        # First, map texture names to texture_id
        texture_map = await self._get_texture_id_map()
        rows = []
        for p in particle_data:
            tex_name = p.get("texture", "WaterTexture")  # fallback
            tex_id = texture_map.get(tex_name)
            if tex_id is None:
                # Texture not found – you may want to insert it, but we'll skip.
                # For safety, raise or use a default.
                tex_id = 1  # default, or you could auto‑create
            rows.append(
                [
                    p["particle_id"],
                    frame_id,
                    job_id,
                    p["position"][0],
                    p["position"][1],
                    p["position"][2],
                    p["velocity"][0],
                    p["velocity"][1],
                    p["velocity"][2],
                    p["size"],
                    tex_id,
                ]
            )

        if not rows:
            return

        bulk = IRBulkInsert(
            table="particles",
            columns=[
                "particle_id",
                "frame_id",
                "job_id",
                "position_x",
                "position_y",
                "position_z",
                "velocity_x",
                "velocity_y",
                "velocity_z",
                "size",
                "texture_id",
            ],
            values=rows,
        )
        await self.db.bulk_insert_ir(bulk)

    async def _get_texture_id_map(self) -> dict[str, int]:
        """Fetch all texture_name -> texture_id mappings."""
        select = IRSelect(table="textures", columns=["texture_id", "texture_name"])
        rows = await self.db.fetch_all_ir(select)
        return {row["texture_name"]: row["texture_id"] for row in rows}

    async def get_particles(
        self,
        job_id: int,
        frame_id: int,
        texture_id: int,
    ) -> list[dict[str, Any]]:
        """
        Fetch particles for a given job, frame, and texture.
        Uses a join with textures, executed via raw SQL because IR cannot join yet.
        """
        sql = """
            SELECT p.particle_id, p.position_x, p.position_y, p.position_z,
                   p.size, t.texture_name
            FROM particles p
            LEFT JOIN textures t ON p.texture_id = t.texture_id
            WHERE p.frame_id = %s AND p.job_id = %s AND t.texture_id = %s
        """
        params = (frame_id, job_id, texture_id)
        res, _ = await self.db.execute_raw(sql, params, unsafe=True)
        return res

    async def get_textures(self) -> list[dict[str, Any]]:
        """Fetch all textures."""
        select = IRSelect(table="textures")
        return await self.db.fetch_all_ir(select)

    # ------------------------------------------------------------------
    #  Nodes
    # ------------------------------------------------------------------

    @staticmethod
    def get_node_info() -> tuple[str, str, int, float]:
        """Gather local system info."""
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        cpu_cores = psutil.cpu_count(logical=True)
        memory_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        return hostname, ip_address, cpu_cores, memory_gb

    async def insert_node_info(self, status: str = "active", role: str = "render") -> None:
        """Insert or update node info."""
        hostname, ip_address, cpu_cores, memory_gb = self.get_node_info()
        # Check if node already exists (by hostname) – update or insert.
        select = IRSelect(
            table="nodes",
            where=Condition("node_name", "=", hostname),
        )
        existing = await self.db.fetch_all_ir(select)
        if existing:
            # Update
            update = IRUpdate(
                table="nodes",
                set_values={
                    "ip_address": ip_address,
                    "cpu_cores": cpu_cores,
                    "memory_gb": memory_gb,
                    "status": status,
                    "role": role,
                },
                where=Condition("node_name", "=", hostname),
            )
            await self.db.execute_ir(update)
        else:
            insert = IRInsert(
                table="nodes",
                values={
                    "node_name": hostname,
                    "ip_address": ip_address,
                    "cpu_cores": cpu_cores,
                    "memory_gb": memory_gb,
                    "status": status,
                    "role": role,
                },
            )
            await self.db.execute_ir(insert)

    async def get_all_node_info(self) -> list[dict[str, Any]]:
        """Fetch ip_address, cpu_cores, memory_gb for all nodes."""
        select = IRSelect(
            table="nodes",
            columns=["ip_address", "cpu_cores", "memory_gb"],
        )
        return await self.db.fetch_all_ir(select)

    # ------------------------------------------------------------------
    #  Work Threads
    # ------------------------------------------------------------------

    async def create_work_threads(self, job_id: int, frame_ids: list[int], node_id: int) -> None:
        """Assign frames to a node as work threads."""
        # Use bulk insert for efficiency
        rows = [[node_id, job_id, fid, "queued"] for fid in frame_ids]
        if rows:
            bulk = IRBulkInsert(
                table="work_threads",
                columns=["node_id", "job_id", "frame_id", "status"],
                values=rows,
            )
            await self.db.bulk_insert_ir(bulk)

    # ------------------------------------------------------------------
    #  Connection (no‑op – handled by provider)
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """No‑op: provider is already initialised."""
        pass

    async def disconnect(self) -> None:
        """No‑op: provider closing is handled by the caller."""
        pass