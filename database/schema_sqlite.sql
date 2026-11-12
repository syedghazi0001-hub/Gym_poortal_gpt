-- ============================================================================
-- VANGUARD GYM OS - SQLITE SCHEMA (FOR PYTHONANYWHERE FREE TIER TESTING)
-- ============================================================================

PRAGMA foreign_keys = ON;

-- 1. GYM SETTINGS
CREATE TABLE IF NOT EXISTS gym_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    gym_name TEXT NOT NULL DEFAULT 'Vanguard Fitness Club',
    gym_tagline TEXT DEFAULT 'Premium Strength & Performance Gym',
    currency TEXT NOT NULL DEFAULT 'PKR',
    timezone TEXT NOT NULL DEFAULT 'Asia/Karachi',
    accent_color TEXT NOT NULL DEFAULT '#10B981',
    contact_phone TEXT DEFAULT '+92 300 1234567',
    contact_email TEXT DEFAULT 'admin@vanguardfitness.com',
    address TEXT DEFAULT 'Main Boulevard, Sports Complex, Jalalpur Jattan',
    absence_threshold_days INTEGER NOT NULL DEFAULT 10,
    terminal_qr_token TEXT DEFAULT 'VANGUARD-TERMINAL-DESK-STATION',
    last_absence_check_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. USERS
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'receptionist', 'trainer', 'member')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- 3. PROFILES
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    avatar_color TEXT DEFAULT '#10B981',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. TRAINERS
CREATE TABLE IF NOT EXISTS trainers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    specialization TEXT DEFAULT 'General Fitness & Strength',
    bio TEXT,
    hire_date DATE DEFAULT (DATE('now')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. RECEPTIONISTS
CREATE TABLE IF NOT EXISTS receptionists (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    shift TEXT DEFAULT 'Morning',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. MEMBERS
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    member_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    dob DATE,
    emergency_contact TEXT,
    membership_plan TEXT NOT NULL DEFAULT 'Monthly Standard',
    membership_start_date DATE NOT NULL,
    membership_end_date DATE NOT NULL,
    monthly_fee REAL NOT NULL DEFAULT 5000.0,
    membership_status TEXT NOT NULL DEFAULT 'active' CHECK (membership_status IN ('active', 'inactive', 'suspended', 'expired', 'pending', 'terminated')),
    assigned_trainer_id TEXT REFERENCES trainers(id) ON DELETE SET NULL,
    qr_token TEXT NOT NULL UNIQUE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. ATTENDANCE
CREATE TABLE IF NOT EXISTS attendance (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    check_in_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    check_out_time TIMESTAMP,
    recorded_by_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    method TEXT NOT NULL DEFAULT 'QR' CHECK (method IN ('QR', 'MANUAL', 'SELF_QR')),
    status TEXT NOT NULL DEFAULT 'present' CHECK (status IN ('present', 'late', 'excused')),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_member_attendance_per_day UNIQUE (member_id, attendance_date)
);

-- 7B. TRAINER ATTENDANCE
CREATE TABLE IF NOT EXISTS trainer_attendance (
    id TEXT PRIMARY KEY,
    trainer_id TEXT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    check_in_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    check_out_time TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'present' CHECK (status IN ('present', 'late', 'excused', 'half_day')),
    method TEXT NOT NULL DEFAULT 'desk_terminal' CHECK (method IN ('desk_terminal', 'qr_scan', 'manual', 'self')),
    recorded_by_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_trainer_attendance_per_day UNIQUE (trainer_id, attendance_date)
);

-- 8. PAYMENTS
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    billing_month TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'PKR',
    payment_date DATE NOT NULL DEFAULT (DATE('now')),
    payment_method TEXT NOT NULL DEFAULT 'cash' CHECK (payment_method IN ('cash', 'bank_transfer', 'card', 'easypaisa_jazzcash', 'other')),
    status TEXT NOT NULL DEFAULT 'paid' CHECK (status IN ('paid', 'refunded', 'reversed')),
    receipt_number TEXT NOT NULL UNIQUE,
    recorded_by_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_member_payment_per_month UNIQUE (member_id, billing_month)
);

-- 9. ABSENCE ALERTS
CREATE TABLE IF NOT EXISTS absence_alerts (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    last_attendance_date DATE,
    consecutive_days_absent INTEGER NOT NULL,
    alert_date DATE NOT NULL DEFAULT (DATE('now')),
    is_resolved INTEGER NOT NULL DEFAULT 0,
    resolved_date DATE,
    acknowledged_by_owner INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 10. TRAINER NOTES
CREATE TABLE IF NOT EXISTS trainer_notes (
    id TEXT PRIMARY KEY,
    trainer_id TEXT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
    member_id TEXT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. NOTIFICATIONS
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('absence', 'payment', 'membership', 'system', 'announcement')),
    is_read INTEGER NOT NULL DEFAULT 0,
    read_at TIMESTAMP,
    link_url TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 12. AUDIT LOGS
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    username TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 13. GYM EQUIPMENT & MACHINES DIRECTORY
CREATE TABLE IF NOT EXISTS equipment (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    target_muscle TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'operational' CHECK (status IN ('operational', 'maintenance', 'out_of_order')),
    description TEXT,
    instructions TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- INDEXES
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_members_code ON members(member_code);
CREATE INDEX IF NOT EXISTS idx_members_qr ON members(qr_token);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_payments_month ON payments(billing_month);
