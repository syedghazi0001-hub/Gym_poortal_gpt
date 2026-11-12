# PythonAnywhere Deployment Guide — Vanguard Gym OS

This guide provides step-by-step instructions for deploying Vanguard Gym OS on **PythonAnywhere** using their WSGI web hosting model.

---

## 1. Prerequisites

- A [PythonAnywhere](https://www.pythonanywhere.com/) account (Free Beginner or Hacker tier).
- A Supabase PostgreSQL database URL (see `SUPABASE_SETUP.md`).

---

## 2. Clone the Repository on PythonAnywhere

1. Log in to PythonAnywhere.
2. Go to the **Consoles** tab and open a **Bash console**.
3. Clone your repository into your home directory:
   ```bash
   cd ~
   git clone https://github.com/your-username/gym-management.git
   cd gym-management
   ```

---

## 3. Set Up Virtual Environment & Dependencies

In your PythonAnywhere Bash console:

```bash
# Create a virtual environment using Python 3.11 or 3.12
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip and install application dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Configure Production Environment Variables

Create your `.env` file in `/home/<your-username>/gym-management/.env`:

```bash
cp .env.example .env
nano .env
```

Add your production secrets:
```ini
SECRET_KEY=replace-with-a-random-32-character-secret-key
DATABASE_URL=postgresql://postgres.yourprojectref:yourpassword@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
GYM_TIMEZONE=Asia/Karachi
FLASK_ENV=production
```
Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## 5. Configure the Web App in PythonAnywhere Dashboard

1. Navigate to the **Web** tab in the PythonAnywhere top navigation.
2. Click **Add a new web app**.
3. Choose **Manual configuration** (do NOT choose the default Flask template; we use an existing codebase).
4. Select **Python 3.11** (matching your virtual environment).
5. Complete the wizard.

### Configure Virtualenv & Paths
In the Web tab configuration screen:
- **Source code**: `/home/<your-username>/gym-management`
- **Working directory**: `/home/<your-username>/gym-management`
- **Virtualenv**: `/home/<your-username>/gym-management/venv`

### Configure Static Files Mapping
Under the **Static files** section, add the mapping so CSS, JS, and SVG assets are served directly by PythonAnywhere's high-speed web server:
- **URL**: `/static/`
- **Directory**: `/home/<your-username>/gym-management/static`

---

## 6. Configure the WSGI Configuration File

1. In the Web tab, click the link to your **WSGI configuration file** (e.g., `/var/www/yourusername_pythonanywhere_com_wsgi.py`).
2. Delete the default boilerplate code and paste the following:

```python
import sys
import os

# 1. Add project directory to python search path
project_home = '/home/<your-username>/gym-management'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 2. Load production environment variables from .env
from dotenv import load_dotenv
env_path = os.path.join(project_home, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# 3. Import Flask application factory
from app import create_app
application = create_app()
```
*(Replace `<your-username>` with your actual PythonAnywhere username).*

3. Click **Save** at the top right.

---

## 7. Reload and Launch Your Web App

1. Go back to the **Web** tab.
2. Click the green **Reload <your-username>.pythonanywhere.com** button.
3. Open your browser to `https://<your-username>.pythonanywhere.com`.
4. If no owner account exists yet, you will automatically be greeted by the **Initial Setup Wizard** at `/setup`. Complete the form to set your master gym owner password and launch your gym portal!

---

## 8. Automated 10-Day Absence Checks (Scheduled Tasks)

### On PythonAnywhere Hacker/Paid Plans:
1. Navigate to the **Tasks** tab.
2. Under **Scheduled tasks**, set a task to run daily at `00:00` UTC:
   ```bash
   /home/<your-username>/gym-management/venv/bin/python /home/<your-username>/gym-management/scripts/check_absence.py
   ```
3. Click **Create**.

### On PythonAnywhere Free Beginner Plan (Cron Alternative):
PythonAnywhere Free tier does not include unlimited automated cron tasks.
**Solution implemented in Vanguard Gym OS:**
We built a **safe, throttled absence evaluation engine** that automatically evaluates absence whenever the gym owner logs in or views the owner dashboard (throttled to at most once per hour). This ensures 10-day absence alerts are generated reliably without requiring any paid background worker or scheduled task!

---

## 9. Understanding Free Plan Limitations

If you are running on the free Beginner plan of PythonAnywhere:
1. **Outbound Network Whitelist**: PythonAnywhere Free accounts only permit outbound HTTP/HTTPS requests to approved sites on their allowlist (`.supabase.co` is officially allowlisted). Direct raw TCP port 5432 connections to external databases are restricted to paid tiers. If you encounter `connection refused` on port 5432, connect via Supabase's HTTP/HTTPS endpoint or upgrade to PythonAnywhere's $5/mo plan.
2. **CPU Quota**: Free accounts receive 100 CPU-seconds/day. Vanguard Gym OS is lightweight and typically consumes less than 2–3 CPU-seconds per 500 requests.
3. **Web Worker**: Free accounts run on 1 worker thread. The database connection pool is conservatively capped at 10 connections to keep memory usage low.
