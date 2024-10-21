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
  `job_id` int(11) NOT NULL COMMENT 'Links to the corresponding job.',
  `frame_id` int(11) NOT NULL COMMENT 'Unique identifier.',
  `status` enum('pending','in progress','rendered','error') DEFAULT 'pending' COMMENT 'Current status of the frame.',
  `started_at` timestamp NULL DEFAULT NULL,
  `completed_at` timestamp NULL DEFAULT NULL,
  UNIQUE KEY `frame_id_job_id` (`frame_id`,`job_id`),
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
  `particle_id` int(11) NOT NULL,
  `frame_id` int(11) NOT NULL,
  `job_id` int(11) NOT NULL,
  `position_x` float NOT NULL,
  `position_y` float NOT NULL,
  `position_z` float NOT NULL,
  `velocity_x` float NOT NULL,
  `velocity_y` float NOT NULL,
  `velocity_z` float NOT NULL,
  `size` float NOT NULL,
  `texture_id` int(11) NOT NULL COMMENT 'Links to the corresponding texture.',
  UNIQUE KEY `unique_position_in_frame` (`position_x`,`position_y`,`position_z`,`frame_id`,`particle_id`,`job_id`) USING BTREE,
  KEY `frame_id` (`frame_id`),
  KEY `job_id` (`job_id`),
  KEY `particles_ibfk_1` (`texture_id`),
  CONSTRAINT `job_id` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE,
  CONSTRAINT `particles_ibfk_1` FOREIGN KEY (`texture_id`) REFERENCES `textures` (`texture_id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Data exporting was unselected.

-- Dumping structure for table povray.render_jobs
CREATE TABLE IF NOT EXISTS `render_jobs` (
  `job_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier.',
  `job_name` varchar(255) NOT NULL COMMENT 'Name of the job.',
  `total_frames` int(11) NOT NULL,
  `width` int(10) unsigned NOT NULL DEFAULT 1920,
  `height` int(10) unsigned NOT NULL DEFAULT 1080,
  `fps` int(4) NOT NULL DEFAULT 24,
  `quality` int(10) unsigned NOT NULL DEFAULT 11,
  `antialias` enum('on','off') NOT NULL DEFAULT 'on',
  `antialias_depth` int(10) unsigned NOT NULL DEFAULT 5,
  `antialias_threshold` float unsigned NOT NULL DEFAULT 0.1,
  `sampling_method` int(11) DEFAULT 2,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `status` enum('pending','in progress','completed') DEFAULT 'pending' COMMENT 'Current status (e.g., pending, processing, completed).',
  PRIMARY KEY (`job_id`),
  KEY `status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Keeps track of rendering jobs';

-- Data exporting was unselected.

-- Dumping structure for table povray.textures
CREATE TABLE IF NOT EXISTS `textures` (
  `texture_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier for the texture.',
  `texture_name` varchar(255) NOT NULL COMMENT 'Name of the texture.',
  `texture_description` text DEFAULT NULL COMMENT 'Description of the texture.',
  PRIMARY KEY (`texture_id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Stores information about available textures.';

-- Data exporting was unselected.

-- Dumping structure for view povray.view_frame_status
-- Creating temporary table to overcome VIEW dependency errors
CREATE TABLE `view_frame_status` (
	`frame_id` INT(11) NOT NULL COMMENT 'Unique identifier.',
	`job_name` VARCHAR(1) NOT NULL COMMENT 'Name of the job.' COLLATE 'utf8mb4_general_ci',
	`frame_status` ENUM('pending','in progress','rendered','error') NULL COMMENT 'Current status of the frame.' COLLATE 'utf8mb4_general_ci',
	`started_at` TIMESTAMP NULL,
	`completed_at` TIMESTAMP NULL,
	`time_to_complete` BIGINT(21) NULL
) ENGINE=MyISAM;

-- Dumping structure for view povray.view_job_summary
-- Creating temporary table to overcome VIEW dependency errors
CREATE TABLE `view_job_summary` (
	`job_id` INT(11) NOT NULL COMMENT 'Unique identifier.',
	`job_name` VARCHAR(1) NOT NULL COMMENT 'Name of the job.' COLLATE 'utf8mb4_general_ci',
	`job_status` ENUM('pending','in progress','completed') NULL COMMENT 'Current status (e.g., pending, processing, completed).' COLLATE 'utf8mb4_general_ci',
	`total_frames` BIGINT(21) NOT NULL,
	`rendered_frames` DECIMAL(22,0) NULL,
	`pending_frames` DECIMAL(22,0) NULL,
	`in_progress_frames` DECIMAL(22,0) NULL,
	`created_at` TIMESTAMP NOT NULL
) ENGINE=MyISAM;

-- Dumping structure for view povray.view_particle_summary
-- Creating temporary table to overcome VIEW dependency errors
CREATE TABLE `view_particle_summary` 
) ENGINE=MyISAM;

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

-- Removing temporary table and create final VIEW structure
DROP TABLE IF EXISTS `view_frame_status`;
CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `view_frame_status` AS select `f`.`frame_id` AS `frame_id`,`rj`.`job_name` AS `job_name`,`f`.`status` AS `frame_status`,`f`.`started_at` AS `started_at`,`f`.`completed_at` AS `completed_at`,timestampdiff(SECOND,`f`.`started_at`,`f`.`completed_at`) AS `time_to_complete` from (`frames` `f` join `render_jobs` `rj` on(`f`.`job_id` = `rj`.`job_id`));

-- Removing temporary table and create final VIEW structure
DROP TABLE IF EXISTS `view_job_summary`;
CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `view_job_summary` AS select `rj`.`job_id` AS `job_id`,`rj`.`job_name` AS `job_name`,`rj`.`status` AS `job_status`,count(`f`.`frame_id`) AS `total_frames`,sum(case when `f`.`status` = 'rendered' then 1 else 0 end) AS `rendered_frames`,sum(case when `f`.`status` = 'pending' then 1 else 0 end) AS `pending_frames`,sum(case when `f`.`status` = 'in progress' then 1 else 0 end) AS `in_progress_frames`,`rj`.`created_at` AS `created_at` from (`render_jobs` `rj` left join `frames` `f` on(`rj`.`job_id` = `f`.`job_id`)) group by `rj`.`job_id`,`rj`.`job_name`,`rj`.`status`,`rj`.`created_at`;

-- Removing temporary table and create final VIEW structure
DROP TABLE IF EXISTS `view_particle_summary`;
CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `view_particle_summary` AS select `p`.`particle_id` AS `particle_id`,`p`.`frame_id` AS `frame_id`,`rj`.`job_name` AS `job_name`,`p`.`position_x` AS `position_x`,`p`.`position_y` AS `position_y`,`p`.`position_z` AS `position_z`,`p`.`velocity_x` AS `velocity_x`,`p`.`velocity_y` AS `velocity_y`,`p`.`velocity_z` AS `velocity_z`,`p`.`size` AS `size`,`p`.`texture` AS `texture` from ((`particles` `p` join `frames` `f` on(`p`.`frame_id` = `f`.`frame_id`)) join `render_jobs` `rj` on(`p`.`job_id` = `rj`.`job_id`));

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
