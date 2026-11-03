# Vanguard Gym OS — Premium Gym Management Portal

A modern, high-performance, dark-themed **Gym Management System** built from the ground up for gym owners, front-desk receptionists, personal trainers, and gym members.

Engineered with **Python (Flask)**, a **Supabase PostgreSQL** relational backend, and modern **HTML5 / CSS / Vanilla JS** with zero heavy build tool requirements. Designed for seamless WSGI deployment on **PythonAnywhere** and scalable cloud hosting.

---

## 🌟 Key Highlights & Design Philosophy

- **Sophisticated Dark Theme**: Deep charcoal (`#121721`), graphite (`#181F2D`), and near-black (`#0A0D12`) surfaces with controlled muted emerald green (`#10B981`) accents. No flat black sheets, no oversaturated neon.
- **Strict Server-Side Authorization**: Real security enforced via server-side `@role_required` decorators and database constraints, not merely hiding UI buttons.
- **True Database Operations**: All metrics, charts, attendance records, and payment transactions are calculated live from PostgreSQL with zero fake/mock numbers.
- **Duplicate Prevention at DB Level**:
  - Same-day duplicate check-in blocked by `UNIQUE (member_id, attendance_date)`.
  - Same-month duplicate fee recording blocked by `UNIQUE (member_id, billing_month)`.
- **Ten-Day Absence Engine**: Automatic detection of active members who have missed 10+ consecutive calendar days, dispatching owner alert cards and personalized Urdu warning banners to member portals.
- **Zero Heavy Frontend Dependencies**: Native HTML5 camera QR scanning, lightweight crisp SVG/Canvas data visualizers, and Web Audio API synthesizer for instant scan feedback.

---

## 👥 User Roles & Access Control

| Role | Permitted Operations | Restricted From |
| :--- | :--- | :--- |
| **Owner** | Full admin command center, register/edit members, create trainers/receptionists, toggle staff access, fee ledger & reversal, absence alert center, gym branding & settings. | Cannot bypass audit trails. |
| **Receptionist** | Front-desk camera QR scanner, daily check-in logs, manual attendance search, mark monthly membership dues as paid, view member status. | Cannot create accounts, cannot view owner financial profit reports or modify gym settings. |
| **Trainer** | View assigned trainees, trainee attendance streak/history, log coaching and workout notes. | Cannot view gym financial ledgers or members assigned to other trainers. |
| **Member** | View digital membership QR pass (printable), check-in history, streak counter, payment history, 10-day absence notice banner, coach notes. | Strictly isolated: cannot view any other member's data or management screens. |

---

## 🏗️ Architecture & Technical Stack

- **Backend Framework**: Python 3.11+ / Flask 3.1
- **WSGI Compatibility**: Native WSGI (`wsgi.py`) for PythonAnywhere, Gunicorn, uWSGI.
- **Database**: Supabase PostgreSQL (Postgres 15/16/17) with Foreign Keys, Check Constraints, Unique Indexes, and Row Level Security (RLS).
- **Authentication**: Werkzeug secure password hashing (PBKDF2/SHA256 & Scrypt), session cookies (`HttpOnly`, `SameSite=Lax`).
- **QR Engine**: Cryptographically random unique tokens (`GYM-XXXXXXXXXXXXXXXX`), server-side generation of high-DPI base64 PNG badges.
- **Frontend**: Clean semantic HTML5, CSS custom properties (`var(--accent-primary)`), lightweight Vanilla JS. Accessible with full `@media (prefers-reduced-motion)` support.

---

## 📁 Project Structure

