CREATE DATABASE IF NOT EXISTS alive_app
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'alive_api'@'localhost' IDENTIFIED BY '572Chien';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
ON alive_app.* TO 'alive_api'@'localhost';

FLUSH PRIVILEGES;
EXIT;

USE alive_app;

-- Users table
CREATE TABLE users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email VARCHAR(254) NOT NULL,
  password_hash VARCHAR(255) NULL,

  auth_provider ENUM('local','google','apple') NOT NULL DEFAULT 'local',
  provider_id VARCHAR(255) NULL,

  checkin_period_hours INT NOT NULL DEFAULT 48,
  last_active_at DATETIME NULL,

  alarm_sent_for_date DATETIME NULL,
  is_dead TINYINT(1) NOT NULL DEFAULT 0,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email),
  UNIQUE KEY uq_users_provider (auth_provider, provider_id)
) ENGINE=InnoDB;

-- Contacts table
CREATE TABLE contacts (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,

  name VARCHAR(120) NOT NULL,
  email VARCHAR(254) NULL,
  phone VARCHAR(32) NULL,
  death_message TEXT NULL,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  KEY idx_contacts_user_id (user_id),

  CONSTRAINT fk_contacts_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- Checkins table
CREATE TABLE checkins (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,

  checked_in_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ip_address VARCHAR(45) NULL,

  -- Generated day (based on checked_in_at); stored so it can be indexed/unique
  checkin_date DATE AS (DATE(checked_in_at)) STORED,

  PRIMARY KEY (id),

  KEY idx_checkins_user_time (user_id, checked_in_at),
  UNIQUE KEY uq_checkins_user_date (user_id, checkin_date),

  CONSTRAINT fk_checkins_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;


