-- Migration: Add name field to users table
-- Used in notification emails to identify the user by name instead of email

ALTER TABLE users
ADD COLUMN name VARCHAR(120) NULL AFTER email;
