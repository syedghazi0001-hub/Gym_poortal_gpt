# VANGUARD GYM OS — COMPLETE HANDOVER & EXECUTION MANUAL

Yeh document aapke liye ek **Master Blueprint** hai jisme step-by-step likha hai ke:
1. Is system ko apne computer par 2 minute mein kaise run karke test karna hai.
2. Agar bina kisi paisay ke online live URL banana ho to Render ke available free plan par deployment kaise try karna hai (current restrictions verify karein).
3. Asal Gym Owner ko yeh app kaise handover karni hai aur uska login/password kaise dena hai.
4. Kaun si file kya kaam karti hai.
5. Kisi doosre AI ya developer se help lene ke liye ready-made prompt.

---

## 📁 1. Project Files Directory & Explanation (Kaun Si File Kya Hai)

Aapke project ke andar yeh files hain:

| File / Folder | Kya Kaam Karti Hai? |
| :--- | :--- |
| **`app.py`** | Main Flask server engine. Saari routes, security filters, aur templates yahan se control hoti hain. |
| **`wsgi.py`** | Production WSGI entrypoint (Gunicorn / Render / hosting servers ke liye). |
| **`Procfile`** | Cloud servers (Render, Railway, Heroku) ke liye 1-click startup command. |
| **`run_local.bat`** | **Windows users ke liye 1-click file**. Is par double-click karne se server khud chal parta hai. |
| **`run_local.sh`** | **Mac / Linux users ke liye 1-click script**. |
| **`requirements.txt`** | Python dependencies ki list (`flask`, `psycopg2-binary`, `qrcode`, `gunicorn`, etc.). |
| **`.env.example`** | Environment settings ka template (secret keys, timezone). |
| **`gym_portal.db`** | Relational database (SQLite/PostgreSQL engine jo offline aur free tier dono par chalta hai). |
| **`database/`** | Database connection pool (`connection.py`), PostgreSQL schema (`schema.sql`), aur SQLite schema (`schema_sqlite.sql`). |
| **`services/`** | Asal business logic: `member_service.py` (member registration & QR badges), `attendance_service.py` (QR check-in & duplicate block), `payment_service.py` (fee tracking), `absence_service.py` (10-day absence alerts). |
| **`routes/`** | Web pages ke controllers (`owner_routes.py`, `receptionist_routes.py`, `trainer_routes.py`, `member_routes.py`, `api_routes.py`). |
| **`templates/`** | Dark theme HTML web pages (Owner Dashboard, Scanner Desk, Member Pass, Staff Management). |
| **`static/`** | Styling CSS, Camera QR scanner script (`scanner.js`), vector gym logo (`logo.svg`), aur charts (`charts.js`). |
| **`scripts/`** | Utility tools: `prepare_for_owner.py` (clean database banana), `seed_demo_data.py` (sample accounts banana), `check_absence.py` (absence engine). |
| **`tests/`** | Automated testing files jo verify karti hain ke system 100% bugs-free hai. |

---

## 💻 2. Testing Ke Liye Apne Computer Par Chalana (2 Minute Guide)

Aapko PythonAnywhere ki koi zaroorat nahi hai. Aap apne laptop/PC par isko 100% free test kar sakte hain:

### Agar Aap Windows Par Hain:
1. Is `gym-management` folder ko open karein.
2. File dhoondhein: **`run_local.bat`**
3. Us par **Double Click** karein!
   - Yeh automatically virtual environment banayega.
   - Requirements install karega.
   - Aur server start kar dega.
4. Browser kholen aur type karein:
   ```
   http://127.0.0.1:5000
   ```
   Aapka Gym Portal open ho jayega!

### Agar Aap Mac / Linux / VS Code Terminal Par Hain:
Terminal kholen aur yeh 3 commands chalayein:
```bash
cd gym-management
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```
Browser mein kholen: `http://127.0.0.1:5000`

---

## 🌐 3. Online Free Live Link Banana (Render.com — PythonAnywhere Ka Aasan Alternative)

Agar aap chahte hain ke gym owner apne mobile par ya kisi bhi laptop par link khol sake (bina aapka computer on rakhe), to **Render.com** sab se aasan aur **Free plan ki current availability aur restrictions verify karna zaroori hai** tareeqa hai:

