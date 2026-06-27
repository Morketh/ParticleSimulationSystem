#!/usr/bin/env python3
# src/insert_preset.py

"""Insert or update a texture preset from JSON into the database.

The JSON must contain:
- texture_name (required)
- preset_name (required)
- parameters (dict with PBR values)
  - pigment_r, pigment_g, pigment_b, pigment_t
  - ambient, diffuse, reflection, specular, roughness

If the texture does not exist, it will be created.
If the preset already exists, it will be updated.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from DBCore import create_database_provider
from dotenv import load_dotenv

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
    """Read JSON from stdin or file and insert preset."""
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

    # Read JSON
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        with open(file_path) as f:
            data = json.load(f)
    else:
        # stdin: read entire content and parse as JSON
        content = sys.stdin.read()
        data = json.loads(content)

    # Support both single object and array
    if isinstance(data, dict):
        data = [data]

    for entry in data:
        texture_name = entry.get("texture_name")
        preset_name = entry.get("preset_name")
        if not texture_name or not preset_name:
            print("Error: Each entry must have 'texture_name' and 'preset_name'.", file=sys.stderr)
            continue

        params = entry.get("parameters", {})
        # Ensure all required keys exist with defaults
        params.setdefault("pigment_r", 1.0)
        params.setdefault("pigment_g", 1.0)
        params.setdefault("pigment_b", 1.0)
        params.setdefault("pigment_t", 0.0)
        params.setdefault("ambient", 0.1)
        params.setdefault("diffuse", 0.9)
        params.setdefault("reflection", 0.0)
        params.setdefault("specular", 0.0)
        params.setdefault("roughness", 0.0)

        try:
            preset_id = await cluster.ensure_preset(texture_name, preset_name, params)
            print(f"Inserted/updated preset '{preset_name}' for texture '{texture_name}' (preset_id={preset_id}).")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            continue

    await db.close()


def main_sync() -> None:
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
