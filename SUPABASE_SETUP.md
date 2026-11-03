# Supabase PostgreSQL Setup Guide — Vanguard Gym OS

This guide walks you through connecting Vanguard Gym OS to a **Supabase PostgreSQL** cloud database.

---

## 1. Create a Supabase Project

1. Visit [https://supabase.com](https://supabase.com) and create an account or sign in.
2. Click **New Project**.
3. Choose an Organization, enter your project details:
   - **Name**: `vanguard-gym-db` (or your gym's name)
   - **Database Password**: Choose a strong, secure password (save this safely; you will need it for `DATABASE_URL`).
   - **Region**: Choose the closest AWS region to your gym (e.g., *Singapore*, *Frankfurt*, or *Mumbai* for South Asia).
4. Click **Create new project** and wait 1–2 minutes for provisioning.

---

## 2. Obtain Your PostgreSQL Connection String

1. In your Supabase project dashboard, navigate to **Project Settings** (gear icon at bottom-left) → **Database**.
2. Scroll to the **Connection strings** section.
3. Select the **URI** tab. You have two options:

### Option A: Session Connection Pooler (Recommended for PythonAnywhere WSGI)
```
postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```
*Why? The session pooler on port 6543 handles ephemeral WSGI web workers efficiently without exceeding Supabase's max connection limits.*

### Option B: Direct Connection
```
postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```
*Note: Direct connections require SSL (`?sslmode=require`), which Vanguard Gym OS automatically enables for remote hosts.*

---

## 3. Apply the Database Migrations

You can apply the complete database schema in one of two ways:

### Method 1: Using the Supabase Dashboard SQL Editor (Easiest)
1. In your Supabase dashboard, click **SQL Editor** in the left sidebar.
2. Click **New Query**.
3. Open `database/schema.sql` from this repository.
4. Copy the entire file contents and paste them into the Supabase SQL Editor.
5. Click **Run** (or `Cmd/Ctrl + Enter`).
6. You will see `Success: No rows returned`. All 12 tables, indexes, check constraints, and RLS policies are now initialized!

### Method 2: Automatic Initialization from Python
Vanguard Gym OS automatically runs `init_db()` upon application startup if tables do not exist. Once your `DATABASE_URL` is set in `.env`, starting the app will verify the schema.

---

## 4. Environment Variables Configuration

In your production `.env` file (e.g. on PythonAnywhere or your server), add your Supabase credentials:

```ini
# Flask Security Key
SECRET_KEY=generate-a-random-32-character-secret

# Supabase PostgreSQL Connection URI
DATABASE_URL=postgresql://postgres.yourprojectref:yourpassword@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# Supabase REST API (Optional fallback for PythonAnywhere Free Tier)
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-supabase-service-role-key

# Gym Local Timezone
GYM_TIMEZONE=Asia/Karachi
```

> **Security Rule**: Keep your `SUPABASE_KEY` (service-role secret key) strictly on the server in `.env`. Never expose it in client-side HTML, GitHub repositories, or JavaScript!

---

## 5. Supabase Free Tier Limitations & Considerations

| Resource | Free Tier Quota | Impact on Gym Management System |
| :--- | :--- | :--- |
| **Database Storage** | 500 MB | More than sufficient for 10,000+ members and 5+ years of daily check-ins and receipts. |
| **Active Projects** | 2 projects | One for production gym portal, one optional for testing. |
| **Inactivity Pausing** | Pauses after 7 days of inactivity | Free projects pause if no queries occur for 7 days. For an active gym, daily member check-ins prevent pausing. If paused, click **Restore** in the dashboard. |
| **Direct Connections** | ~60 direct connection pool | Handled cleanly by Vanguard's connection pooler (`ThreadedConnectionPool(minconn=1, maxconn=10)`). |
| **Monthly Active Users** | 50,000 MAU | Gym members and staff will easily fit within this generous limit. |

---

## 6. Verifying Database Health

To verify your Supabase database connectivity from the command line:

```bash
python3 -c "
from database.connection import check_db_health, query_one
print('Connection Healthy:', check_db_health())
print('Gym Settings:', query_one('SELECT * FROM gym_settings WHERE id = 1;'))
"
```
You should see:
```
Connection Healthy: True
Gym Settings: {'id': 1, 'gym_name': 'Vanguard Fitness Club', ...}
```