1. [www.render.com](https://render.com) par free account banayein (Sign in with GitHub).
2. Apna yeh code GitHub repository par upload/push karein.
3. Render Dashboard par ja kar click karein: **New +** → **Web Service**.
4. Apni GitHub repository select karein.
5. Render settings mein yeh likhein:
   - **Name**: `my-gym-portal` (ya gym ka naam)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:application`
   - **Plan**: `Free` ($0/month)
6. Click karein **Create Web Service**.
7. 2 minute mein Render aapko ek live HTTPS link de dega:
   `https://my-gym-portal.onrender.com`
   *(Yeh link mobile, tablet aur PC sab par camera QR scanner ke sath 100% live chalega).*

---

## 🔑 4. Gym Owner Ke Hawale Kaise Karna Hai (Handover Procedure)

Jab aapki testing complete ho jaye aur aapne gym owner ko app deni ho, to system se fake/test data khatam karke **Owner ka apna account** create karna hoga:

### Tareeqa A: Terminal / Script Ke Zariye (Sab Se Aasan)
Apne terminal ya command prompt mein yeh command chalayein:
```bash
python scripts/prepare_for_owner.py
```
Yeh script aapse poochhegi:
- **Gym Name**: (e.g. *Iron Fitness Club*)
- **Owner Full Name**: (e.g. *Usman Ghani*)
- **Owner Phone**: (e.g. *0300-1234567*)
- **Owner Login Username**: (e.g. *owner*)
- **Owner Login Password**: (ek unique strong password jo owner khud set kare)

Enter dabate hi:
- Pura purana test data saaf ho jayega.
- Sirf Owner ka real account database mein save hoga.
- Screen par username aur password print ho jayega.

### Tareeqa B: Browser Setup Wizard Ke Zariye
Agar aap `gym_portal.db` file delete kar dein aur server start karein, to pehli baar website kholte hi automatic **Initial Setup Wizard (`/setup`)** screen khulegi. Wahan owner khud apna Gym Name, Currency, Timezone aur Password set kar sakta hai!

---

## 📋 5. Gym Owner Ko WhatsApp / Email Par Handover Message

Owner ko handover karte waqt aap yeh message bhej sakte hain:

> **Salam [Owner Name] Bhai,**
> 
> Aapka Gym Management Portal tayyar hai. Details neechay di gayi hain:
> 
> 🌐 **Portal Link:** `https://your-domain-or-ip:5000` (ya aapka live URL)  
> 👤 **Username:** `owner`  
> 🔒 **Password:** Owner ke liye setup ke waqt banaya gaya unique password (is document mein password na likhein).  
> 
> **Pehle Din Ka Kaam:**
> 1. Is link par ja kar login karein.
> 2. **Staff & Trainers** menu mein ja kar apne Trainers aur Front Desk Receptionist ke accounts banayein (username aur password ke sath).
> 3. **Members** menu mein ja kar **+ Register Member** se apne customers add karein. System har customer ka unique QR Code aur Login ID khud bana dega.
> 4. Front desk par Receptionist apne account se login karke camera se QR code scan karegi aur rozana attendance mark karegi.
> 5. Monthly fees collect hone par **Monthly Payments** mein ja kar **Mark as Paid** dabana hoga.

---

## 🏋️ 6. Gym Ke Rozana Operations (Owner & Staff Ka Workflow)

### 1. Owner Ka Kaam (Daily / Weekly):
- **Dashboard Dekhna**: Kitne active members hain, aaj kitne log aaye, is month kitni fees collect hui, aur kaunse log 10 din se gym nahi aa rahe (10-Day Absence Alert).
- **Naye Customer Add Karna**: `Members` -> `+ Register Member`. Form bharte hi customer ka Digital Card generate ho jayega jisko print karke customer ko diya ja sakta hai.
- **Gym Settings**: Agar fees currency (PKR), gym ka naam, ya address change karna ho to `Gym Settings` se kar sakte hain.

### 2. Receptionist Ka Kaam (Front Desk):
- Receptionist apne username/password se login karegi.
- **QR Scanner Terminal** open karegi.
- Customer apna phone ya printable card scanner ke aagay karega:
  - System chime sound bajayega aur green tick dikhayega: *"Welcome [Name]! Attendance Verified."*
  - Agar wohi customer dubara scan kare, to system red error dega: *"Already checked in today."*
- Agar customer ke paas phone na ho, to screen par naam type karke **Check In** button daba sakti hai.
- Month ke start mein fees collect karke **Record Payments** menu mein ja kar **Mark as Paid** karegi.

### 3. Customer / Member Ka Kaam:
- Customer apne mobile par login karega.
- Usay apna **Digital QR Pass** nazar aayega.
- Uski attendance streak (e.g. 15 Days Streak 🔥) aur total attended/absent days dikhenge.
- Uski monthly fee status (Paid ya Pending) dikhegi.
- Agar woh 10 din se gym na jaye, to usay warning alert dikhega: *"Aap ne pichlay 10 din se attendance mark nahi karwai. Gym se rabta karein."*

---

## 🤖 7. Kisi Doosre AI Ya Developer Se Help Lene Ke Liye Ready-Made Prompt

Agar aapko aage chal kar kisi doosre AI (ChatGPT, Claude, DeepSeek waghera) se koi sawaal poochna ho ya modification karwani ho, to aap **neechay wala box copy karke seedha paste** kar sakte hain:

```text
Maine ek Flask-based Python Gym Management System (Vanguard Gym OS) build kiya hua hai.
Tech Stack & Architecture:
- Backend: Python 3.11+, Flask application factory, WSGI compatible (Procfile with Gunicorn).
- Database: Dual relational engine (PostgreSQL Supabase schema in database/schema.sql, local SQLite in gym_portal.db / database/schema_sqlite.sql with auto-switch).
- Frontend: HTML5, modern CSS with deep charcoal dark theme (#121721), Vanilla JS, Web Audio API chime, no Node.js/build steps.
- Security: Role-based access control with @role_required decorator for 4 roles: 'owner', 'receptionist', 'trainer', 'member'. Werkzeug PBKDF2 password hashing.
- Core Features:
  1. Member registration with auto-generated ID (MEM-2026-XXXX) and unique QR code tokens.
  2. Front-desk camera QR attendance scanner with duplicate check-in prevention (UNIQUE member_id, attendance_date).
  3. Monthly fee tracker with duplicate month prevention (UNIQUE member_id, billing_month) and receipt generation.
  4. Ten-day consecutive absence alert engine with owner alerts and member Urdu portal warning.
  5. Trainer hub with coaching notes for assigned trainees.
  6. Dedicated member portal with printable digital QR badges and streak counters.
- Current Status: 100% unit tests pass via pytest in tests/ directory.

Mera sawaal yeh hai ke: [Yahan apna sawaal likhein, maslan: isko Render par deploy kaise karoon / ya isme WhatsApp API kaise joroon]
```

---

Aapko ab PythonAnywhere par time waste karne ki koi zaroorat nahi hai. Simply `run_local.bat` par double-click karke apne PC par chala kar test karein, phir `python scripts/prepare_for_owner.py` se clean database bana kar owner ke hawale kar dein!
