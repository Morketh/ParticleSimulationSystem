import random
import numpy as np

# Function to generate particles in a conical fountain spray
def generate_conical_fountain(num_particles, apex_position, cone_height,
                              cone_angle, base_radius, wind_direction,
                              wind_velocity, texture="WaterTexture"):
    
    particles = []
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

        # Random particle size and color
        size = random.uniform(0.05, 0.15)

        particles.append({
            'position': [x, y, z],
            'velocity': [velocity_x, velocity_y, velocity_z],
            'size': size,
            'texture': texture
        })
    return particles


def generate_fire_particles(base_position, num_particles, texture="FireTexture"):
    particles = []
    for i in range(num_particles):
        # Randomly generate initial position near the base of the brazier
        position = [base_position[0] + random.uniform(-0.1, 0.1), base_position[1], base_position[2] + random.uniform(-0.1, 0.1)]
        velocity = [random.uniform(-0.2, 0.2), random.uniform(1.0, 3.0), random.uniform(-0.2, 0.2)]  # Upward motion
        size = random.uniform(0.05, 0.15)
        texture = "FireTexture"

        particles.append({
            'position': position,
            'velocity': velocity,
            'size': size,
            'texture': texture
        })
    return particles