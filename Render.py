from inc.cluster import *
from dotenv import load_dotenv
import os
import subprocess
import time
import socket

def remove_extension(file_name):
    # Split the file name into the base name and extension
    base_name, _ = os.path.splitext(file_name)
    return base_name

def open_pov_template(templateFile,FrameNum,JobName):
    try:
        # Open the POV template file in read mode
        with open(templateFile, 'r') as file:
            # Read the entire file content
            template_content = file.read()

        
        modified_content = template_content.replace("// PARTICLE_SYSTEM", )

        # Save the modified content to a new file (or overwrite the original)
        output_file_path = "{}_{}_Frame-{}.pov".format(remove_extension(templateFile),JobName,FrameNum)
        with open(output_file_path, 'w') as output_file:
            # TODO MODIFY TEMPLATE WITH PARTICLE DATA

            output_file.write(modified_content)

        print(f"Modified POV template saved as {output_file_path}")

    except FileNotFoundError:
        print(f"Error: The file {templateFile} does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
        # LOAD settings from the .env file
    load_dotenv()
    host = os.getenv('HOST')
    user = os.getenv('USER')
    passwrd = os.getenv('PASSWORD')
    port = os.getenv('PORT')
    db = os.getenv('DATABASE')

    povCluster = ClusterManager(host=host, user=user, port=port, passwrd=passwrd, db=db)
    povCluster.connect()
    print(povCluster.get_next_pending_job())

#    pov_file_path = 'path_to_your_template.pov'
#    open_pov_template(pov_file_path)
