import MySQLdb
import time
from datetime import datetime
import socket
import psutil
import sys

class ClusterManager:
    """
    A class to manage the connection and operations of a database cluster
    for rendering jobs, particles, and nodes in a distributed system.

    This class provides methods to establish a connection to a MySQL database,
    manage jobs, frames, particles, and monitor nodes within a Beowulf cluster.
    The connection details are provided during initialization, and the class
    manages the database cursor and connection for executing SQL queries.
    
    Attributes:
        conn (MySQLdb.Connection): The MySQL database connection object (None until connected).
        cursor (MySQLdb.Cursor): The cursor for executing SQL queries (None until connected).
        host (str): The database host (IP address or domain) to connect to.
        port (int): The port number used for connecting to the database.
        user (str): The username for authenticating with the database.
        password (str): The password for the database connection (using the port value for demo purposes).
        database (str): The name of the database to use.

    Methods:
        __init__(self, host, user, port, db):
            Initializes the ClusterManager instance with database connection parameters.
    """
    def __init__(self, host, user, port, db, passwrd):
        """
        Initializes the ClusterManager class with the connection parameters for the MySQL database.

        Args:
            host (str): The hostname or IP address of the MySQL server.
            user (str): The username used to authenticate with the MySQL database.
            port (int): The port number for the MySQL connection (default is typically 3306).
            db (str): The name of the database to connect to.
            passwrd (str): The password for the database user

        Attributes:
            conn (MySQLdb.Connection): Initially set to None. The connection to the MySQL database will be established later.
            cursor (MySQLdb.Cursor): Initially set to None. The cursor for executing SQL queries will be created after connecting.
            host (str): Stores the database host address.
            port (int): Stores the port number for the MySQL connection.
            user (str): Stores the username for MySQL authentication.
            password (str): For demo purposes, stores the port number (should be the actual password in real use).
            database (str): Stores the name of the database to connect to.
        """
        self.conn = None
        self.cursor = None
        self.host=host
        self.port=int(port)
        self.user=user
        self.password=passwrd
        self.database=db

    def __return_dict(self):
           # Get column names from the cursor
           columns = [col[0] for col in self.cursor.description]
           # Fetch all rows and convert each row into a dictionary
           return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        