```
gym-management/
├── app.py                      # Application factory & Blueprint registration
├── wsgi.py                     # PythonAnywhere WSGI entrypoint
├── config.py                   # Environment configuration & defaults
├── requirements.txt            # Python dependencies
├── .env.example                # Template for environment secrets
├── database/
│   ├── connection.py           # Thread-safe PostgreSQL pool & query execution
│   └── schema.sql              # Supabase PostgreSQL schema with RLS & indexes
├── auth/
│   ├── decorators.py           # @login_required, @role_required, user context
│   └── security.py             # Password hashing, CSRF tokens, UUID/QR generators
├── services/
│   ├── auth_service.py         # Initial setup wizard & authentication
│   ├── member_service.py       # Member CRUD, QR generation, status management
│   ├── staff_service.py        # Trainer & Receptionist management
│   ├── attendance_service.py   # QR verification, duplicate check, streak calculations
│   ├── payment_service.py      # Monthly payments, duplicate prevention, receipts
│   ├── absence_service.py      # 10-day absence evaluation & alert engine
│   └── notification_service.py # Role-isolated user notifications
├── routes/
│   ├── auth_routes.py          # /setup, /login, /logout, /change-password
│   ├── owner_routes.py         # Dashboard, members, staff, payments, alerts, settings
│   ├── receptionist_routes.py  # Desk scanner terminal, check-in, fee collection
│   ├── trainer_routes.py       # Trainer coaching hub & trainee progress
│   ├── member_routes.py        # Member personal pass, history, dues
│   └── api_routes.py           # JSON endpoints for scanner, search, charts
├── templates/                  # Premium dark Jinja2 templates for all roles
├── static/
│   ├── css/                    # Modular CSS (main.css, components.css, animations.css)
│   ├── js/                     # Client scripts (app.js, scanner.js, charts.js)
│   └── images/logo.svg         # Minimalist vector brand mark
├── scripts/
│   ├── check_absence.py        # PythonAnywhere CLI / Cron absence check script
│   └── seed_demo_data.py       # Realistic demonstration data generator
├── tests/                      # Full automated test suite (100% pass)
├── SUPABASE_SETUP.md           # Step-by-step Supabase database deployment guide
└── PYTHONANYWHERE_DEPLOYMENT.md# PythonAnywhere hosting & WSGI configuration guide
```

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Python 3.10+
- PostgreSQL or Supabase project

### 2. Setup Virtual Environment & Install Dependencies
```bash
git clone <repo-url> gym-management
cd gym-management
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and configure your database URI:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
SECRET_KEY=your-secure-secret-key-min-32-chars
DATABASE_URL=postgresql://gym_user:gym_secure_pass_2026@127.0.0.1:5432/gym_portal
GYM_TIMEZONE=Asia/Karachi
```

### 4. Optional: Populate Demo Data
To instantly test the system with preconfigured owner, trainers, receptionists, members, check-ins, and absence alerts:
```bash
python3 scripts/seed_demo_data.py
```

### 5. Run the Application
```bash
python3 app.py
```
Open your browser at `http://localhost:5000`.

---

## 🧪 Automated Testing

The system includes a 100% passing automated test suite covering authentication, permissions, duplicate QR scans, duplicate payments, 10-day absence alerts, and data isolation:

```bash
pytest tests/ -v
```

Test coverage includes:
- `tests/test_auth.py`: Initial one-time setup, login, password security, session expiry.
- `tests/test_owner.py`: Member CRUD, trainer/receptionist creation, trainer assignment.
- `tests/test_attendance.py`: Valid QR scan, duplicate scan rejection (409), inactive member rejection, manual search check-in.
- `tests/test_payments.py`: Monthly fee recording, duplicate month prevention, paid vs pending calculation, audit trail reversal.
- `tests/test_absence.py`: 10-day consecutive absence calculation, owner notification, member warning text in Urdu, automatic resolution upon check-in.
- `tests/test_isolation.py`: Strict cross-role isolation (trainer cannot access unassigned trainees, members cannot view management records).

---

## 🔑 Demo Credentials (When Seeded)

| Role | Username | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Owner** | `owner` | `OwnerPassword123!` | Full admin access |
| **Receptionist** | `receptionist` | `ReceptionPassword123!` | Scanner & payment collection |
| **Trainer 1** | `coach.hamza` | `CoachPassword123!` | Strength coach with assigned trainees |
| **Trainer 2** | `coach.bilal` | `CoachPassword123!` | Conditioning coach |
| **Member 1** | `zubair` | `MemberPassword123!` | VIP member, regular attendee, paid |
| **Member 2** | `usman` | `MemberPassword123!` | Standard member, fee pending |
| **Member 3** | `kamran` | `MemberPassword123!` | Active 14-day absence alert |

*(Note: In production, the initial setup wizard at `/setup` prompts the owner to set their own master credentials; no default passwords exist).*
