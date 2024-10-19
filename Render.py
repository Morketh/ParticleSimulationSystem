import subprocess
from inc.cluster import *
import time
import socket

def render_frame(frame_num, output_file):
    ini_file = f"frame_{frame_num}.ini"
    # Generate .ini file for this frame
    with open(ini_file, 'w') as ini:
        ini.write(f"""
        Input_File_Name={output_file}
        Output_File_Name=frame_{frame_num}.png
        Width=1920
        Height=1080
        Quality=9
        Antialias=On
        """)

    # Run the POV-Ray rendering command
    subprocess.run(["povray", ini_file])

def run_render_node(machine_name=socket.gethostname()):
    conn = connect_db()
    while True:
        job = fetch_job(machine_name, conn)
        if job is None:
            print(f"No jobs available for {machine_name}. Retrying in a while...")
            time.sleep(10)
            continue

        frame_num = job['frame_num']
        print(f"Rendering frame {frame_num} on {machine_name}")

        template_file = 'scene_template.pov'
        output_pov_file = f'frame_{frame_num:04d}.pov'
        BuildTemplate(frame_num, template_file, output_pov_file)
        render_frame(frame_num, output_pov_file)
        mark_job_done(frame_num, conn)

    conn.close()

def BuildTemplate(frame_num, template_file, output_file):
    conn = connect_db()
    particles = fetch_particles_for_frame(conn, frame_num)
    
    # Read the template
    with open(template_file, 'r') as file:
        template = file.read()

    # Prepare particle data in POV-Ray format
    particle_strings = []
    for particle in particles:
        particle_str = f"sphere {{ <{particle['position_x']}, {particle['position_y']}, {particle['position_z']}> {particle['size']} texture {{ pigment {{ color {particle['color']} }} }} }}"
        particle_strings.append(particle_str)
    
    # Join all particles into a single string
    particle_data = '\n'.join(particle_strings)
    
    # Replace the placeholder in the template with the generated particles
    filled_template = template.replace("// PARTICLE_SYSTEM", particle_data)

    # Write the filled template to the output POV-Ray file
    with open(output_file, 'w') as output:
        output.write(filled_template)

    conn.close()


if __name__ == "__main__":
    con = connect_db()
    InitNode(con)
    job = fetch_job(con)
