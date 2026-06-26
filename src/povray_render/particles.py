# src/povray_render/particles.py
"""Particle generation and simulation module for fountain, fire, and rain effects."""

import random
from typing import Any, Optional

import numpy as np


class ParticleGenerator:
    """
    A class for generating different types of particle simulations, including conical fountain sprays,
    fire particles, and rain.

    Attributes:
        particles (list): A list to store generated particle dictionaries.
            - key: 'particle_id' (int) unique ID
            - key: 'position' (list of 3 floats) [x, y, z] position of particle
            - key: 'velocity' (list of 3 floats) [vx, vy, vz] velocity of particle
            - key: 'size' (float) size of particle
            - key: 'texture' (str) texture name (e.g., "WaterTexture", "FireTexture")

    Methods:
        generate_conical_fountain: Generates particles in a conical fountain spray pattern.
        generate_fire_particles: Generates particles simulating fire in a brazier or similar setting.
        generate_rain: Generates raindrops with Gaussian size distribution.
        plot_particles_at_frame: Calculates particle positions at a given frame considering gravity.
        clear_particles: Clears the particle list.
        generate_waterdrop_sizes: Generates raindrop sizes based on POV‑Ray formula.
    """

    def __init__(self, gravity: float = 9.81):
        """
        Initialises the ParticleGenerator class.

        Args:
            gravity (float): Acceleration due to gravity (m/s²). Default 9.81.
        """
        self.particles: list[dict[str, Any]] = []
        self.gravity = gravity

    @staticmethod
    def _vlength(v: np.ndarray) -> float:
        """
        Computes the magnitude (length) of a vector and returns a Python float.

        Args:
            v (np.ndarray): Input vector (1D array).

        Returns:
            float: Magnitude of the vector.
        """
        if v.ndim == 1:
            v = v.reshape(1, -1)
        return float(np.sqrt(np.sum(v**2, axis=1))[0])

    def clear_particles(self) -> None:
        """Clears the list of particles."""
        self.particles = []

    # ------------------------------------------------------------------
    #  Rain
    # ------------------------------------------------------------------

    def generate_rain(
        self,
        num_drops: int,
        mean: float = 0.0015,
        std_dev: float = 0.0005,
        min_size: float = 0.0005,
        max_size: float = 0.004,
        wind_direction: list[float] = [1.0, 0.0, 0.0],
        wind_velocity: float = 5.0,
        texture: str = "WaterTexture",
    ) -> None:
        """
        Generates raindrops using a Gaussian distribution for size, and assigns random positions and velocities.

        Args:
            num_drops (int): Number of raindrops to generate.
            mean (float): Mean size of raindrops in meters.
            std_dev (float): Standard deviation for raindrop size.
            min_size (float): Minimum raindrop size in meters.
            max_size (float): Maximum raindrop size in meters.
            wind_direction (list[float]): Wind direction vector [x, y, z].
            wind_velocity (float): Wind speed (m/s).
            texture (str): Texture name to apply to the raindrops.
        """
        # Generate raindrop sizes using a Gaussian distribution
        raindrop_sizes = np.random.normal(loc=mean, scale=std_dev, size=num_drops)
        raindrop_sizes = np.clip(raindrop_sizes, min_size, max_size)

        for i in range(num_drops):
            # Random position in the sky
            x = random.uniform(-10, 10)
            y = random.uniform(5, 20)
            z = random.uniform(-10, 10)

            # Initial velocity: wind in x/z, falling in y
            velocity_x = wind_velocity * wind_direction[0]
            velocity_y = -9.8
            velocity_z = wind_velocity * wind_direction[2]

            size = float(raindrop_sizes[i])

            self.particles.append({
                'particle_id': i + 1,
                'position': [x, y, z],
                'velocity': [velocity_x, velocity_y, velocity_z],
                'size': size,
                'texture': texture,
            })

    # ------------------------------------------------------------------
    #  Conical Fountain
    # ------------------------------------------------------------------

    def generate_conical_fountain(
        self,
        num_particles: int,
        apex_position: list[float],
        cone_height: float,
        cone_angle: float,
        base_radius: float,
        wind_direction: list[float],
        wind_velocity: float,
        texture: str = "WaterTexture",
        drop_sizes: Optional[np.ndarray] = None,
    ) -> None:
        """
        Generates particles in a conical fountain spray pattern.

        Args:
            num_particles (int): The number of particles to generate.
            apex_position (list[float]): The [x, y, z] coordinates of the cone's apex.
            cone_height (float): The height of the cone from apex to base.
            cone_angle (float): The spread angle of the particles in radians.
            base_radius (float): The radius of the base of the cone.
            wind_direction (list[float]): A [x, y, z] vector representing the wind direction.
            wind_velocity (float): The velocity of the wind affecting the particles.
            texture (str): Texture name to apply to the particles.
            drop_sizes (Optional[np.ndarray]): Pre‑computed drop sizes. If None, new sizes are generated.
        """
        if drop_sizes is None:
            drop_sizes = self.generate_waterdrop_sizes(num_particles, water_size=0.02)

        for i in range(num_particles):
            height = random.uniform(0, cone_height)
            angle = random.uniform(0, 2 * np.pi)  # Angle around the cone
            radius = random.uniform(0, base_radius) * (1 - height / cone_height)

            x = apex_position[0] + radius * np.cos(angle)
            y = apex_position[1] + height
            z = apex_position[2] + radius * np.sin(angle)

            # Random initial velocity within the cone
            velocity_angle = random.uniform(-cone_angle, cone_angle)
            velocity_magnitude = random.uniform(5, 10)

            velocity_x = velocity_magnitude * np.cos(velocity_angle) * np.cos(angle)
            velocity_y = velocity_magnitude * np.sin(velocity_angle)
            velocity_z = velocity_magnitude * np.cos(velocity_angle) * np.sin(angle)

            # Apply wind
            velocity_x += wind_velocity * wind_direction[0]
            velocity_y += wind_velocity * wind_direction[1]
            velocity_z += wind_velocity * wind_direction[2]

            size = float(drop_sizes[i])

            self.particles.append({
                'particle_id': i + 1,
                'position': [float(x), float(y), float(z)],
                'velocity': [float(velocity_x), float(velocity_y), float(velocity_z)],
                'size': size,
                'texture': texture,
            })

    # ------------------------------------------------------------------
    #  Fire
    # ------------------------------------------------------------------

    def generate_fire_particles(
        self,
        base_position: list[float],
        num_particles: int,
        texture: str = "FireTexture",
    ) -> None:
        """
        Generates particles simulating fire, with upward velocity and random positions around the base.

        Args:
            base_position (list[float]): The [x, y, z] coordinates representing the centre of the fire.
            num_particles (int): The number of fire particles to generate.
            texture (str): Texture name to apply to the particles.
        """
        for i in range(num_particles):
            position = [
                base_position[0] + random.uniform(-0.1, 0.1),
                base_position[1],
                base_position[2] + random.uniform(-0.1, 0.1),
            ]
            velocity = [
                random.uniform(-0.2, 0.2),
                random.uniform(1.0, 3.0),
                random.uniform(-0.2, 0.2),
            ]
            size = random.uniform(0.05, 0.15)

            self.particles.append({
                'particle_id': i + 1,
                'position': position,
                'velocity': velocity,
                'size': size,
                'texture': texture,
            })

    # ------------------------------------------------------------------
    #  Plotting / Frame Simulation
    # ------------------------------------------------------------------

    def plot_particles_at_frame(
        self,
        frame_number: int,
        frame_rate: float,
        water_size: float = 0.02,
        water_sizeturb: float = 0.2,
        water_falloff: float = 1.0,
        water_stretch: float = 0.1,
    ) -> list[dict[str, Any]]:
        """
        Calculates the positions of particles at a given frame, considering gravity.

        Args:
            frame_number (int): The frame number (F) to calculate particle positions.
            frame_rate (float): The frame rate of the simulation in frames per second (fps).
            water_size (float): Base size of the raindrops (in meters).
            water_sizeturb (float): Turbulence factor for size variation.
            water_falloff (float): Falloff factor for reducing size based on raindrop state.
            water_stretch (float): Stretch factor applied based on velocity magnitude.

        Returns:
            list: A list of updated particle dictionaries, each containing:
                - particle_id (int)
                - position (list[float, float, float])
                - size (float)
                - velocity (list[float, float, float])
                - texture (str)
        """
        time_elapsed = frame_number / frame_rate
        updated_particles = []

        for particle in self.particles:
            initial_position = np.array(particle['position'])
            velocity = np.array(particle['velocity'])

            # Linear motion in x/z
            new_x = initial_position[0] + velocity[0] * time_elapsed
            new_z = initial_position[2] + velocity[2] * time_elapsed

            # Gravity in y
            initial_y = initial_position[1]
            velocity_y = velocity[1]
            new_y = initial_y + velocity_y * time_elapsed - 0.5 * self.gravity * (time_elapsed ** 2)
            new_y = max(new_y, 0.0)

            # Compute velocity magnitude (scalar)
            velocity_magnitude = self._vlength(velocity)

            # Apply size scaling
            scale = (
                water_size
                * (1 + (np.random.random() - 0.5) * 2 * water_sizeturb)
                * (0.001 + 0.999 * np.power(1 - np.random.random(), water_falloff))
            )
            scale += velocity_magnitude * water_stretch
            scale = float(scale)

            updated_particles.append({
                'particle_id': particle['particle_id'],
                'position': [float(new_x), float(new_y), float(new_z)],
                'size': scale,
                'velocity': velocity.tolist(),  # convert to list for JSON compatibility
                'texture': particle['texture'],
            })

        return updated_particles

    # ------------------------------------------------------------------
    #  Waterdrop Size Generation
    # ------------------------------------------------------------------

    def generate_waterdrop_sizes(
        self,
        num_particles: int,
        water_size: float = 1.0,
        water_sizeturb: float = 0.0,
        water_falloff: float = 0.0,
    ) -> np.ndarray:
        """
        Generates raindrop sizes based on the POV‑Ray formula.

        Args:
            num_particles (int): Number of particles (raindrops) to generate.
            water_size (float): Base size of the raindrops (in meters).
            water_sizeturb (float): Turbulence factor for size variation.
            water_falloff (float): Falloff factor for reducing size based on raindrop state.

        Returns:
            np.ndarray: Array of raindrop sizes (in meters).
        """
        p_random = np.random.random(size=num_particles)
        p_state = np.random.random(size=num_particles)

        _scale = (
            water_size
            * (1 + (p_random - 0.5) * 2 * water_sizeturb)
            * (0.001 + 0.999 * np.power(1 - p_state, water_falloff))
        )
        return _scale