# src/sim/validator.py
"""Physics validation and metrics computation for fountain simulation.

This module provides pure functions (no I/O) to:
- Validate individual particle states (NaN, Inf, bounds)
- Compute aggregate metrics (energy, momentum, etc.)
- Detect anomalies (spikes, divergence)
"""

from typing import Any

import numpy as np


class PhysicsValidator:
    """Pure physics validation for a frame (list of particle states).

    No database, no I/O - purely mathematical checks.
    """

    @staticmethod
    def validate_particle_state(state: dict[str, Any]) -> tuple[bool, list[str]]:
        """Check a single particle state for physical correctness.

        Returns:
            (is_valid, errors)
        """
        errors = []

        required = [
            "particle_id", "position_x", "position_y", "position_z",
            "velocity_x", "velocity_y", "velocity_z", "size", "texture_name"
        ]
        for key in required:
            if key not in state:
                errors.append(f"Missing key: {key}")
                return False, errors

        numeric_keys = [
            "position_x", "position_y", "position_z",
            "velocity_x", "velocity_y", "velocity_z", "size"
        ]
        for key in numeric_keys:
            val = state[key]
            if not np.isfinite(val):
                errors.append(f"{key} is not finite: {val}")
            if np.isnan(val):
                errors.append(f"{key} is NaN")
            if np.isinf(val):
                errors.append(f"{key} is Inf")

        v2 = (state["velocity_x"]**2 + state["velocity_y"]**2 + state["velocity_z"]**2)
        if v2 > 1e6:  # 1000 m/s limit
            errors.append(f"Velocity magnitude too high: {np.sqrt(v2)} m/s")

        if state["size"] <= 0:
            errors.append(f"Size must be positive: {state['size']}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_frame(particles: list[dict[str, Any]]) -> tuple[bool, list[dict]]:
        """Validate all particles in a frame.

        Returns:
            (all_valid, per_particle_errors)
        """
        all_valid = True
        errors = []
        for idx, p in enumerate(particles):
            valid, errs = PhysicsValidator.validate_particle_state(p)
            if not valid:
                all_valid = False
                errors.append({
                    "particle_index": idx,
                    "particle_id": p.get("particle_id", -1),
                    "errors": errs
                })
        return all_valid, errors

    @staticmethod
    def compute_metrics(particles: list[dict[str, Any]], gravity: float = 9.81) -> dict[str, Any]:
        """Compute aggregate physics metrics for a frame.

        Returns dictionary with:
            - particle_count
            - min_x, max_x, min_y, max_y, min_z, max_z
            - avg_velocity, max_velocity, velocity_std
            - kinetic_energy, potential_energy, total_energy
            - momentum_x, momentum_y, momentum_z
            - nan_count, inf_count
            - center_of_mass_x, y, z
        """
        if not particles:
            return {
                "particle_count": 0,
                "nan_count": 0,
                "inf_count": 0,
                "kinetic_energy": 0.0,
                "potential_energy": 0.0,
                "total_energy": 0.0,
                "momentum_x": 0.0, "momentum_y": 0.0, "momentum_z": 0.0,
                "avg_velocity": 0.0, "max_velocity": 0.0,
            }

        pos = np.array([[p["position_x"], p["position_y"], p["position_z"]] for p in particles])
        vel = np.array([[p["velocity_x"], p["velocity_y"], p["velocity_z"]] for p in particles])
        sizes = np.array([p["size"] for p in particles])

        nan_count = int(np.isnan(pos).sum() + np.isnan(vel).sum())
        inf_count = int(np.isinf(pos).sum() + np.isinf(vel).sum())

        speed2 = np.sum(vel**2, axis=1)
        speed = np.sqrt(speed2)

        mass = sizes
        ke = 0.5 * np.sum(mass * speed2)
        pe = np.sum(mass * gravity * pos[:, 1])
        total_energy = ke + pe
        momentum = np.sum(mass[:, np.newaxis] * vel, axis=0)

        total_mass = np.sum(mass)
        if total_mass > 0:
            com = np.sum(pos * mass[:, np.newaxis], axis=0) / total_mass
        else:
            com = np.array([0, 0, 0])

        return {
            "particle_count": len(particles),
            "min_x": float(pos[:, 0].min()),
            "max_x": float(pos[:, 0].max()),
            "min_y": float(pos[:, 1].min()),
            "max_y": float(pos[:, 1].max()),
            "min_z": float(pos[:, 2].min()),
            "max_z": float(pos[:, 2].max()),
            "avg_velocity": float(np.mean(speed)),
            "max_velocity": float(np.max(speed)),
            "velocity_std": float(np.std(speed)),
            "kinetic_energy": float(ke),
            "potential_energy": float(pe),
            "total_energy": float(total_energy),
            "momentum_x": float(momentum[0]),
            "momentum_y": float(momentum[1]),
            "momentum_z": float(momentum[2]),
            "center_of_mass_x": float(com[0]),
            "center_of_mass_y": float(com[1]),
            "center_of_mass_z": float(com[2]),
            "nan_count": nan_count,
            "inf_count": inf_count,
        }

    @staticmethod
    def detect_energy_spike(
        metrics_series: list[dict[str, Any]],
        threshold_factor: float = 10.0
    ) -> list[int]:
        """Detect frames where total_energy spikes relative to moving average.

        Returns list of frame indices (or times) that exceeded threshold.
        """
        if not metrics_series:
            return []
        energies = [m["total_energy"] for m in metrics_series]
        if len(energies) < 3:
            return []
        spikes = []
        for i in range(1, len(energies) - 1):
            # Use average of neighbours, not including the current point
            avg_neighbors = (energies[i - 1] + energies[i + 1]) / 2.0
            if avg_neighbors > 0:
                if energies[i] > avg_neighbors * threshold_factor:
                    spikes.append(i)
            else:
                # If neighbours average is zero, any positive spike is infinite ratio
                if energies[i] > 0:
                    spikes.append(i)
        return spikes
