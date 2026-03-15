-- Migration: Change email uniqueness to allow same email with different auth providers
-- Run this against your alive_app database

USE alive_app;

-- Drop the single-column email unique constraint
ALTER TABLE users DROP INDEX uq_users_email;

-- Add composite unique constraint: same email allowed with different providers
-- This allows: (test@gmail.com, google) AND (test@gmail.com, apple) to coexist
ALTER TABLE users ADD UNIQUE KEY uq_users_email_provider (email, auth_provider);
