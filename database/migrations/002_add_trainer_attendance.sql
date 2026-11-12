-- ============================================================================
-- MIGRATION 002: Add Trainer Attendance & Duty Shift Tracking Table
-- Run this in your Supabase SQL Editor if you already had an existing database!
-- ============================================================================

CREATE TABLE IF NOT EXISTS trainer_attendance (
    id VARCHAR(36) PRIMARY KEY,
    trainer_id VARCHAR(36) NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    check_in_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    check_out_time TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'present' CHECK (status IN ('present', 'late', 'excused', 'half_day')),
    method VARCHAR(30) NOT NULL DEFAULT 'desk_terminal' CHECK (method IN ('desk_terminal', 'qr_scan', 'manual', 'self')),
    recorded_by_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_trainer_attendance_per_day UNIQUE (trainer_id, attendance_date)
);

CREATE INDEX IF NOT EXISTS idx_trainer_att_date ON trainer_attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_trainer_att_trainer_id ON trainer_attendance(trainer_id);
