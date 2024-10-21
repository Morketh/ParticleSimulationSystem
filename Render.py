from inc.cluster import *
from dotenv import load_dotenv
import os
import subprocess
import platform
import time
import socket

def detect_povray_path():
    current_os = platform.system()

    if current_os == "Windows":
        # Default path for Windows POV-Ray installation (update if needed)
        povray_path = r"C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe"
    elif current_os == "Darwin":  # macOS
        # Default path for macOS POV-Ray installation (update if needed)
        povray_path = "/Applications/POV-Ray 3.7/POV-Ray.app/Contents/MacOS/POV-Ray"
    else:  # Linux or other Unix-like systems
        try:
            # Run 'which povray' command to find POV-Ray in the system's PATH
            result = subprocess.run(['which', 'povray'], capture_output=True, text=True, check=True)
            povray_path = result.stdout.strip()  # Get the output and remove any extra spaces/newlines
        except subprocess.CalledProcessError:
            # Handle the case where POV-Ray is not found in PATH
            print("Error: POV-Ray executable not found in system's PATH. Please install POV-Ray or specify the correct path.")
            povray_path = None
            exit(-1)

    return povray_path

def CallRenderEngine(job_details,input_file,output_file):
    # Extract job details
    width = job_details[0]['width']
    height = job_details[0]['height']
    quality = job_details[0]['quality']
    antialias = job_details[0]['antialias']
    antialias_depth = job_details[0]['antialias_depth']
    # Construct the POV-Ray command
    pov_command = [
        detect_povray_path(),
        "/Exit",                        # EXIT povray when complete
        f"+I{input_file}",              # Input file
        f"+O{output_file}",             # Output file
        f"+W{width}",                   # Width
        f"+H{height}",                  # Height
        f"+Q{quality}",                 # Quality
    ]
    
    # Handle antialiasing
    if antialias == "on":
        pov_command.append(f"+A")
        pov_command.append(f"+R{antialias_depth}")  # Antialias depth
    
    # Execute the POV-Ray command
    print(f"Rendering: {input_file} -> {output_file}")
    proc = subprocess.run(pov_command)
    return proc.returncode

def remove_extension(file_name):
    # Split the file name into the base name and extension
    base_name, _ = os.path.splitext(file_name)
    return base_name

def format_particle_objects(particle_list):
    """
    Format the particle data into POV-Ray object syntax.

    Args:
        particle_list (list): List of particle dictionaries.

    Returns:
        str: Formatted string for POV-Ray objects.
    """
    particle_objects = []
    for particle in particle_list:
        obj = (f"sphere {{ <{particle['position_x']}, {particle['position_y']}, {particle['position_z']}> , {particle['size']}, 1 }}\n")
        particle_objects.append(obj)
    
    return ''.join(particle_objects)

def buildOutputFile(template_file_path, output_file_path, particle_objects):
    """
    Writes a POV file with particle data using a template as a base for static objects

    Args:
        template_file_path (str): Path to the template POV file.
        output_file_path (str): Path to save the modified POV file.
        particle_objects (str): The particle objects string to insert.

    Returns:
        None
    """
    with open(template_file_path, 'r') as file:
        content = file.read()
    # Write the updated content to the output file
    content = content.replace("//PARTICLE_SYSTEM", particle_objects)
    with open(output_file_path, 'w') as file:
        file.write(content)

def create_outputDirectory(directory_path):
    """
    Creates a directory if it does not already exist.

    Args:
        directory_path (str): The path of the directory to create.
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        print(f"Directory {directory_path} created.")

if __name__ == "__main__":
    # LOAD settings from the .env file
    load_dotenv()
    host = os.getenv('HOST')
    user = os.getenv('USER')
    passwrd = os.getenv('PASSWORD')
    port = os.getenv('PORT')
    db = os.getenv('DATABASE')
    template = 'NewBegining.pov'

    povCluster = ClusterManager(host=host, user=user, port=port, passwrd=passwrd, db=db)
    povCluster.connect()
    povCluster.insert_node_info('active','render')

    # TODO Get mynode role from db

    jobDetails = povCluster.get_next_pending_job()
    frames = povCluster.get_total_frames(jobDetails[0]['job_id'])
    for i in range(frames['total']):
        frameID = povCluster.get_next_frame(jobDetails[0]['job_id'])[0]['frame_id']
        
        outFile = "{}_frame-{:04d}.pov".format(remove_extension(template),frameID)
        povFile = "output/{}/{}".format(jobDetails[0]['job_name'],outFile)
        pngFile = "output/{}/{}_frame-{:04d}".format(jobDetails[0]['job_name'],remove_extension(template),frameID)
        
        create_outputDirectory("output/{}".format(jobDetails[0]['job_name']))

        povCluster.update_frame_status(frameID, 'in progress')

        # Build frame render info
        textures = povCluster.get_textures()
        particles = []
        for _, t in enumerate(textures): # Get all particles in frame group by texture
            particles = povCluster.get_particles(jobDetails[0]['job_id'], frameID, t['texture_id'])
            if particles:
                pvOBJ = format_particle_objects(particles)
                buildOutputFile(template,"output/{}/{}".format(jobDetails[0]['job_name'],outFile),pvOBJ)

        retCode = CallRenderEngine(jobDetails, povFile, pngFile)
        if retCode != 0:
            povCluster.update_frame_status(frameID, 'error')
        else:
            povCluster.update_frame_status(frameID, 'rendered')