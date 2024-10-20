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

    def __init__(self):
        """
        Initializes the ParticleGenerator class with an empty particle list.
        """
        self.particles = []
    
    def clear_particles(self):
        """
        Clears the list of particles.
        """
        self.particles = []

    def generate_conical_fountain(self, num_particles, apex_position, cone_height,
                                  cone_angle, base_radius, wind_direction,
                                  wind_velocity, texture="WaterTexture"):
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
            size = random.uniform(0.05, 0.15)

            self.particles.append({
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
                'position': position,
                'velocity': velocity,
                'size': size,
                'texture': texture
            })

    def plot_particles_at_frame(self, frame_number, frame_rate):
        """
        Plots the positions of particles at a given frame, considering gravity.
        
        Args:
            frame_number (int): The frame number (F) to calculate particle positions.
            frame_rate (float): The frame rate of the simulation in frames per second (fps).
        
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

            updated_particles.append({
                'particle_id': particle['particle_id'],
                'position': [new_x, new_y, new_z],
                'size': particle['size'],
                'texture': particle['texture']
            })

        return updated_particles