import numpy as np
from inc import particles
from inc.cluster import *

# Update the main simulation part to use the new function
if __name__ == "__main__":

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
    apex_position = [0, 0, 0]  # Starting point of the fountain
    cone_height = 10  # Height of the cone
    cone_angle = np.pi / 6  # 30 degrees cone angle
    base_radius = 5  # Base radius of the cone

    # Define wind direction (as a unit vector) and velocity
    wind_direction = [1, 0.5, 0]  # Wind blowing along the x-axis
    wind_velocity = 2.0  # Wind speed

    water_particles = particles.generate_conical_fountain(num_particles, apex_position,
                                                         cone_height, cone_angle, base_radius,
                                                         wind_direction, wind_velocity)
    
    # Connect to the database and insert particle data for each frame
    db = DB()

    job_id = submit_render_job(db,JobName,num_frames)

 # Main loop for inserting particle data frame by frame
for frame_num in range(num_frames):
    print("Inserting Frame Data: {:.2f}%".format((frame_num / num_frames) * 100), end='\r', flush=True)
    
    # Generate batch data for the current frame
    particle_data_batch = generate_batch_data(job_id, frame_num+1, water_particles)
    
    # Insert all particles for this frame in one batch
    insert_particle_data_batch(conn, frame_num+1, particle_data_batch)
 

    conn.close()
print("Inserting Frame Data: 100%  Done.")