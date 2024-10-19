-- --------------------------------------------------------
-- Host:                         10.147.18.167
-- Server version:               11.4.3-MariaDB-1 - Debian n/a
-- Server OS:                    debian-linux-gnu
-- HeidiSQL Version:             12.8.0.6908
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Dumping database structure for povray
CREATE DATABASE IF NOT EXISTS `povray` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci */;
USE `povray`;

-- Dumping structure for table povray.frames
CREATE TABLE IF NOT EXISTS `frames` (
  `frame_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier.',
  `job_id` int(11) NOT NULL COMMENT 'Links to the corresponding job.',
  `frame_num` int(11) NOT NULL COMMENT 'The specific frame number.',
  `status` enum('pending','in progress','rendered','error') DEFAULT 'pending' COMMENT 'Current status of the frame.',
  `started_at` timestamp NULL DEFAULT NULL,
  `completed_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`frame_id`),
  KEY `job_id` (`job_id`),
  CONSTRAINT `frames_ibfk_1` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Contains information about frames in each render job.';

-- Data exporting was unselected.

-- Dumping structure for table povray.nodes
CREATE TABLE IF NOT EXISTS `nodes` (
  `node_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier.',
  `node_name` varchar(255) NOT NULL COMMENT ' Identifier (like IP or hostname).',
  `ip_address` varchar(45) NOT NULL DEFAULT 'active' COMMENT 'Stores the IP address of the node ',
  `role` enum('master','render','database','storage','monitor') NOT NULL COMMENT 'Node Role',
  `status` enum('active','inactive') NOT NULL DEFAULT 'active' COMMENT 'Active or inactive.',
  `last_heartbeat` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'Timestamp for the last activity.',
  `cpu_cores` int(11) NOT NULL COMMENT 'The number of CPU cores available on the node.',
  `memory_gb` float NOT NULL DEFAULT 0 COMMENT 'The amount of memory (in GB) available on the node',
  PRIMARY KEY (`node_id`),
  KEY `role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Keeps track of rendering nodes (computers).';

-- Data exporting was unselected.

-- Dumping structure for table povray.particles
CREATE TABLE IF NOT EXISTS `particles` (
  `particle_id` int(11) NOT NULL AUTO_INCREMENT,
  `frame_id` int(11) NOT NULL,
  `job_id` int(11) NOT NULL,
  `position_x` float NOT NULL,
  `position_y` float NOT NULL,
  `position_z` float NOT NULL,
  `velocity_x` float NOT NULL,
  `velocity_y` float NOT NULL,
  `velocity_z` float NOT NULL,
  `size` float NOT NULL,
  `texture` varchar(255) NOT NULL,
  PRIMARY KEY (`particle_id`),
  KEY `frame_id` (`frame_id`),
  KEY `job_id` (`job_id`),
  CONSTRAINT `job_id` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Data exporting was unselected.

-- Dumping structure for table povray.render_jobs
CREATE TABLE IF NOT EXISTS `render_jobs` (
  `job_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier.',
  `job_name` varchar(255) NOT NULL COMMENT 'Name of the job.',
  `total_frames` int(11) NOT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `status` enum('pending','in progress','completed') DEFAULT 'pending' COMMENT 'Current status (e.g., pending, processing, completed).',
  `width` int(10) unsigned NOT NULL DEFAULT 1920,
  `height` int(10) unsigned NOT NULL DEFAULT 1080,
  `quality` int(10) unsigned NOT NULL DEFAULT 11,
  `antialias` varchar(4) NOT NULL DEFAULT 'on',
  `antialias_depth` int(10) unsigned NOT NULL DEFAULT 5,
  `antialias_threshold` float unsigned NOT NULL DEFAULT 0.1,
  `sampling_method` int(11) DEFAULT 2,
  PRIMARY KEY (`job_id`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Keeps track of rendering jobs';

-- Data exporting was unselected.

-- Dumping structure for table povray.work_threads
CREATE TABLE IF NOT EXISTS `work_threads` (
  `thread_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier.',
  `node_id` int(11) NOT NULL COMMENT 'Links to the corresponding node.',
  `job_id` int(11) NOT NULL COMMENT 'Links to the job.',
  `frame_id` int(11) NOT NULL COMMENT 'Links to the frame being processed',
  `status` enum('queued','processing','completed') DEFAULT 'queued' COMMENT 'Status of the thread (queued, processing, completed).',
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`thread_id`),
  KEY `node_id` (`node_id`),
  KEY `job_id` (`job_id`),
  KEY `frame_id` (`frame_id`),
  CONSTRAINT `work_threads_ibfk_1` FOREIGN KEY (`node_id`) REFERENCES `nodes` (`node_id`) ON DELETE CASCADE,
  CONSTRAINT `work_threads_ibfk_2` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE,
  CONSTRAINT `work_threads_ibfk_3` FOREIGN KEY (`frame_id`) REFERENCES `frames` (`frame_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Manages individual work threads assigned to nodes.';

-- Data exporting was unselected.

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
