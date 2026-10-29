-- Migration 005: Expand membership_status check constraint to include 'terminated'
-- Allows Owner to terminate memberships when needed

ALTER TABLE members DROP CONSTRAINT IF EXISTS members_membership_status_check;
ALTER TABLE members ADD CONSTRAINT members_membership_status_check CHECK (membership_status IN ('active', 'inactive', 'suspended', 'expired', 'pending', 'terminated'));
