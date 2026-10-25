-- ============================================================================
-- GYM MANAGEMENT PORTAL - SUPABASE POSTGRESQL SCHEMA
-- Designed for Supabase PostgreSQL & Python WSGI Deployments
-- ============================================================================

-- Ensure pgcrypto or uuid-ossp for secure random UUID generation if needed
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. GYM SETTINGS (Singleton configuration table)
CREATE TABLE IF NOT EXISTS gym_settings (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    gym_name VARCHAR(120) NOT NULL DEFAULT 'Vanguard Fitness Club',
    gym_tagline VARCHAR(200) DEFAULT 'Premium Strength & Performance Gym',
    currency VARCHAR(10) NOT NULL DEFAULT 'PKR',
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Karachi',
    accent_color VARCHAR(10) NOT NULL DEFAULT '#10B981',
    contact_phone VARCHAR(40) DEFAULT '+92 300 1234567',
    contact_email VARCHAR(120) DEFAULT 'admin@vanguardfitness.com',
    address TEXT DEFAULT 'Main Boulevard, Sports Complex, Jalalpur Jattan',
    absence_threshold_days INT NOT NULL DEFAULT 10,
    last_absence_check_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. USERS (Core authentication & role-based access)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('owner', 'receptionist', 'trainer', 'member')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMPTZ
);

-- 3. PROFILES (General user profile details)
CREATE TABLE IF NOT EXISTS profiles (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(120) NOT NULL,
    phone VARCHAR(40) NOT NULL,
    email VARCHAR(120),
    avatar_color VARCHAR(20) DEFAULT '#10B981',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. TRAINERS (Staff - Trainers)
CREATE TABLE IF NOT EXISTS trainers (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(120) NOT NULL,
    phone VARCHAR(40) NOT NULL,
    email VARCHAR(120),
    specialization VARCHAR(120) DEFAULT 'General Fitness & Strength',
    bio TEXT,
    hire_date DATE DEFAULT CURRENT_DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. RECEPTIONISTS (Staff - Front Desk)
CREATE TABLE IF NOT EXISTS receptionists (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(120) NOT NULL,
    phone VARCHAR(40) NOT NULL,
    email VARCHAR(120),
    shift VARCHAR(40) DEFAULT 'Morning',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. MEMBERS (Customers / Gym Members)
CREATE TABLE IF NOT EXISTS members (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    member_code VARCHAR(30) NOT NULL UNIQUE,
    full_name VARCHAR(120) NOT NULL,
    phone VARCHAR(40) NOT NULL,
    email VARCHAR(120),
    dob DATE,
    emergency_contact VARCHAR(80),
    membership_plan VARCHAR(60) NOT NULL DEFAULT 'Monthly Standard',
    membership_start_date DATE NOT NULL,
    membership_end_date DATE NOT NULL,
    monthly_fee NUMERIC(10,2) NOT NULL DEFAULT 5000.00,
    membership_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (membership_status IN ('active', 'inactive', 'suspended', 'expired')),
    assigned_trainer_id VARCHAR(36) REFERENCES trainers(id) ON DELETE SET NULL,
    qr_token VARCHAR(64) NOT NULL UNIQUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. ATTENDANCE (Daily check-ins with duplicate prevention)
CREATE TABLE IF NOT EXISTS attendance (
    id VARCHAR(36) PRIMARY KEY,
    member_id VARCHAR(36) NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    check_in_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recorded_by_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    method VARCHAR(20) NOT NULL DEFAULT 'QR' CHECK (method IN ('QR', 'MANUAL')),
    status VARCHAR(20) NOT NULL DEFAULT 'present' CHECK (status IN ('present', 'late', 'excused')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_member_attendance_per_day UNIQUE (member_id, attendance_date)
);

-- 8. PAYMENTS (Monthly fee collections with duplicate billing period prevention)
CREATE TABLE IF NOT EXISTS payments (
    id VARCHAR(36) PRIMARY KEY,
    member_id VARCHAR(36) NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    billing_month VARCHAR(7) NOT NULL, -- Format: YYYY-MM
    amount NUMERIC(10,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'PKR',
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    payment_method VARCHAR(30) NOT NULL DEFAULT 'cash' CHECK (payment_method IN ('cash', 'bank_transfer', 'card', 'easypaisa_jazzcash', 'other')),
    status VARCHAR(20) NOT NULL DEFAULT 'paid' CHECK (status IN ('paid', 'refunded', 'reversed')),
    receipt_number VARCHAR(40) NOT NULL UNIQUE,
    recorded_by_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_member_payment_per_month UNIQUE (member_id, billing_month)
);

-- 9. ABSENCE ALERTS (10-day consecutive absence tracking)
CREATE TABLE IF NOT EXISTS absence_alerts (
    id VARCHAR(36) PRIMARY KEY,
    member_id VARCHAR(36) NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    last_attendance_date DATE,
    consecutive_days_absent INT NOT NULL,
    alert_date DATE NOT NULL DEFAULT CURRENT_DATE,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_date DATE,
    acknowledged_by_owner BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 10. TRAINER NOTES (Workout / progress notes by trainers)
CREATE TABLE IF NOT EXISTS trainer_notes (
    id VARCHAR(36) PRIMARY KEY,
    trainer_id VARCHAR(36) NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
    member_id VARCHAR(36) NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. NOTIFICATIONS (Role-based alerts & inbox)
CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    category VARCHAR(30) NOT NULL CHECK (category IN ('absence', 'payment', 'membership', 'system', 'announcement')),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    link_url VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 12. AUDIT LOGS (Security & compliance trail)
CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(80),
    action VARCHAR(80) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(50),
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PERFORMANCE INDEXES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_members_code ON members(member_code);
CREATE INDEX IF NOT EXISTS idx_members_qr_token ON members(qr_token);
CREATE INDEX IF NOT EXISTS idx_members_status ON members(membership_status);
CREATE INDEX IF NOT EXISTS idx_members_trainer ON members(assigned_trainer_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_attendance_member ON attendance(member_id);
CREATE INDEX IF NOT EXISTS idx_payments_month ON payments(billing_month);
CREATE INDEX IF NOT EXISTS idx_payments_member ON payments(member_id);
CREATE INDEX IF NOT EXISTS idx_absence_unresolved ON absence_alerts(member_id, is_resolved);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) FOR SUPABASE DIRECT CLIENTS
-- ============================================================================
-- Enable RLS on core tables
ALTER TABLE gym_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE trainers ENABLE ROW LEVEL SECURITY;
ALTER TABLE receptionists ENABLE ROW LEVEL SECURITY;
ALTER TABLE members ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE absence_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE trainer_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Note: The Python Flask backend operates with trusted database credentials
-- (Service role or direct PostgreSQL connection) and enforces comprehensive
-- server-side role-based authorization before each query.
-- The policies below safeguard direct Supabase client access.

DROP POLICY IF EXISTS gym_settings_public_read ON gym_settings;
CREATE POLICY gym_settings_public_read ON gym_settings FOR SELECT USING (true);
