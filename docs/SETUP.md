# Setup Guide — Job Pipeline for Your Own Laptop

A step-by-step guide to running the job pipeline on a fresh Windows laptop. Expect ~60–90 minutes from start to first scored job, assuming no errors.

**What this guide covers:**
- Prerequisites and hardware check
- Cloning and configuring the repo
- Building your own `profile.json`
- Setting up Google Sheets + OAuth (the trickiest step)
- Running the pipeline
- Common errors and fixes

**This guide is for Windows users.** If you're on Mac or Linux, most steps work the same — substitute `cp` for `Copy-Item`, etc.

---

## ✅ Checkpoint 0 — Hardware check

Before installing anything, confirm:

- [ ] **Windows 10 or 11** (64-bit)
- [ ] **At least 16 GB RAM** (8 GB will run but be sluggish; Ollama + Docker + Chrome together need headroom)
- [ ] **At least 15 GB free disk space** (Docker images + the Llama 3.2 3B model are ~5 GB; CSVs, cache, and overhead add more)
- [ ] **A stable internet connection** for first-time downloads (~3 GB total)
- [ ] **About 90 minutes** of uninterrupted time

If you're below the RAM minimum or short on disk, stop here and address that first. Running this on low-spec hardware leads to timeouts that look like bugs but are just exhaustion.

---

## ✅ Checkpoint 1 — Install prerequisites

You need three tools installed before anything else.

### 1.1 Docker Desktop

Download and install from: https://www.docker.com/products/docker-desktop/

After install:
- Launch Docker Desktop
- Wait for the whale icon in your system tray to turn solid white (no animation)
- This takes 30–60 seconds the first time

**Verify:**
```powershell
docker --version
docker compose version
```

Both should print version numbers. If either errors, Docker Desktop isn't running yet — wait longer.

### 1.2 Git for Windows

Download and install from: https://git-scm.com/download/win

Accept all defaults during install.

**Verify:**
```powershell
git --version
```

Should print something like `git version 2.45.0`.

### 1.3 A code editor (VS Code recommended)

Download and install from: https://code.visualstudio.com/

This is for editing `profile.json` and other config files. Notepad works too, but VS Code shows JSON syntax errors immediately.

---

## ✅ Checkpoint 2 — Clone the repo

Open **PowerShell** (search "powershell" in the Start menu). You'll work from here for the rest of the guide.

Pick where you want the project to live. The user folder is fine:

```powershell
cd $env:USERPROFILE
git clone https://github.com/Ayushman-Raghav/job-pipeline.git
cd job-pipeline
```

**Verify:** you should now see the project files:

```powershell
ls
```

Expected output: folders for `assets`, `jobspy-service`, `workflows`, and files like `README.md`, `docker-compose.yml`, `.env.example`.

---

## ✅ Checkpoint 3 — Create your environment file

Copy the example env file. You don't need to edit anything in it — the defaults work locally.

```powershell
Copy-Item .env.example .env
```

**Verify:**
```powershell
ls .env
```

Should show the file exists.

---

## ✅ Checkpoint 4 — Create YOUR profile.json

This is the most important step. The pipeline scores jobs against this profile. If it doesn't match your actual experience, the scores will be meaningless.

### 4.1 Start from the example

```powershell
Copy-Item jobspy-service\profile.example.json jobspy-service\profile.json
```

### 4.2 Open it in VS Code

```powershell
code jobspy-service\profile.json
```

You'll see a JSON file with sections like `candidate`, `experience`, `education`, `core_skills`, `target_roles`, `preferences`, `strengths_to_highlight`.

### 4.3 Edit these sections to match YOU

Replace the example values with your real info. **Do not change the structure** (key names, brackets, quotes) — only the values.

**Required edits:**

