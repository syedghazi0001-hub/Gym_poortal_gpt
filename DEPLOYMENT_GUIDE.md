# VANGUARD GYM OS — COMPLETE DEPLOYMENT & HANDOVER GUIDE
### Beginner-Friendly Deployment Guide for GitHub, Render & Gym Owner Handover

Yeh guide ek complete beginner ke liye step-by-step tayyar ki gayi hai taake aap is project ko bina kisi confusion ke **GitHub par upload karein, Render ke free plan par live chalayein, aur gym owner ke hawale karein**.

---

## 📑 Fehris (Table of Contents)
1. [ZIP Extract Karna](#1-zip-extract-karna)
2. [GitHub Repository Banana Aur Code Upload Karna](#2-github-repository-banana-aur-code-upload-karna)
3. [Render.com Ke Free Plan Par Deploy Karna](#3-rendercom-ke-free-plan-par-deploy-karna)
4. [Build Command Aur Start Command](#4-build-command-aur-start-command)
5. [Environment Variables Configure Karna](#5-environment-variables-configure-karna)
6. [Database Persistence: Data Safe Rakhne Ka Tareeqa](#6-database-persistence-data-safe-rakhne-ka-tareeqa)
7. [Gym Owner Ka Secure Account Banana](#7-gym-owner-ka-secure-account-banana)
8. [Live URL Par Testing Checklist](#8-live-url-par-testing-checklist)
9. [Data Backup Aur Restore Ka Tareeqa](#9-data-backup-aur-restore-ka-tareeqa)
10. [Alternative Free Hosting (PythonAnywhere, Koyeb) & Limitations](#10-alternative-free-hosting-pythonanywhere-koyeb--limitations)

---

## 1. ZIP Extract Karna

1. `Vanguard-Gym-OS.zip` file ko apne computer (Windows / Mac / Linux) par download karein.
2. File par right-click karke **Extract All** (ya `unzip Vanguard-Gym-OS.zip`) karein.
3. Extract karne ke baad aapko `Vanguard-Gym-OS` ka folder milega jisme application ki tamam files mojood hongi:
   - `app.py`, `wsgi.py`, `Procfile`, `runtime.txt`, `requirements.txt`
   - `routes/`, `services/`, `database/`, `templates/`, `static/`, `scripts/`, `tests/`
   - `.env.example`, `.gitignore`, `README.md`

---

## 2. GitHub Repository Banana Aur Code Upload Karna

GitHub par code upload karne ke 2 aasan tareeqay hain:

### Tareeqa A: GitHub Website Par Drag-and-Drop (Bina Kisi Command Ke)
1. [github.com](https://github.com) par login karein.
2. Top right par **+** icon par click karke **New repository** select karein.
3. Repository name likhein: `vanguard-gym-os` (Public ya Private dono chalenge).
4. **Create repository** par click karein.
5. Agle page par **uploading an existing file** ka link hoga, us par click karein.
6. `Vanguard-Gym-OS` folder ki tamam files aur folders ko drag karke drop karein.
7. Neechay **Commit changes** par click karein. Code GitHub par upload ho gaya!

### Tareeqa B: Git Terminal Se Push Karna (Recommended)
Apne terminal ya command prompt mein folder ke andar ja kar yeh commands chalayein:
```bash
cd Vanguard-Gym-OS
git init
git add .
git commit -m "Initial commit - Vanguard Gym OS"
git branch -M main
git remote add origin https://github.com/your-username/vanguard-gym-os.git
git push -u origin main
```

---

## 3. Render.com Ke Free Plan Par Deploy Karna

Render.com par Flask application deploy karne se pehle current free-plan availability aur account verification requirements check karein. Free access ya no-card signup ki guarantee nahi di ja sakti.

1. [render.com](https://render.com) par jayen aur **Sign Up with GitHub** karein (Free account, koi credit card zaroori nahi).
2. Dashboard par top right par **New +** button dabayein aur **Web Service** select karein.
3. **Build and deploy from a Git repository** choose karein aur **Next** karein.
4. Apni GitHub repository (`vanguard-gym-os`) ko connect karein.
5. Settings form samne aayega:
   - **Name**: `vanguard-gym-portal` (ya apne gym ka naam)
   - **Region**: Closest region select karein (e.g. *Frankfurt* ya *Singapore*)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Instance Type**: Select **Free ($0/month)**

---

## 4. Build Command Aur Start Command

Render ke settings page par yeh exact commands enter karein:

| Field | Exact Value |
| :--- | :--- |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn wsgi:application` |

*(Note: `wsgi:application` hamare project ki `wsgi.py` file mein mojood Flask factory callable `application` ko run karta hai).*

---

## 5. Environment Variables Configure Karna

Usi page par neechay scroll karein aur **Environment Variables** section mein **Add Environment Variable** par click karke yeh values daalein:

| Key | Value | Explanation |
| :--- | :--- | :--- |
| `SECRET_KEY` | Apni machine par `python -c "import secrets; print(secrets.token_hex(32))"` chala kar generate ki hui unique value | Is value ko private rakhein; GitHub par commit na karein. |
| `FLASK_ENV` | `production` | Production mode active karne ke liye. |
| `GYM_TIMEZONE` | `Asia/Karachi` | Gym ka local timezone (dates aur attendance ke liye). |
| `DATABASE_URL` | *(See Section 6 below)* | Database connection URI (permanent data safe rakhne ke liye). |

Ab neechay green button **Deploy Web Service** par click karein!
Render 2 se 3 minute mein build complete karke aapko live HTTPS link de dega:
`https://vanguard-gym-portal.onrender.com`

---

## 6. Database Persistence: Data Safe Rakhne Ka Tareeqa

### ⚠️ Zaroori Technical Haqeeqat (Data Loss Se Bachne Ke Liye):
Render ke Free Web Service par **local filesystem ephemeral (arzi) hota hai**. Iska matlab yeh hai ke agar aap sirf local SQLite file (`gym_portal.db`) use karenge, to Render jab 15 minute baad sleep mode mein jayega ya restart hoga, to local file reset ho sakti hai!

### ✅ 100% Permanent Data Solution (Free Managed PostgreSQL):
Vanguard Gym OS mein built-in **PostgreSQL connection pool** mojood hai. Render ya Supabase par PostgreSQL attach karne se ephemeral local filesystem par depend karne ka risk kam hota hai. Free-tier availability, retention aur backups provider ki current terms par depend karte hain; independent backups phir bhi rakhein:

#### Option 1: Supabase Free PostgreSQL (Recommended — Lifetime Free 500MB)
1. [supabase.com](https://supabase.com) par free project create karein.
2. Project Settings → Database se **Connection String (URI)** copy karein.
3. Supabase ke **SQL Editor** mein ja kar hamari project file `database/schema.sql` paste karke **Run** dabayein.
4. Render ke Environment Variables mein add karein:
   ```ini
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```

#### Option 2: Render PostgreSQL Database (availability/price verify karein)
1. Render dashboard par **New +** → **PostgreSQL** select karein.
2. Name dein (e.g. `gym-database`), Free plan select karein aur create karein.
3. Render aapko **Internal Database URL** de dega.
4. Is URL ko apne Web Service ke `DATABASE_URL` environment variable mein paste kar dein.
5. Application startup par automatically sari tables create kar legi!

---

## 7. Gym Owner Ka Secure Account Banana

Owner account banana nihayat secure hai aur iske liye koi hardcoded password use nahi hota:

### Online Setup Wizard (Bina Kisi Code Ke)
1. Jab aap pehli baar apni live website open karenge (`https://your-app.onrender.com/`), system detect karega ke database mein abhi koi owner nahi hai.
2. Website automatically aapko **`/setup`** page par redirect karegi.
3. Setup form mein details bharein:
   - **Gym Name**: e.g. *Apex Fitness Club*
   - **Currency**: `PKR` (ya USD/EUR)
   - **Timezone**: `Asia/Karachi`
   - **Owner Full Name**: e.g. *Malik Usman*
   - **Owner Phone**: `0300-1234567`
   - **Owner Username**: `owner` (ya koi bhi manpasand username)
   - **Owner Password**: Minimum 6 characters ka strong password
4. **Complete Setup & Enter Portal** button par click karein.
5. **Security Feature**: Account create hote hi `/setup` page **hamesha ke liye lock ho jata hai**. Koi doosra shakhs dobara account create nahi kar sakta!

---

## 8. Live URL Par Testing Checklist

Owner ko dene se pehle khud 5 minute mein test karein:

- [ ] **Owner Login**: `/login` par ja kar owner username aur password enter karein. Owner Command Center open hoga.
- [ ] **Create Trainer**: `Staff & Trainers` menu mein ja kar `+ Add Trainer` dabayein aur Coach account banayein.
- [ ] **Create Receptionist**: `+ Add Receptionist` dabayein aur front desk user banayein.
- [ ] **Register Member**: `Members` -> `+ Register Member` se test customer add karein. Confirm karein ke unique Member ID aur Digital QR Pass generate ho raha hai.
- [ ] **Print QR Pass**: Member detail page par ja kar **Print Badge** button check karein.
- [ ] **QR Camera Scanner**: Receptionist account se login karein aur `/receptionist/desk` par camera scan check karein.
- [ ] **Duplicate Scan Test**: Ussi member ko usi din dobara scan karein; system ko duplicate check-in block karna chahiye.
- [ ] **Monthly Fee Record**: `Monthly Payments` mein ja kar **Mark as Paid** dabayein aur receipt generate hona verify karein.
- [ ] **10-Day Absence Alert**: `Absence Alerts` page par 10-day rule aur alert status verify karein.

---

## 9. Data Backup Aur Restore Ka Tareeqa

### Agar Supabase / PostgreSQL Use Kar Rahe Hain:
- **Backup**: Supabase dashboard mein **Database** → **Backups** par click karein aur snapshot download karein, ya terminal se:
  ```bash
  pg_dump "YOUR_DATABASE_URL" > gym_backup.sql
  ```
- **Restore**:
  ```bash
  psql "YOUR_DATABASE_URL" < gym_backup.sql
  ```

### Agar Local SQLite (`gym_portal.db`) Use Kar Rahe Hain:
- Simply apne server se `gym_portal.db` file download karke Google Drive ya USB mein save kar lein.

---

## 10. Alternative Free Hosting (PythonAnywhere, Koyeb) & Limitations

| Platform | Free Tier Ke Fayde | Limitations & Challenges |
| :--- | :--- | :--- |
| **Render.com** (Recommended) | - HTTPS SSL free milta hai.<br>- Mobile camera permissions 100% chalte hain.<br>- GitHub auto-deploy support.<br>- Gunicorn native performance. | - Free web service 15 min baad sleep mode mein jati hai (pehli request par wake up mein 30-50 seconds lagte hain).<br>- Permanent data ke liye external PostgreSQL (Supabase/Neon) zaroori hai. |
| **PythonAnywhere** | - Python native WSGI platform.<br>- Simple file browser. | - Free tier par external PostgreSQL port 5432 blocked hoti hai.<br>- Outbound internet allowlist par restricted hai.<br>- Setup mein manual WSGI configuration required hai. |
| **Koyeb / Railway** | - Fast containers.<br>- Microservices support. | - Railway ab strict free plan nahi deta (limited trial credits hain). |

---

## 🎯 Gym Owner Ko Handover Message Template

Owner ko handover karte waqt yeh message bhejein:

> **Salam [Owner Name] Bhai,**
> 
> Aapka Gym Management Portal live ho chuka hai:
> 
> 🌐 **Website Link:** `https://your-app.onrender.com`  
> 👤 **Owner Username:** `owner`  
> 🔒 **Password:** `[Aapka Set Kiya Hua Password]`  
> 
> **Pehle Din Ka Workflow:**
> 1. Website khol kar login karein.
> 2. **Staff & Trainers** mein apne Trainers aur Front Desk Receptionist ke accounts banayein.
> 3. **Members** menu mein apne gym members add karein. Har customer ka **Printable Digital QR Badge** khud ban jayega.
> 4. Front desk par Receptionist apne mobile ya laptop se QR Code scan karke attendance lagayegi.
> 5. Monthly fees aane par **Monthly Payments** mein ja kar **Mark as Paid** dabana hoga.
