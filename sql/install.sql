-- --------------------------------------------------------
-- Host:                         127.0.0.1
-- Server version:               11.4.3-MariaDB-1
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

CREATE DATABASE IF NOT EXISTS `povray` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci */;
USE `povray`;

-- --------------------------------------------------------
-- Table: textures (identity only)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `textures` (
  `texture_id` int(11) NOT NULL AUTO_INCREMENT,
  `texture_name` varchar(255) NOT NULL,
  `texture_description` text DEFAULT NULL,
  PRIMARY KEY (`texture_id`),
  UNIQUE KEY `texture_name` (`texture_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Texture identities';

-- --------------------------------------------------------
-- Table: texture_presets (PBR parameters)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `texture_presets` (
  `preset_id` int(11) NOT NULL AUTO_INCREMENT,
  `texture_id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL COMMENT 'e.g., "Default Water", "Blue Water"',
  `pigment_r` float NOT NULL DEFAULT 1.0,
  `pigment_g` float NOT NULL DEFAULT 1.0,
  `pigment_b` float NOT NULL DEFAULT 1.0,
  `pigment_t` float NOT NULL DEFAULT 0.0 COMMENT 'transparency (0 opaque, 1 fully transparent)',
  `ambient` float NOT NULL DEFAULT 0.1,
  `diffuse` float NOT NULL DEFAULT 0.9,
  `reflection` float NOT NULL DEFAULT 0.0,
  `specular` float NOT NULL DEFAULT 0.0,
  `roughness` float NOT NULL DEFAULT 0.0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`preset_id`),
  KEY `texture_id` (`texture_id`),
  CONSTRAINT `preset_texture_fk` FOREIGN KEY (`texture_id`) REFERENCES `textures` (`texture_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='PBR texture presets';

-- --------------------------------------------------------
-- Table: render_jobs (including preset reference)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `render_jobs` (
  `job_id` int(11) NOT NULL AUTO_INCREMENT,
  `job_name` varchar(255) NOT NULL,
  `total_frames` int(11) NOT NULL,
  `width` int(10) unsigned NOT NULL DEFAULT 1920,
  `height` int(10) unsigned NOT NULL DEFAULT 1080,
  `fps` int(4) NOT NULL DEFAULT 24,
  `quality` int(10) unsigned NOT NULL DEFAULT 11,
  `antialias` enum('on','off') NOT NULL DEFAULT 'on',
  `antialias_depth` int(10) unsigned NOT NULL DEFAULT 5,
  `antialias_threshold` float unsigned NOT NULL DEFAULT 0.1,
  `sampling_method` int(11) DEFAULT 2,
  `gravity` float NOT NULL DEFAULT 9.81 COMMENT 'Gravity (m/s²)',
  `water_level` float NOT NULL DEFAULT 0.0 COMMENT 'Collision plane Y coordinate',
  `preset_id` int(11) DEFAULT NULL COMMENT 'Texture preset for all particles in this job',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `status` enum('pending','in progress','completed','error') DEFAULT 'pending',
  PRIMARY KEY (`job_id`),
  KEY `status` (`status`),
  KEY `preset_id` (`preset_id`),
  CONSTRAINT `job_preset_fk` FOREIGN KEY (`preset_id`) REFERENCES `texture_presets` (`preset_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
-- Table: frames
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `frames` (
  `job_id` int(11) NOT NULL,
  `frame_id` int(11) NOT NULL,
  `status` enum('pending','in progress','rendered','error') DEFAULT 'pending',
  `started_at` timestamp NULL DEFAULT NULL,
  `completed_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`job_id`, `frame_id`),
  KEY `status` (`status`),
  CONSTRAINT `frames_job_fk` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
-- Table: particle_births
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `particle_births` (
  `birth_id` int(11) NOT NULL AUTO_INCREMENT,
  `job_id` int(11) NOT NULL,
  `particle_id` int(11) NOT NULL,
  `birth_time` float NOT NULL,
  `x0` float NOT NULL,
  `y0` float NOT NULL,
  `z0` float NOT NULL,
  `vx0` float NOT NULL,
  `vy0` float NOT NULL,
  `vz0` float NOT NULL,
  `size` float NOT NULL,
  `texture_id` int(11) NOT NULL,
  `seed` int(11) NOT NULL,
  `impact_time` float DEFAULT NULL,
  PRIMARY KEY (`birth_id`),
  UNIQUE KEY `job_particle` (`job_id`,`particle_id`),
  KEY `texture_id` (`texture_id`),
  CONSTRAINT `pb_job_fk` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE,
  CONSTRAINT `pb_texture_fk` FOREIGN KEY (`texture_id`) REFERENCES `textures` (`texture_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
-- Table: simulation_metrics
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `simulation_metrics` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `job_id` int(11) NOT NULL,
  `time` float NOT NULL,
  `particle_count` int(11) DEFAULT 0,
  `min_x` float DEFAULT NULL,
  `max_x` float DEFAULT NULL,
  `min_y` float DEFAULT NULL,
  `max_y` float DEFAULT NULL,
  `min_z` float DEFAULT NULL,
  `max_z` float DEFAULT NULL,
  `avg_velocity` float DEFAULT NULL,
  `max_velocity` float DEFAULT NULL,
  `kinetic_energy` float DEFAULT NULL,
  `potential_energy` float DEFAULT NULL,
  `total_energy` float DEFAULT NULL,
  `momentum_x` float DEFAULT NULL,
  `momentum_y` float DEFAULT NULL,
  `momentum_z` float DEFAULT NULL,
  `nan_count` int(11) DEFAULT 0,
  `inf_count` int(11) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `job_time` (`job_id`,`time`),
  CONSTRAINT `metrics_job_fk` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
-- Table: frame_particle_cache
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `frame_particle_cache` (
  `cache_id` int(11) NOT NULL AUTO_INCREMENT,
  `job_id` int(11) NOT NULL,
  `frame` int(11) NOT NULL,
  `particle_data` longtext NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`cache_id`),
  UNIQUE KEY `job_frame` (`job_id`,`frame`),
  CONSTRAINT `cache_job_fk` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
-- Table: nodes
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `nodes` (
  `node_id` int(11) NOT NULL AUTO_INCREMENT,
  `node_name` varchar(255) NOT NULL,
  `ip_address` varchar(45) NOT NULL,
  `role` enum('master','render','database','storage','monitor','generator') NOT NULL,
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `last_heartbeat` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `cpu_cores` int(11) NOT NULL,
  `memory_gb` float NOT NULL DEFAULT 0,
  PRIMARY KEY (`node_id`),
  KEY `role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
-- Table: work_threads
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `work_threads` (
  `thread_id` int(11) NOT NULL AUTO_INCREMENT,
  `node_id` int(11) NOT NULL,
  `job_id` int(11) NOT NULL,
  `frame_id` int(11) NOT NULL,
  `status` enum('queued','processing','completed') DEFAULT 'queued',
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`thread_id`),
  KEY `node_id` (`node_id`),
  KEY `job_id` (`job_id`),
  KEY `frame_id` (`frame_id`),
  KEY `job_frame` (`job_id`, `frame_id`),
  CONSTRAINT `wt_node_fk` FOREIGN KEY (`node_id`) REFERENCES `nodes` (`node_id`) ON DELETE CASCADE,
  CONSTRAINT `wt_job_fk` FOREIGN KEY (`job_id`) REFERENCES `render_jobs` (`job_id`) ON DELETE CASCADE,
  CONSTRAINT `wt_frame_fk` FOREIGN KEY (`job_id`, `frame_id`) REFERENCES `frames` (`job_id`, `frame_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
-- Views (optional)
-- --------------------------------------------------------
CREATE OR REPLACE VIEW `view_frame_status` AS
SELECT f.frame_id, rj.job_name, f.status AS frame_status,
       f.started_at, f.completed_at,
       TIMESTAMPDIFF(SECOND, f.started_at, f.completed_at) AS time_to_complete
FROM frames f
JOIN render_jobs rj ON f.job_id = rj.job_id;

CREATE OR REPLACE VIEW `view_job_summary` AS
SELECT rj.job_id, rj.job_name, rj.status AS job_status,
       COUNT(f.frame_id) AS total_frames,
       SUM(CASE WHEN f.status = 'rendered' THEN 1 ELSE 0 END) AS rendered_frames,
       SUM(CASE WHEN f.status = 'pending' THEN 1 ELSE 0 END) AS pending_frames,
       SUM(CASE WHEN f.status = 'in progress' THEN 1 ELSE 0 END) AS in_progress_frames,
       rj.created_at
FROM render_jobs rj
LEFT JOIN frames f ON rj.job_id = f.job_id
GROUP BY rj.job_id, rj.job_name, rj.status, rj.created_at;

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;