| Field | What to put |
|---|---|
| `candidate.name` | Your full name |
| `candidate.current_location` | City, Country |
| `candidate.willing_to_relocate` | List of locations you'd move to |
| `candidate.right_to_work` | Your work authorization (e.g. "Ireland (full)", "UK (graduate visa)") |
| `experience.total_years` | Your years of experience as a number |
| `experience.current_seniority` | Your current title (e.g. "Senior Analyst") |
| `experience.current_employer` | Your current employer |
| `experience.previous_employer` | Your previous employer |
| `experience.domains` | Industries you've worked in |
| `education.highest` | Your highest qualification |
| `education.university` | The institution |
| `education.year` | Year of graduation |
| `certifications` | List of your certifications |
| `core_skills` | Your real skills grouped by category — keep the four categories, replace items inside |
| `target_roles.preferred` | Roles you actively want |
| `target_roles.acceptable` | Roles you'd accept but aren't first choice |
| `target_roles.avoid` | Roles you don't want recommended |
| `preferences.salary_min_eur` | Minimum salary you'd accept (number, no comma) |
| `preferences.salary_target_eur` | Your target salary |
| `preferences.industries_preferred` | Industries you want to work in |
| `preferences.industries_avoid` | Industries you don't want |
| `strengths_to_highlight` | 5–7 short bullets summarising what makes you a strong candidate |
| `things_that_dont_fit` | Roles or contexts you explicitly don't want — be honest, this improves scoring |

### 4.4 Save and validate

After editing, save the file (Ctrl+S in VS Code).

**Verify it's valid JSON:**

```powershell
Get-Content jobspy-service\profile.json | ConvertFrom-Json | Out-Null
```

No output = valid JSON. If you see a red error, you broke the syntax somewhere — likely a missing comma, bracket, or quote. Fix and re-run.

---

## ✅ Checkpoint 5 — Create your Google Sheet

The pipeline writes scraped jobs and their scores to a Google Sheet. You need your own.

### 5.1 Create a new sheet

1. Go to https://sheets.google.com
2. Click **Blank** to make a new sheet
3. Name it something memorable like "Job Pipeline Output"

### 5.2 Add the headers

Click cell **A1**, then paste this entire line into the formula bar:

```
scraped_at	role_family	site	title	company	location	date_posted	is_remote	job_url	min_amount	max_amount	currency	search_term	description	fit_score	fit_reason
```

The values are tab-separated, so they'll fill columns A through P in one go.

**Verify:** A1 says `scraped_at`, B1 says `role_family`, ..., P1 says `fit_reason`.

**Critical:** make sure there are NO leading or trailing spaces in any cell. Spaces are invisible but break n8n's column matching. Diagnostic: click any empty cell and type `=LEN(E1)` — it should return exactly 5 (the length of "title"). If it returns 6 or 7, there's whitespace. Retype the cell.

### 5.3 Get your Sheet ID

Look at the browser URL. It will look like:

```
https://docs.google.com/spreadsheets/d/1ABCDEF12345xyz789ghijk/edit#gid=0
```

The Sheet ID is the long string between `/d/` and `/edit`. Copy it. You'll paste it into the workflow shortly.

---

## ✅ Checkpoint 6 — Set up Google OAuth (the fiddly one)

n8n needs permission to read and write to your Google Sheet. This requires a Google Cloud project with OAuth credentials. **This is the most confusing step. Expect ~20 minutes. Follow each substep exactly.**

### 6.1 Open Google Cloud Console

Go to https://console.cloud.google.com/

If you've never used Google Cloud before, you'll be asked to accept terms. Free tier covers everything we need.

### 6.2 Create a new project

1. Click the project dropdown at the top of the page (next to "Google Cloud" logo)
2. Click **New Project**
3. Name it `job-pipeline-n8n` (or anything memorable)
4. Click **Create**
5. Wait for the project to be created, then **switch to it** using the same dropdown

### 6.3 Enable the Google Sheets API

1. In the left sidebar, navigate to **APIs & Services** → **Library**
2. Search for `Google Sheets API`
3. Click it
4. Click **Enable**
5. Wait for it to enable (5–10 seconds)

### 6.4 Configure the OAuth consent screen

