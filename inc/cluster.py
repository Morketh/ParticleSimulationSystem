import MySQLdb
import time
from datetime import datetime
import socket
import sys

class DB:
    conn = None
    host="10.147.18.167"
    port=3306
    user="povray"
    password="123qwe"
    database="povray"

# Function to connect to the MySQL database
    def connect(self):
        self.conn = MySQLdb.Connect(host=self.host,user=self.user,passwd=self.password,db=self.database,port=self.port)

    def fetch(self, sql):
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
        except (AttributeError, MySQLdb.OperationalError):
            self.connect()
            cursor = self.conn.cursor()
            cursor.execute(sql)
        finally:
            self.conn.commit()
            return cursor.lastrowid

    
    def BulkInsert(self, sql, data):
        try:
            cursor = self.conn.cursor()
            cursor.executemany(sql, data)
        except (AttributeError, MySQLdb.OperationalError):
            self.connect()
            cursor = self.conn.cursor()
            cursor.executemany(sql, data)
        finally:
            self.conn.commit()
            return cursor.lastrowid

def insert_particle_data_batch(conn, fnum, particle_data):
    """
    Insert particle data in batches into the MySQL database.
    
    :param conn: MySQL database connection object
    :param particle_data: List of tuples containing particle data for batch insert
    """
    
    # Perform batch insert for all particles in this frame
    #print("Query Size {}".format(sys.getsizeof(particle_data)))
    bulk_sql = """
            INSERT INTO particles (frame_id, job_id, position_x, position_y, position_z,
                                  velocity_x, velocity_y, velocity_z, size, texture)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        #print("Number of rows inserted: {}".format(cursor.rowcount))

def generate_batch_data(job_id, frame_id, particles):
    """
    Generate a list of particle data for batch insert.
    
    :param job_id: ID of the rendering job
    :param frame_num: Frame number in the simulation
    :param particles: List of particle dictionaries containing particle data
    :return: List of tuples for batch insert
    """
    particle_data = []
    
    for particle_id, particle in enumerate(particles):
        # Append each particle's data as a tuple for batch insertion
        particle_data.append((
            job_id, frame_id,
            particle['position'][0], particle['position'][1], particle['position'][2],
            particle['velocity'][0], particle['velocity'][1], particle['velocity'][2],
            particle['size'], particle['texture']
        ))
    
    return particle_data

def fetch_job(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM render_jobs WHERE status = 'pending' LIMIT 1")
    job = cursor.fetchone()
    if job:
        cursor.execute("UPDATE render_jobs SET status = 'in_progress' WHERE id = %s", (job['id'],))
        conn.commit()
    return job

def mark_job_done(frame_num, conn):
    cursor = conn.cursor()
    cursor.execute("UPDATE render_jobs SET status = 'done' WHERE frame_num = %s", (frame_num,))
    conn.commit()

def fetch_particles_for_frame(conn, frame_num):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM particles WHERE frame_num = %s", (frame_num,))
    return cursor.fetchall()

def job_scheduler(conn):
    while True:
        # Fetch the next job
        cursor = conn.cursor()
        cursor.execute("SELECT job_id FROM job_queue WHERE status = 'queued' LIMIT 1")
        job = cursor.fetchone()

        if job:
            job_id = job[0]
            # Update job status to 'processing'
            cursor.execute("UPDATE job_queue SET status = 'processing' WHERE job_id = %s", (job_id,))
            conn.commit()

            # Assign frames and manage threads...
        
        time.sleep(5)  # Wait before checking again

def submit_render_job(conn, job_name, num_frames,
                      res_x=1920, res_y=1080, quality=11, antialias='on',
                      antialias_depth=5, antialias_threshold=0.1, sampling_method=2):
    cursor = conn.cursor()

    # Insert new job into render_jobs table
    cursor.execute("""
        INSERT INTO render_jobs (job_name, status, created_at,
                   total_frames, width, height, quality,
                   antialias, antialias_depth,
                   antialias_threshold, sampling_method)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (job_name, 'pending', datetime.now(),
           num_frames, res_x, res_y, quality, antialias,
           antialias_depth, antialias_threshold, sampling_method))
    
    job_id = cursor.lastrowid  # Get the job_id of the newly inserted job
    conn.commit()

    # Insert frames into the frames table
    for frame_number in range(1, num_frames + 1):
        print(f"Adding frames: {frame_number/num_frames*100:.2f}%", end='\r', flush=True)
        cursor.execute("""
            INSERT INTO frames (job_id, frame_num, status)
            VALUES (%s, %s, %s)
        """, (job_id, frame_number, 'pending'))

    print("Adding frames: 100.00%  Done.")
    conn.commit()
    
    print(f"Submitted job {job_id} with {num_frames} frames.")
    return job_id

def InitNode(conn, node_name=socket.gethostname()):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO nodes (node_name) VALUES (%s)
    """, (node_name,))
    conn.commit()
    return cursor.lastrowid  # Return the node_id

# Function to create work threads for a job
def create_work_threads(conn, job_id, frame_ids, node_id):
    cursor = conn.cursor()
    for frame_id in frame_ids:
        cursor.execute("""
            INSERT INTO work_threads (node_id, job_id, frame_id)
            VALUES (%s, %s, %s)
        """, (node_id, job_id, frame_id))
    conn.commit()