# tests/unit/sim/test_validator.py
"""Unit tests for PhysicsValidator."""

import numpy as np

from sim.validator import PhysicsValidator


def make_particle(x=0.0, y=5.0, z=0.0, vx=0.0, vy=0.0, vz=0.0, size=0.02):
    """Helper to create a valid particle dict."""
    return {
        "particle_id": 1,
        "position_x": x,
        "position_y": y,
        "position_z": z,
        "velocity_x": vx,
        "velocity_y": vy,
        "velocity_z": vz,
        "size": size,
        "texture_name": "WaterTexture",
    }


def test_validate_particle_state_valid():
    """Valid particle passes validation."""
    p = make_particle()
    valid, errors = PhysicsValidator.validate_particle_state(p)
    assert valid is True
    assert errors == []


def test_validate_particle_state_missing_key():
    """Particle missing required key fails."""
    p = {"particle_id": 1}
    valid, errors = PhysicsValidator.validate_particle_state(p)
    assert valid is False
    assert "Missing key: position_x" in errors[0]


def test_validate_particle_state_nan():
    """Particle with NaN position fails."""
    p = make_particle(x=np.nan)
    valid, errors = PhysicsValidator.validate_particle_state(p)
    assert valid is False
    assert any("position_x is NaN" in e for e in errors)


def test_validate_particle_state_inf():
    """Particle with Inf velocity fails."""
    p = make_particle(vy=np.inf)
    valid, errors = PhysicsValidator.validate_particle_state(p)
    assert valid is False
    assert any("velocity_y is Inf" in e for e in errors)


def test_validate_particle_state_negative_size():
    """Particle with negative size fails."""
    p = make_particle(size=-0.02)
    valid, errors = PhysicsValidator.validate_particle_state(p)
    assert valid is False
    assert any("Size must be positive" in e for e in errors)


def test_validate_frame_valid():
    """Frame with valid particles passes."""
    particles = [make_particle(x=1), make_particle(x=2)]
    valid, errors = PhysicsValidator.validate_frame(particles)
    assert valid is True
    assert errors == []


def test_validate_frame_invalid():
    """Frame with an invalid particle reports errors."""
    particles = [make_particle(x=1), make_particle(x=np.nan)]
    valid, errors = PhysicsValidator.validate_frame(particles)
    assert valid is False
    assert len(errors) == 1
    assert errors[0]["particle_id"] == 1
    assert any("position_x is NaN" in e for e in errors[0]["errors"])


def test_compute_metrics_single_particle():
    """Metrics for a single particle are computed correctly."""
    p = make_particle(x=0, y=10, vx=2, vy=3, size=0.02)
    metrics = PhysicsValidator.compute_metrics([p], gravity=9.81)

    expected_ke = 0.5 * 0.02 * (2**2 + 3**2)  # 0.13
    expected_pe = 0.02 * 9.81 * 10             # 1.962
    expected_total = expected_ke + expected_pe

    assert metrics["particle_count"] == 1
    assert metrics["min_y"] == 10.0
    assert metrics["max_y"] == 10.0
    assert abs(metrics["kinetic_energy"] - expected_ke) < 1e-9
    assert abs(metrics["potential_energy"] - expected_pe) < 1e-9
    assert abs(metrics["total_energy"] - expected_total) < 1e-9
    assert abs(metrics["momentum_y"] - 0.02 * 3) < 1e-9
    assert abs(metrics["center_of_mass_x"] - 0.0) < 1e-9
    assert abs(metrics["center_of_mass_y"] - 10.0) < 1e-9
    assert metrics["nan_count"] == 0
    assert metrics["inf_count"] == 0


def test_compute_metrics_multiple_particles():
    """Metrics for multiple particles are summed correctly."""
    p1 = make_particle(x=0, y=10, size=0.02)
    p2 = make_particle(x=2, y=5, size=0.03, vx=1, vy=0)
    metrics = PhysicsValidator.compute_metrics([p1, p2], gravity=9.81)

    assert metrics["particle_count"] == 2
    assert metrics["min_x"] == 0.0
    assert metrics["max_x"] == 2.0
    assert metrics["min_y"] == 5.0
    assert metrics["max_y"] == 10.0

    expected_ke = 0.5 * 0.03 * (1**2)  # 0.015
    expected_pe = 0.02*9.81*10 + 0.03*9.81*5  # 1.962 + 1.4715 = 3.4335
    expected_total = expected_ke + expected_pe
    assert abs(metrics["kinetic_energy"] - expected_ke) < 1e-9
    assert abs(metrics["potential_energy"] - expected_pe) < 1e-9
    assert abs(metrics["total_energy"] - expected_total) < 1e-9

    assert abs(metrics["momentum_x"] - 0.03*1) < 1e-9
    assert abs(metrics["momentum_y"]) < 1e-9
    assert abs(metrics["momentum_z"]) < 1e-9

    com_x = (0*0.02 + 2*0.03) / 0.05
    com_y = (10*0.02 + 5*0.03) / 0.05
    assert abs(metrics["center_of_mass_x"] - com_x) < 1e-9
    assert abs(metrics["center_of_mass_y"] - com_y) < 1e-9


def test_compute_metrics_empty():
    """Empty particle list returns zeros."""
    metrics = PhysicsValidator.compute_metrics([], gravity=9.81)
    assert metrics["particle_count"] == 0
    assert metrics["nan_count"] == 0
    assert metrics["inf_count"] == 0
    assert metrics["kinetic_energy"] == 0.0


def test_compute_metrics_nan_handling():
    """NaN positions are counted correctly."""
    p = make_particle(x=np.nan)
    metrics = PhysicsValidator.compute_metrics([p], gravity=9.81)
    assert metrics["nan_count"] == 1
    assert np.isnan(metrics["min_x"])


def test_detect_energy_spike():
    """Spike detection works with neighbours' average."""
    series = [{"total_energy": 1.0} for _ in range(10)]
    spikes = PhysicsValidator.detect_energy_spike(series, threshold_factor=10.0)
    assert spikes == []

    # Spike at index 5 (0-based) with value 100, neighbours average ~1
    series[5] = {"total_energy": 100.0}
    spikes = PhysicsValidator.detect_energy_spike(series, threshold_factor=10.0)
    # Should detect index 5 because 100 > 1*10
    assert spikes == [5]
