-- ============================================================================
-- MIGRATION 004: Update attendance_method_check Constraint
-- Resolves check constraint violation on reverse QR self-scanning
-- ============================================================================

DO $$
BEGIN
    -- Drop existing check constraint if it exists
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'attendance_method_check'
    ) THEN
        ALTER TABLE attendance DROP CONSTRAINT attendance_method_check;
    END IF;

    -- Re-add check constraint supporting QR, MANUAL, SELF_QR, qr_scan, desk_terminal
    ALTER TABLE attendance ADD CONSTRAINT attendance_method_check 
        CHECK (method IN ('QR', 'MANUAL', 'SELF_QR', 'qr_scan', 'desk_terminal'));
END $$;
