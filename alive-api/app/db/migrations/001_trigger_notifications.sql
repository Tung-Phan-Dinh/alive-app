-- Migration: Add trigger_events and notifications tables
-- Run this against your alive_app database

USE alive_app;

-- Trigger events: tracks each time a user misses their deadline
CREATE TABLE trigger_events (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,

  -- When the trigger was detected
  triggered_at DATETIME NOT NULL,

  -- The deadline that was missed (last_active_at + checkin_period_hours)
  deadline_at DATETIME NOT NULL,

  -- When user checked in again (resurrection)
  resolved_at DATETIME NULL,

  -- Status of this trigger event
  status ENUM('triggered', 'resolved') NOT NULL DEFAULT 'triggered',

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  KEY idx_trigger_events_user_id (user_id),
  KEY idx_trigger_events_status (status),
  KEY idx_trigger_events_user_status (user_id, status),

  CONSTRAINT fk_trigger_events_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- Notifications: tracks each email/SMS sent for a trigger event
CREATE TABLE notifications (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  trigger_event_id BIGINT UNSIGNED NOT NULL,
  contact_id BIGINT UNSIGNED NOT NULL,

  -- Channel used (email, sms in future)
  channel ENUM('email', 'sms') NOT NULL DEFAULT 'email',

  -- Recipient address (denormalized for audit trail)
  recipient_address VARCHAR(254) NOT NULL,

  -- When notification was sent
  sent_at DATETIME NULL,

  -- Status of the notification
  status ENUM('pending', 'sent', 'failed') NOT NULL DEFAULT 'pending',

  -- Error message if failed
  error_text TEXT NULL,

  -- Retry count
  retry_count INT NOT NULL DEFAULT 0,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),

  -- Prevent duplicate notifications for same trigger event + contact + channel
  UNIQUE KEY uq_notification_trigger_contact_channel (trigger_event_id, contact_id, channel),

  KEY idx_notifications_trigger_event (trigger_event_id),
  KEY idx_notifications_contact (contact_id),
  KEY idx_notifications_status (status),

  CONSTRAINT fk_notifications_trigger_event
    FOREIGN KEY (trigger_event_id) REFERENCES trigger_events(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_notifications_contact
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- Add index on users for efficient trigger detection query
CREATE INDEX idx_users_trigger_check
  ON users(is_dead, last_active_at, checkin_period_hours);
