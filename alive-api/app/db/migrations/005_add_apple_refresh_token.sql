-- Migration: Add apple_refresh_token to users table
-- Required for Apple Sign-In token revocation during account deletion

ALTER TABLE users
ADD COLUMN apple_refresh_token VARCHAR(512) NULL AFTER provider_id;

-- Index not needed since we only look up by user_id, not by token
