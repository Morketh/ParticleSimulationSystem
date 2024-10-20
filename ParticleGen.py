import numpy as np
from inc.particles import ParticleGenerator
from inc.cluster import ClusterManager
from dotenv import load_dotenv
import os

# Update the main simulation part to use the new function
if __name__ == "__main__":
    # LOAD settings from the .env file
    load_dotenv()
    host = os.getenv('HOST')
    user = os.getenv('USER')
    passwrd = os.getenv('PASSWORD')
    port = os.getenv('PORT')
    db = os.getenv('DATABASE')

    # Global Settings for Render Job (should be pulled from the commandline or job que)
    res_x = 1920
    res_y = 1080
    AntiAlias = 10
    Quality = 11
    fps = 120
    num_frames = 3600
    num_particles = 1000

    JobName = "Fountain_{}x{}_Q{}_aa{}_fr{}".format(res_x,res_y,Quality,AntiAlias,fps)

    # Scene Settings
    apex_position = [0, 1.5, 14]  # Starting point of the fountain
    cone_height = 2  # Height of the cone
    cone_angle = np.pi / 6  # 30 degrees cone angle
    base_radius = 1.75  # Base radius of the cone

    # Define wind direction (as a unit vector) and velocity
    wind_direction = [1, 0.5, 0]  # Wind blowing along the x-axis
    wind_velocity = 2.0  # Wind speed

    cluster = ClusterManager(host=host, user=user, port=port, passwrd=passwrd, db=db)
    node_info = cluster.get_node_info()

    waterParticles = ParticleGenerator()

    waterParticles.generate_conical_fountain(num_particles, apex_position, cone_height, cone_angle, base_radius, wind_direction, wind_velocity)

# Main loop for inserting particle data frame by frame
    cluster.connect()
    jid = cluster.create_job(JobName,num_frames,res_x,res_y,Quality,AntiAlias,10,0.1,2)
    cluster.insert_frames(jid,num_frames)
    for frame_num in range(num_frames):
        print("Inserting Frame Data: {:.2f}%".format((frame_num / num_frames) * 100), end='\r', flush=True)
        waterParticles.plot_particles_at_frame(frame_num,frame_rate=fps)
        cluster.insert_particle_data(jid,frame_num,waterParticles.particles)

    print("Inserting Frame Data: 100%  Done.")