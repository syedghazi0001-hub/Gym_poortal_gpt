-- ============================================================================
-- MIGRATION 003: Reverse QR, Check-Out Times, Equipment & Self-Registration
-- ============================================================================

-- 1. Add check_out_time to member attendance if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'attendance' AND column_name = 'check_out_time'
    ) THEN
        ALTER TABLE attendance ADD COLUMN check_out_time TIMESTAMPTZ;
    END IF;
END $$;

-- 2. Add terminal_qr_token to gym_settings if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'gym_settings' AND column_name = 'terminal_qr_token'
    ) THEN
        ALTER TABLE gym_settings ADD COLUMN terminal_qr_token VARCHAR(64) DEFAULT 'VANGUARD-TERMINAL-DESK-STATION';
        UPDATE gym_settings SET terminal_qr_token = 'VANGUARD-TERMINAL-DESK-STATION' WHERE terminal_qr_token IS NULL;
    END IF;
END $$;

-- 3. Gym Equipment & Machines Table
CREATE TABLE IF NOT EXISTS equipment (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'Cardio', 'Chest', 'Back', 'Legs', 'Shoulders', 'Arms', 'Core', 'Free Weights'
    target_muscle VARCHAR(100),
    quantity INT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'operational' CHECK (status IN ('operational', 'maintenance', 'out_of_order')),
    description TEXT,
    instructions TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_equipment_category ON equipment(category);
CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment(status);