1. In the left sidebar, navigate to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (because you're not in a Google Workspace organization)
3. Click **Create**
4. Fill in:
   - **App name:** `Job Pipeline`
   - **User support email:** your email
   - **Developer contact email:** your email
5. Click **Save and Continue**
6. **Scopes screen:** click **Save and Continue** (we'll add scopes later)
7. **Test users screen:** click **+ Add Users**, add your own Gmail address (the one your Sheet is in)
8. Click **Save and Continue**
9. Click **Back to Dashboard**

### 6.5 Create OAuth credentials

1. In the left sidebar, navigate to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. **Application type:** Web application
4. **Name:** `n8n local`
5. **Authorized redirect URIs:** click **+ Add URI** and paste exactly:
   ```
   http://localhost:5678/rest/oauth2-credential/callback
   ```
6. Click **Create**
7. A modal pops up showing your **Client ID** and **Client Secret**
8. **Copy both values** — save them in a temporary text file. You'll paste them into n8n in the next checkpoint.

---

## ✅ Checkpoint 7 — Start the Docker stack

```powershell
cd $env:USERPROFILE\job-pipeline
docker compose up -d
```

This will:
- Pull the n8n, Ollama, and Python base images (~2 GB on first run)
- Build the jobspy-service container
- Start all three services

**Expected time:** 5–10 minutes on first run, 30 seconds on subsequent runs.

**Verify all three are up:**

```powershell
docker compose ps
```

You should see three containers: `jobspy-service`, `n8n`, `ollama`, all with status `Up`.

**Verify jobspy is healthy:**

```powershell
(Invoke-WebRequest http://localhost:8000/health).Content
```

Should return: `{"status":"ok","service":"jobspy-service","version":"3.0.0"}`

---

## ✅ Checkpoint 8 — Pull the Llama model

The Ollama container is up but doesn't have a model loaded yet. Pull the small one:

```powershell
docker exec -it ollama ollama pull llama3.2:3b
```

This downloads a 2 GB file. **Expected time:** 5–20 minutes depending on connection speed.

**Verify the model is loaded:**

```powershell
docker exec ollama ollama list
```

Should show `llama3.2:3b` with size 2.0 GB.

---

## ✅ Checkpoint 9 — Set up n8n

### 9.1 Open n8n

In a browser, go to http://localhost:5678

You'll see an n8n setup screen. Create an owner account:
- **Email:** your email
- **Password:** something memorable

This account exists only on your local n8n instance.

### 9.2 Import the workflow

1. In n8n, click the **Workflows** menu (top left)
2. Click **+ Add workflow**
3. Then click the menu (three dots, top right of the canvas) → **Import from File**
4. Navigate to and select: `C:\Users\<your-username>\job-pipeline\workflows\job-pipeline-phase-4.json`
5. Click **Open**

The full 11-node workflow appears on the canvas.

### 9.3 Connect Google Sheets credentials

1. Click any of the **Google Sheets** nodes (e.g., "Append or update row in sheet")
2. In the right-hand panel, find **Credential to connect with**
3. Click **+ Create New Credential**
4. Select **Google Sheets OAuth2 API**
5. Paste in:
   - **Client ID:** (from Checkpoint 6.5)
   - **Client Secret:** (from Checkpoint 6.5)
6. Click **Sign in with Google**
7. A new browser tab opens for Google OAuth
8. Choose your Google account (the one your sheet is in)
9. You'll see a warning that the app is unverified — click **Advanced** → **Go to Job Pipeline (unsafe)**. This is fine because the app is yours.
10. Click **Allow** to grant access
11. The tab will redirect and show "Got it!" or close automatically
12. Back in n8n, the credential is now connected

### 9.4 Set your Sheet ID in each Google Sheets node

For each Google Sheets node in the workflow (there are 3: "Append or update row in sheet", "Read unscored rows", "Write scores to sheet"):

1. Click the node
2. In the **Document** field, you'll see a dropdown. Click it.
3. Find your sheet (it'll be listed by name now that you're authenticated)
4. Select it
5. In the **Sheet** field, select **Sheet1** (or whatever your first tab is named)

Do this for all 3 Google Sheets nodes.

### 9.5 Save the workflow

Click **Save** (top right).

---

## ✅ Checkpoint 10 — Run the workflow

1. Click the **Execute Workflow** button (bottom of the canvas)
2. The workflow begins running

**What happens:**
- ~5 minutes: scrapes 8 role/geo combinations from Indeed and LinkedIn
- ~1 minute: deduplicates and writes results to your Google Sheet
- Up to ~50 minutes: scores each job 0–10 with the local LLM

**Monitor progress:**

Open your Google Sheet — rows will start populating during the scrape phase. The `fit_score` and `fit_reason` columns fill in later, during scoring.

**Verify scoring works (after the workflow finishes):**

```powershell
(Invoke-WebRequest http://localhost:8000/score-cache/stats).Content
```

Should show a count of scored jobs (e.g., `{"count": 145, ...}`).

---

## 🎉 You're set up!

Sort your sheet by `fit_score` descending to see your highest-fit jobs at the top. Each one has a one-sentence reason explaining the score.

To re-run the pipeline tomorrow: just open n8n and click **Execute Workflow** again. The score cache means previously-scored jobs are returned instantly; only new jobs cost inference time.

---

## 🆘 Troubleshooting

### "Unable to connect to localhost:8000"
Docker Desktop isn't running, or the containers haven't started yet. Run `docker compose ps` — all three containers should show `Up`. If not, run `docker compose up -d`.

### "Cannot connect to Docker daemon"
Docker Desktop isn't running. Open it from the Start menu and wait for the whale icon to turn solid white.

### "Out of memory" or containers keep restarting
Your laptop doesn't have enough RAM. Close Chrome, Slack, other heavy apps. If it still fails, try the smaller Llama 3.2 1B model instead: `docker exec -it ollama ollama pull llama3.2:1b`, then change `OLLAMA_MODEL` in your `.env` to `llama3.2:1b`.

### Google OAuth shows "redirect_uri_mismatch"
The redirect URI in your Google Cloud OAuth client doesn't match exactly. Go back to Checkpoint 6.5 and verify it's `http://localhost:5678/rest/oauth2-credential/callback` exactly — no trailing slash, http not https.

### Google Sheets node errors with "schema not detected"
There's hidden whitespace in your sheet headers. Click each header cell and re-type the value. Then in n8n, toggle the Mapping Column Mode dropdown off and back on to force a schema refresh.

### Workflow runs but no scores appear
The `Read unscored rows` node might be filtering everything out. Open it and check: `Filter` should be set to `fit_score is empty`. Re-run the workflow.

### Ollama scoring is very slow (>20 sec per job)
Your laptop is underpowered for the 3B model. Try the 1B model (see above) — it's faster but slightly less discriminating.

### "fit_score column is empty after a full run"
The scoring batch took longer than n8n's timeout. Check `docker logs jobspy-service --tail 100` — if it says "score-batch: done", scoring finished but n8n disconnected. Re-run the workflow; the cache will fill in instantly.

---

## 🔧 Customising the pipeline

**Change search locations:** open the workflow in n8n, click the "Build search configs" node, edit the JavaScript code.

**Change role families:** same node — modify the role names and search terms.

**Tweak the scoring prompt:** edit `jobspy-service/app.py`, find the `SCORE_PROMPT` constant, modify, then rebuild: `docker compose up -d --build`.

**Switch to the bigger model (Llama 3.1 8B):** much sharper reasoning, 3–5x slower. Pull it (`docker exec -it ollama ollama pull llama3.1:8b`) and change `OLLAMA_MODEL=llama3.1:8b` in `.env`.

---

## 📚 What's running

Three Docker containers on a shared network:

- **jobspy-service** (port 8000) — Python FastAPI service that scrapes job boards and scores jobs against your profile
- **n8n** (port 5678) — Workflow orchestrator. The UI you use to trigger the pipeline.
- **ollama** (port 11434) — Local LLM runtime. Runs the Llama model that scores each job.

They share a Docker volume at `/data/shared` where CSVs and the score cache live.

Your data never leaves your laptop. No API keys are sent anywhere except Google Sheets (your own account).

