import random
import numpy as np


class ParticleGenerator:
    """
    A class for generating different types of particle simulations, including conical fountain sprays
    and fire particles.

    Attributes:
        particles (list): A list to store generated particle dictionaries.
            - key: 'position' [x,y,z] position of particle
            - key: 'velocity' [x,y,z] velocity of particle
            - key: 'size' (float) size of particle
            - key: 'texture' (str) texture of particle. (each method has a default)

    Methods:
    - generate_conical_fountain: Generates particles in a conical fountain spray pattern.
    - generate_fire_particles: Generates particles simulating fire in a brazier or similar setting.
    - clear_particles: Clears the particle list.
    """

    def __init__(self, gravity=9.81):
        """
        Initializes the ParticleGenerator class with an empty particle list.
        """
        self.particles = []
        self.gravity = gravity

    def __vlength(self, v):
        """Computes the magnitude (length) of a vector."""
        if v.ndim == 1:
            v = np.array([v])
        return np.sqrt(np.sum(v**2, axis=1))
    
    def clear_particles(self):
        """
        Clears the list of particles.
        """
        self.particles = []

    def generate_rain(self, num_drops, mean=0.0015, std_dev=0.0005, min_size=0.0005, max_size=0.004,
                      wind_direction=[1, 0, 0], wind_velocity=5.0, texture="WaterTexture"):
        """
        Generates raindrops using a Gaussian distribution for size, and assigns random positions and velocities.

        Args:
            num_drops (int): Number of raindrops to generate.
            mean (float): Mean size of raindrops in mm.
            std_dev (float): Standard deviation for raindrop size.
            min_size (float): Minimum raindrop size in mm.
            max_size (float): Maximum raindrop size in mm.
            texture (str): Texture to apply to the raindrops (default: "WaterTexture").

        """
        # Generate raindrop sizes using a Gaussian distribution
        raindrop_sizes = np.random.normal(loc=mean, scale=std_dev, size=num_drops)
        raindrop_sizes = np.clip(raindrop_sizes, min_size, max_size)

        for i in range(num_drops):
            # Random position in the sky, e.g., x, y, z ranges
            x = random.uniform(-10, 10)  # Adjust ranges as needed
            y = random.uniform(5, 20)    # Heights for raindrops to fall from
            z = random.uniform(-10, 10)

            # Initial velocity, assuming raindrops fall vertically
            velocity_x = wind_velocity * wind_direction[0]
            velocity_y = -9.8
            velocity_z = wind_velocity * wind_direction[2]

            # Get the size of the raindrop
            size = raindrop_sizes[i]

            # Append the particle data to self.particles list
            self.particles.append({
                'particle_id': i + 1,
                'position': [x, y, z],
                'velocity': [velocity_x, velocity_y, velocity_z],
                'size': size,
                'texture': texture
            })

    def generate_conical_fountain(self, num_particles, apex_position, cone_height,
                                  cone_angle, base_radius, wind_direction,
                                  wind_velocity, texture="WaterTexture", drop_sizes=None):
        """
        Generates particles in a conical fountain spray pattern.

        Args:
            num_particles (int): The number of particles to generate.
            apex_position (list of float): The [x, y, z] coordinates of the cone's apex.
            cone_height (float): The height of the cone from apex to base.
            cone_angle (float): The spread angle of the particles in radians.
            base_radius (float): The radius of the base of the cone.
            wind_direction (list of float): A [x, y, z] vector representing the wind direction.
            wind_velocity (float): The velocity of the wind affecting the particles.
            texture (str, optional): The texture or material to apply to the particles. Defaults to "WaterTexture".
        """
        if drop_sizes is None:
            drop_sizes = self.generate_waterdrop_sizes(num_particles, water_size=0.02)

        for i in range(num_particles):
            height = random.uniform(0, cone_height)
            angle = random.uniform(0, 2 * np.pi)  # Angle around the cone
            radius = random.uniform(0, base_radius) * (1 - height / cone_height)

            # Calculate the position using polar coordinates
            x = apex_position[0] + radius * np.cos(angle)
            y = apex_position[1] + height
            z = apex_position[2] + radius * np.sin(angle)

            # Random initial velocity within the cone
            velocity_angle = random.uniform(-cone_angle, cone_angle)
            velocity_magnitude = random.uniform(5, 10)

            # Calculate velocity components based on angle
            velocity_x = velocity_magnitude * np.cos(velocity_angle) * np.cos(angle)
            velocity_y = velocity_magnitude * np.sin(velocity_angle)
            velocity_z = velocity_magnitude * np.cos(velocity_angle) * np.sin(angle)

            # Apply wind effect to the particle's velocity
            velocity_x += wind_velocity * wind_direction[0]
            velocity_y += wind_velocity * wind_direction[1]
            velocity_z += wind_velocity * wind_direction[2]

            # Random particle size and texture
            size = drop_sizes[i]

            self.particles.append({
                'particle_id': i+1,
                'position': [x, y, z],
                'velocity': [velocity_x, velocity_y, velocity_z],
                'size': size,
                'texture': texture
            })

    def generate_fire_particles(self, base_position, num_particles, texture="FireTexture"):
        """
        Generates particles simulating fire, with upward velocity and random positions around the base.

        Args:
            base_position (list of float): The [x, y, z] coordinates representing the center of the fire.
            num_particles (int): The number of fire particles to generate.
            texture (str, optional): The texture or material to apply to the particles. Defaults to "FireTexture".
        """
        for i in range(num_particles):
            # Randomly generate initial position near the base of the brazier
            position = [
                base_position[0] + random.uniform(-0.1, 0.1),
                base_position[1],
                base_position[2] + random.uniform(-0.1, 0.1)
            ]
            # Random upward motion
            velocity = [
                random.uniform(-0.2, 0.2),
                random.uniform(1.0, 3.0),
                random.uniform(-0.2, 0.2)
            ]
            # Random particle size
            size = random.uniform(0.05, 0.15)

            self.particles.append({
                'particle_id': i+1,
                'position': position,
                'velocity': velocity,
                'size': size,
                'texture': texture
            })

    def plot_particles_at_frame(self, frame_number, frame_rate, water_size=0.02, water_sizeturb=0.2, water_falloff=1.0, water_stretch=0.1):
        """
        Plots the positions of particles at a given frame, considering gravity.
        
        Args:
            frame_number (int): The frame number (F) to calculate particle positions.
            frame_rate (float): The frame rate of the simulation in frames per second (fps).
            water_size (float): Base size of the raindrops (in meters).
            water_sizeturb (float): Turbulence factor for size variation.
            water_falloff (float): Falloff factor for reducing size based on raindrop state.
            water_stretch (float): Stretch factor applied based on velocity magnitude.

        Returns:
            list: A list of updated particle positions at frame F.
        """
        # Calculate the time corresponding to the frame
        time_elapsed = frame_number / frame_rate

        updated_particles = []

        for particle in self.particles:
            initial_position = np.array(particle['position'])
            velocity = np.array(particle['velocity'])

            # Update the x, z positions with simple linear motion
            new_x = initial_position[0] + velocity[0] * time_elapsed
            new_z = initial_position[2] + velocity[2] * time_elapsed

            # Update the y position considering gravity
            initial_y = initial_position[1]
            velocity_y = velocity[1]
            new_y = initial_y + velocity_y * time_elapsed - 0.5 * self.gravity * (time_elapsed ** 2)

            # Prevent particles from falling below ground level (y >= 0)
            new_y = max(new_y, 0)

            # Calculate the magnitude of the velocity vector
            velocity_magnitude = self.__vlength(velocity)

            # Apply scaling based on the water size parameters
            # Base size and turbulence
            scale = (water_size 
                     * (1 + (np.random.random() - 0.5) * 2 * water_sizeturb)
                     * (0.001 + 0.999 * np.power(1 - np.random.random(), water_falloff))
                    )

            # Apply stretch based on the velocity magnitude
            scale += velocity_magnitude * water_stretch

            updated_particles.append({
                'particle_id': particle['particle_id'],
                'position': [new_x, new_y, new_z],
                'size': float(scale),  # Updated size based on velocity and parameters
                'velocity': velocity,
                'texture': particle['texture']
            })

        return updated_particles
    
    def generate_waterdrop_sizes(self, num_particles, water_size=1.0, water_sizeturb=0.0, water_falloff=0.0):
        """
        Generates raindrop sizes based on the extracted POV-Ray formula.

        Args:
            num_particles (int): Number of particles (raindrops) to generate.
            water_size (float): Base size of the raindrops (in meters).
            water_sizeturb (float): Turbulence factor for size variation.
            water_falloff (float): Falloff factor for reducing size based on raindrop state.

        Returns:
            list: List of raindrop sizes (in meters).
        """

        # Generate random values for p_random and p_state for each raindrop
        p_random = np.random.random(size=num_particles)  # Random values between 0 and 1
        p_state = np.random.random(size=num_particles)   # Random state values between 0 and 1

        # Apply the formula from the POV-Ray macro
        _scale = (water_size 
                  * (1 + (p_random - 0.5) * 2 * water_sizeturb)
                  * (0.001 + 0.999 * np.power(1 - p_state, water_falloff))
                 )

        # Return the list of raindrop sizes (in meters)
        return _scale