# Function to connect to the MySQL database
    def connect(self):
        """
        Establishes a connection to the MySQL database using the provided credentials.
        """
        try:
            self.conn = MySQLdb.Connect(host=self.host,user=self.user,passwd=self.password,db=self.database,port=self.port)
            self.cursor = self.conn.cursor()
            print("Connection established")
        except MySQLdb.Error as e:
            print("Error connecting to database: {}".format(e))
            exit(-1)
    
    def disconnect(self):
        """
        Closes the connection to the database and the cursor.
        """
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("Connection closed")

    def insert_particle_data(self, job_id, frame_id, particle_data):
        """
        Inserts all particles for a given frame into the particles table.

        Args:
            job_id (int): The ID of the job.
            frame_id (int): the frame number.
            particle_job (list): list of dict values for particles
        """
        query = """
            INSERT INTO particles (particle_id, frame_id, job_id, position_x, position_y, position_z,
                              velocity_x, velocity_y, velocity_z, size, texture_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        texture_query = "SELECT texture_id FROM textures WHERE texture_name = %s"
        try:
            for particle in particle_data:
                # Fetch the texture_id based on the texture name
                self.cursor.execute(texture_query, (particle['texture'],))
                texture_result = self.cursor.fetchone()
                
                if texture_result is None:
                    print(f"Error: Texture '{particle['texture']}' not found in textures table.")
                    continue

                texture_id = texture_result[0]  # Extract texture_id from result tuple

                self.cursor.execute(query, (
                    particle['particle_id'],   # Extract individual values from the particle dict
                    frame_id,
                    job_id,
                    particle['position'][0],   # position_x
                    particle['position'][1],   # position_y
                    particle['position'][2],   # position_z
                    particle['velocity'][0],   # velocity_x
                    particle['velocity'][1],   # velocity_y
                    particle['velocity'][2],   # velocity_z
                    particle['size'],
                    texture_id
                ))
                self.conn.commit()
        except MySQLdb.Error as e:
            print(f"Error inserting particle data: {e}")
            self.conn.rollback()

    def fetch_frame_by_job(self, job_id):
        """
        Fetches all frames associated with a given job.

        Args:
            job_id (int): The ID of the job.

        Returns:
            list: A list of frames associated with the job.
        """
        query = "SELECT * FROM frames WHERE job_id = %s"
        try:
            self.cursor.execute(query, (job_id,))
            return self.__return_dict()
        except MySQLdb.Error as e:
            print(f"Error fetching frames: {e}")
            return None

    def insert_frames(self, job_id, num_frames):
        """
        Inserts multiple frames into the frames table for a given job.

        Args:
            job_id (int): The ID of the job.
            num_frames (int): The number of frames to insert.
        """
        query = """
                INSERT INTO frames (job_id, frame_id, status)
                VALUES (%s, %s, %s)
            """
        try:
            for frame_number in range(1, num_frames + 1):
                print(f"Adding frames: {frame_number/num_frames*100:.2f}%", end='\r', flush=True)
                self.cursor.execute(query, (job_id, frame_number, 'pending'))

            print("Adding frames: 100.00%  Done.")
            self.conn.commit()

            print(f"Submitted job {job_id} with {num_frames} frames.")
            return job_id
        except MySQLdb.Error as e:
            print(f"Error adding frames: {e}")
            return None

    def update_frame_status(self, frame_id, status):
        """
        Updates the status of a specific frame in the frames table.

        Args:
            frame_id (int): The ID of the frame.
            status (str): The new status of the frame (e.g., 'rendering', 'completed').
        """
        query = "UPDATE frames SET status = %s WHERE frame_id = %s"
        try:
            self.cursor.execute(query, (status, frame_id))
            self.conn.commit()
            print(f"Updated frame {frame_id} to status: {status}")
        except MySQLdb.Error as e:
            print(f"Error updating frame status: {e}")
            self.conn.rollback()

    def create_job(self, job_name, num_frames, res_x, res_y, fps, quality, antialias,
                antialias_depth, antialias_threshold, sampling_method):
        """
        Creates a new render job in the render_jobs table.

        Args:
            job_name (str): The name of the job.
            num_frames (int): The total number of frames in the job.
            res_x (int): The width of the render in pixels.
            res_y (int): The height of the render in pixels.
            quality (int): The quality setting for the render.
            antialias (bool): Whether antialiasing is enabled.
            antialias_depth (int): The depth of antialiasing.
            antialias_threshold (float): The antialiasing threshold.
            sampling_method (int): The method of sampling for antialiasing.
        Return:
            job_id (int): job ID from SQL server or None if failed.
        """
        query = """
            INSERT INTO render_jobs (job_name, total_frames, width, height, fps, quality, antialias, antialias_depth, antialias_threshold, sampling_method)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """ 
        try:
            self.cursor.execute(query, (job_name, num_frames, res_x, res_y, fps, quality, antialias,
                antialias_depth, antialias_threshold, sampling_method))
            self.conn.commit()
            job_id = self.cursor.lastrowid
            print(f"Created job {job_name} with job_id {job_id}")
            return job_id
        except MySQLdb.Error as e:
            print(f"Error creating job: {e}")
            self.conn.rollback()
            return None

    def get_next_frame(self, job_id):
        """Get the next available frame for rendering (i.e., pending)."""
        query = "SELECT frame_id FROM frames WHERE job_id = %s AND status = 'pending' LIMIT 1"
        try:
            self.cursor.execute(query, (job_id,))
            return self.__return_dict()
        except MySQLdb.Error as e:
            print(f"Error fetching available frame: {e}")
            return None
    
    def get_active_render_nodes(self):
        """Fetch all active render nodes."""
        query = "SELECT * FROM nodes WHERE role = 'render' AND status = 'active'"
        try:
            self.cursor.execute(query)
            render_nodes = self.cursor.fetchall()
            return render_nodes
        except MySQLdb.Error as e:
            print(f"Error fetching render nodes: {e}")
            return None
        
    def get_node_info(self):
        """
        Fetches the current machine's system information including the IP address,
        number of CPU cores, and total memory in GB.

        This method gathers the following information:
        1. **IP Address**: Obtains the machine's local IP address using the `socket` library.
        2. **CPU Cores**: Retrieves the number of logical CPU cores using the `psutil` library.
        3. **Memory**: Fetches the total memory (RAM) in gigabytes using `psutil`.

        Returns:
            tuple: A tuple containing the following elements:
                - ip_address (str): The IP address of the current machine.
                - cpu_cores (int): The number of logical CPU cores.
                - memory_gb (float): The total memory in gigabytes, rounded to two decimal places.
        """
        # Get IP address
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        
        # Get CPU cores
        cpu_cores = psutil.cpu_count(logical=True)
        
        # Get total memory in GB
        memory_info = psutil.virtual_memory()
        memory_gb = round(memory_info.total / (1024 ** 3), 2)  # Convert bytes to GB
        
        return hostname, ip_address, cpu_cores, memory_gb

    def insert_node_info(self, status='active',role='render'):
        """Insert the node's info into the database."""
        hostname, ip_address, cpu_cores, memory_gb = self.get_node_info()
        query = """
            INSERT INTO nodes (node_name, ip_address, cpu_cores, memory_gb, status, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        try:
            # Assuming this is an active render node by default
            self.cursor.execute(query, (hostname, ip_address, cpu_cores, memory_gb, status, role))
            self.conn.commit()
            print(f"Registered node with IP: {ip_address}, CPU: {cpu_cores} cores, Memory: {memory_gb} GB")
        except MySQLdb.Error as e:
            print(f"Error inserting node info: {e}")

    def get_all_node_info(self):
        """Fetch ip_address, cpu_cores, and memory_gb for all nodes."""
        query = "SELECT ip_address, cpu_cores, memory_gb FROM nodes"
        try:
            self.cursor.execute(query)
            nodes = self.cursor.fetchall()
            return nodes
        except MySQLdb.Error as e:
            print(f"Error fetching node info: {e}")
            return None
        finally:
            self.conn.commit()

    def create_work_threads(self, job_id, frame_ids, node_id):
        """
        Creates work threads for the given frames, assigning them to a specific node for rendering.

        Args:
            job_id (int): The ID of the job.
            frame_ids (list): List of frame IDs to assign to work threads.
            node_id (int): The ID of the node handling the frames.
        """
        query = """
            INSERT INTO work_threads (node_id, job_id, frame_id)
            VALUES (%s, %s, %s)
        """
        try:
            for frame_id in frame_ids:
                self.cursor.execute(query, (node_id, job_id, frame_id))
            self.conn.commit()
            print(f"Created work threads for job {job_id} on node {node_id}")
        except MySQLdb.Error as e:
            print(f"Error creating work threads: {e}")
            self.conn.rollback()

    def get_next_pending_job(self):
        try:            
            # Prepare the SQL query
            query = """
                SELECT * FROM povray.render_jobs
                WHERE render_jobs.status = 'pending'
                ORDER BY job_id
                LIMIT 1;
            """
            
            # Execute the query
            self.cursor.execute(query)
            return self.__return_dict()  # Returns a dictionary of the job details

        except MySQLdb.Error as e:
            print(f"Error: {e}")
            return None
        
    def get_particles(self, job_id, frame_id, texture_id):
        """
        Retrieve particle data from the database for a specific rendering job and frame.

        This method queries the `particles` table to fetch details about particles 
        associated with a specific job and frame, including their positions, size, 
        and corresponding texture name. The results are obtained by joining with 
        the `textures` table based on the texture ID.

        Args:
            job_id (int): The unique identifier of the rendering job.
            frame_id (int): The unique identifier of the frame for which to retrieve particles.
            texture_id (int): The unique identifier of the texture to filter the results.

        Returns:
            list: A list of dictionaries, each containing:
                - 'particle_id' (int): The unique identifier of the particle.
                - 'position_x' (float): The X position of the particle.
                - 'position_y' (float): The Y position of the particle.
                - 'position_z' (float): The Z position of the particle.
                - 'size' (float): The size of the particle.
                - 'texture_name' (str): The name of the texture associated with the particle.

        Raises:
            MySQLdb.Error: If there is an error executing the SQL query.
        """
        query = """
            SELECT p.particle_id, p.position_x, p.position_y, p.position_z, p.size, t.texture_name
            FROM 
                `povray`.`particles` p
            LEFT JOIN 
                `povray`.`textures` t ON p.texture_id = t.texture_id
            WHERE p.frame_id = %s AND p.job_id = %s AND t.texture_id = %s
            """
        self.cursor.execute(query,(frame_id,job_id,texture_id))
        return self.__return_dict()
    
    def get_textures(self):
        query = """
            SELECT texture_id, texture_name
            FROM `povray`.`textures`
            """
        self.cursor.execute(query)
        return self.__return_dict()
    
    def get_total_frames(self,job_id):
        """Retrieve total frame count from database
        Args:
            job_id (int): The unique identifier of the rendering job.
        Returns:
            dict: 'total' total frames registerd in DB for a given job_id
        """
        query = """SELECT COUNT(*) AS total FROM frames WHERE `job_id` = %s;"""
        self.cursor.execute(query,(job_id,))
        return self.__return_dict()[0] #should only be getting a single row for each job so we can strip it here

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