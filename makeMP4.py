import subprocess
from inc.cluster import ClusterManager

# Query to pull FPS, total frames, and job name
query = """
    SELECT job_name, fps, total_frames 
    FROM jobs 
    WHERE status = 'completed'
    LIMIT 1;
"""

def create_ffmpeg_command(job_name, fps, total_frames):
    """ Constructs the FFMPEG command using the job data. """
    input_pattern = f"/nfs/{job_name}/frame_%04d.png"
    output_file = f"/nfs/{job_name}/{job_name}.mp4"
    
    # FFMPEG command to stitch frames into a video
    command = [
        "ffmpeg",
        "-framerate", str(fps),
        "-i", input_pattern,
        "-frames:v", str(total_frames),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_file
    ]
    
    return command

def run_ffmpeg_command(command):
    """ Runs the FFMPEG command to compile the video. """
    try:
        subprocess.run(command, check=True)
        print("Video compilation complete.")
    except subprocess.CalledProcessError as e:
        print(f"Error during FFMPEG execution: {e}")

# Main process

job_data = get_job_data()

if job_data:
    job_name = job_data['job_name']
    fps = job_data['fps']
    total_frames = job_data['total_frames']

    ffmpeg_command = create_ffmpeg_command(job_name, fps, total_frames)
    run_ffmpeg_command(ffmpeg_command)
else:
    print("No job data found.")
